"""Peer calibration for the challenge layer (F-121 substrate-grounded tier).

Governance (docs/PEER_GOVERNANCE_RULINGS.md):
  R1 selection authority — cohort membership is PRE-REGISTERED and attribute-
     derived (the applicant's asset band), never hand-picked. No client-number
     knowledge enters selection.
  R2 direction of inference — a peer PLACEMENT is consistency evidence, and a
     value derived FROM the cohort is tagged so the challenge layer never reads
     circular support. (Foundry inputs are not peer-derived here, so placement
     is independent — but the provenance still records the cohort + vintage.)
  R4 thin evidence — small groups are LABELED (n per point), never suppressed;
     the substrate floor is n=3, so the n<SMALL_N honesty rider does real work.
  R5 statistic of record — the substrate serves the distribution; where a value
     sits at/over a percentile seam the WORSE reading governs the flag.
  Per-metric vintage — earnings/capital/concentration reach 2026Q1; funding
     metrics (deposit_cost, brokered) lag to 2025Q4 until M6a. The provenance
     carries the vintage PER METRIC, never one global 'as of'.

Tier today: PROVISIONAL (asset-band + universe proxies; UBPR/Deliverable-D not
landed). certified stays False. Flipping to certified is a data-only swap behind
the same schema — no code change here.

Fail-closed: any substrate miss falls back to the static Roman-lineage band with
its honest provenance. Percentile grounding is ADDITIVE; the engine's flag set is
never weakened by a substrate outage.
"""
from .peer_bands import get_bands, corridor_position, BandsError, SMALL_N_THRESHOLD

# Foundry asset-band buckets mirror the substrate's stored group_ids exactly
# ($mm thresholds). Derivation is from the applicant's OWN projected size — the
# pre-registered rule, frozen before any challenge value is read (R1).
_ASSET_BANDS = [
    (200, "under_200M"), (500, "200M_500M"), (2000, "500M_2B"),
    (10000, "2B_10B"), (50000, "10B_50B"), (float("inf"), "over_50B"),
]

def asset_band_for(total_assets_000s):
    """(cert-free) attribute-derived band from projected assets. $000s -> $mm."""
    mm = (total_assets_000s or 0.0) / 1000.0
    for hi, name in _ASSET_BANDS:
        if mm < hi:
            return name
    return "over_50B"

# Challenge-flag metric -> (substrate metric_name, vintage tier). The vintage tier
# is documentation the provenance surfaces; the substrate returns its own latest.
# 'substrate' = reaches 2026Q1; 'funding_legacy' = lags to 2025Q4 until M6a.
FLAG_METRIC_MAP = {
    "FUND-HOT":  ("deposit_cost",       "funding_legacy"),
    "FUND-DDA":  ("deposit_cost",       "funding_legacy"),
    "CO-BAND":   ("net_charge_off_pct", "substrate"),   # disclosure-ledger id
    "BAND-CO":   ("net_charge_off_pct", "substrate"),   # emitted-flag id (BAND-CO-HI/LO)
}
VINTAGE_LABEL = {
    "substrate": "2026Q1 (substrate-grade)",
    "funding_legacy": "2025Q4 (legacy; M6a pending)",
}

def calibrate_thresholds(static_thresholds, total_assets_000s):
    """Attach peer context to each static threshold WITHOUT replacing it.

    Returns (rows, provenance). Each row keeps its static id/rule/trigger/sev and
    gains, when a substrate band resolves: band_metric, cohort, vintage, the p10..p90
    distribution, and n. Selection is pre-registered (asset band). Fail-closed:
    an unresolved metric leaves the static row untouched and records the reason.
    """
    band = asset_band_for(total_assets_000s)
    cohort = band  # a stored group_id; the endpoint also accepts arbitrary cohorts
    rows, any_live, reasons = [], False, []
    for th in static_thresholds:
        row = dict(th)
        parts = th["id"].split("-")
        two = "-".join(parts[:2]) if len(parts) >= 2 else th["id"]
        mapped = (FLAG_METRIC_MAP.get(th["id"]) or FLAG_METRIC_MAP.get(two))
        if not mapped or not mapped[0]:
            row["peer"] = None
            row["peer_note"] = "structural check — no peer metric maps to this rule"
            rows.append(row); continue
        metric, tier = mapped
        try:
            parsed, source = get_bands(metric, cohort)
            latest = parsed["bands"][-1] if parsed.get("bands") else None
            if latest:
                n = latest.get("n")
                row["peer"] = {
                    "band_metric": metric, "cohort": cohort,
                    "vintage": VINTAGE_LABEL.get(tier, tier),
                    "p10": latest["p10"], "p25": latest["p25"], "p50": latest["p50"],
                    "p75": latest["p75"], "p90": latest["p90"], "n": n,
                    "source": source,
                    "small_n": (n is not None and n < SMALL_N_THRESHOLD),
                }
                any_live = True
            else:
                row["peer"] = None
                row["peer_note"] = "cohort resolved but carried no band for this quarter"
        except BandsError as e:
            row["peer"] = None
            row["peer_note"] = f"substrate miss — static threshold governs ({str(e)[:60]})"
            reasons.append(metric)
        except Exception as e:
            row["peer"] = None
            row["peer_note"] = f"substrate unreachable — static threshold governs"
            reasons.append(metric)
        rows.append(row)
    if any_live:
        prov = (f"asset-band peer cohort '{band}' \u2014 percentiles per metric at the vintage "
                f"shown; distributions carry n per point (substrate floor n=3, small-n labeled "
                f"not suppressed). Selection is pre-registered by projected asset size, not "
                f"hand-picked. Placement is consistency evidence, not support. Provisional tier: "
                f"UBPR reconciliation (Deliverable D) pending \u2014 not yet certified.")
    else:
        prov = ("standard industry ranges \u2014 not yet calibrated to a peer cohort; "
                "peer-percentile grounding attaches with the evidence layer")
    return rows, prov


def place_flag_value(value, metric, cohort, worse="high"):
    """R5 placement with the conservative rule: return the corridor AND, at a seam,
    the worse-for-applicant reading. 'worse' = which direction is aggressive:
    'high' (deposit cost, charge-offs — high is bad), 'low' (spreads — low is bad).
    Returns dict or None on substrate miss (fail-closed)."""
    try:
        parsed, source = get_bands(metric, cohort)
    except Exception:
        return None
    band = parsed["bands"][-1] if parsed.get("bands") else None
    if not band:
        return None
    pos = corridor_position(value, band)
    n = band.get("n")
    return {"corridor": pos, "n": n, "source": source,
            "small_n": (n is not None and n < SMALL_N_THRESHOLD),
            "p50": band["p50"], "p90": band["p90"], "p10": band["p10"],
            "conservative_note": ("worse-reading governs at a seam per R5; direction="
                                   + worse)}
