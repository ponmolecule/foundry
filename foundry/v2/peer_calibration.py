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
    # --- CONFIRMED against prod substrate (peer_metric_audit, 2026Q1, 45 quarters) ---
    # Clean like-for-like matches:
    "FUND-HOT":  ("deposit_cost",            "substrate"),
    "FUND-DDA":  ("deposit_cost",            "substrate"),
    "PRICE-USURY":    ("loan_yield",         "substrate"),
    "PRICE-LOWYIELD": ("loan_yield",         "substrate"),
    "COUPLED-02":     ("loan_yield",         "substrate"),   # yield leg of the joint rule
    "RES-THIN":       ("alll_to_loans",      "substrate"),
    "PROV-BELOW-CO":  ("provision_to_avg_assets", "substrate"),
    # Value-adding proxy (labeled): sustainable-growth capacity, not observed growth.
    "FUND-GROWTH":    ("max_sustainable_growth", "proxy_growth"),  # pierces optimistic growth
    # Charge-off: the REAL metrics (net_charge_off_rate / _ubpr) are being written to the
    # substrate now. Encode them as a preference LIST — the first that resolves wins, so the
    # flag AUTO-UPGRADES from the npl_ratio proxy to the real charge-off band the moment the
    # columns land, with no code change. Tier is per-candidate so the label stays honest.
    "CO-BAND":        [("net_charge_off_rate", "substrate"),
                       ("net_charge_off_rate_ubpr", "substrate"),
                       ("npl_ratio", "proxy_credit")],   # disclosure-ledger id
    "BAND-CO":        [("net_charge_off_rate", "substrate"),
                       ("net_charge_off_rate_ubpr", "substrate"),
                       ("npl_ratio", "proxy_credit")],   # emitted-flag id (BAND-CO-HI/LO)
    # --- genuinely absent in substrate: stay fail-closed on static bars ---
    # GOS-MARGIN-HI, GOS-WAREHOUSE, MSR-CAP, MSR-FEE (mortgage-banking niche, no peer metric)
}


def _resolve_mapped(mapped):
    """A FLAG_METRIC_MAP value is either a single (metric, tier) or a preference list
    of them. Yield each (metric, tier) candidate in order so the caller can try the
    real metric first and fall back to a proxy. Fail-closed: unknown shape -> nothing."""
    if mapped is None:
        return []
    if isinstance(mapped, tuple):
        return [mapped]
    if isinstance(mapped, list):
        return [m for m in mapped if isinstance(m, tuple)]
    return []


VINTAGE_LABEL = {
    "substrate": "2026Q1 (substrate-grade)",
    "funding_legacy": "2025Q4 (latest published; funding-metric refresh in progress)",
    "proxy_growth": "2026Q1 \u2014 sustainable-growth band (capacity proxy, not observed growth)",
    "proxy_credit": "2026Q1 \u2014 NPL band (credit-quality proxy, not net charge-offs)",
}

def calibrate_thresholds(static_thresholds, total_assets_000s):
    """Attach peer context to each static threshold WITHOUT replacing it.

    Returns (rows, provenance). Each row keeps its static id/rule/trigger/sev and
    gains, when a substrate band resolves: band_metric, cohort, vintage, the p10..p90
    distribution, and n. Selection is pre-registered (asset band). Fail-closed:
    an unresolved metric leaves the static row untouched and records the reason.
    """
    band = asset_band_for(total_assets_000s)
    cohort = band  # a stored group_id -> served by the single CHARTERIQ_DATABASE_URL client
    rows, any_live, reasons = [], False, []
    for th in static_thresholds:
        row = dict(th)
        parts = th["id"].split("-")
        two = "-".join(parts[:2]) if len(parts) >= 2 else th["id"]
        mapped = (FLAG_METRIC_MAP.get(th["id"]) or FLAG_METRIC_MAP.get(two))
        candidates = _resolve_mapped(mapped)
        if not candidates:
            row["peer"] = None
            row["peer_note"] = "structural check — no peer metric maps to this rule"
            rows.append(row); continue
        # try candidates in order; first that resolves wins (real metric before proxy)
        latest, metric, tier, source = None, None, None, None
        last_reason = None
        for cand_metric, cand_tier in candidates:
            try:
                parsed, src = get_bands(cand_metric, cohort)
                b = parsed["bands"][-1] if parsed.get("bands") else None
                if b:
                    latest, metric, tier, source = b, cand_metric, cand_tier, src
                    break
            except BandsError as e:
                last_reason = str(e)[:60]; continue
            except Exception:
                last_reason = "substrate unreachable"; continue
        try:
            if latest:
                n = latest.get("n")
                _q = latest.get("quarter") or "latest"
                row["peer"] = {
                    "band_metric": metric, "cohort": cohort,
                    "vintage": _q + (" (proxy)" if str(tier).startswith("proxy") else ""),
                    "p10": latest["p10"], "p25": latest["p25"], "p50": latest["p50"],
                    "p75": latest["p75"], "p90": latest["p90"], "n": n,
                    "source": source,
                    "small_n": (n is not None and n < SMALL_N_THRESHOLD),
                }
                any_live = True
            else:
                row["peer"] = None
                row["peer_note"] = (f"substrate miss — static threshold governs "
                                    f"({last_reason})" if last_reason
                                    else "cohort resolved but carried no band for this quarter")
                if last_reason:
                    reasons.append(candidates[0][0])
        except BandsError as e:
            row["peer"] = None
            row["peer_note"] = f"substrate miss — static threshold governs ({str(e)[:60]})"
            if metric: reasons.append(metric)
        except Exception as e:
            row["peer"] = None
            row["peer_note"] = f"substrate unreachable — static threshold governs"
            if metric: reasons.append(metric)
        rows.append(row)
    if any_live:
        prov = (f"asset-band peer cohort '{band}' \u2014 percentiles per metric at the vintage "
                f"shown; distributions carry n per point (substrate floor n=3, small-n labeled "
                f"not suppressed). Selection is pre-registered by projected asset size, not "
                f"hand-picked. Placement is consistency evidence, not support. Provisional tier: "
                f"national peer-group reconciliation pending \u2014 not yet certified.")
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


# --------------------------------------------------------------------------
# F-121 flag peer-annotation (post-pass over challenge_config output).
# For each emitted flag whose id maps to a substrate metric that RESOLVES,
# append a peer-percentile clause to its text. Fail-closed: an unresolved
# metric leaves the flag's static text untouched. Never changes WHICH flags
# fire (that stays challenge_config's deterministic static logic) — only
# enriches the message of ones that already fired with peer evidence.
# --------------------------------------------------------------------------

def _corridor_to_pctlabel(pos):
    """Human 'pNN of peers' phrasing from a corridor position."""
    return {
        "below p10": "below the 10th percentile of peers",
        "p10-p25":   "in the 10th-25th percentile of peers",
        "p25-p50":   "in the 25th-50th percentile of peers",
        "p50-p75":   "in the 50th-75th percentile of peers",
        "p75-p90":   "in the 75th-90th percentile of peers",
        "above p90": "above the 90th percentile of peers",
    }.get(pos, pos)


# How to pull the client value each flag should be placed at, from the config.
# Mirrors the value challenge_config already tested, so placement is consistent
# with why the flag fired. Returns a float or None (skip annotation).
def _flag_client_value(flag, cfg):
    from .engine_q_a import rate_fn, _prod_rate
    a = cfg.get("assumptions", {})
    rate = rate_fn(a.get("rate_path_q"), a.get("rate_path_longer_run"))
    lend = a.get("lending_products") or []
    dep = a.get("deposit_products") or []
    fid = flag.get("id", "")
    # deposit-cost family: balance-weighted Q1 deposit rate (%)
    if fid in ("FUND-HOT", "FUND-DDA"):
        wd = sum((p.get("opening_balance") or 0) for p in dep)
        if wd <= 0:
            return None
        wc = sum((p.get("opening_balance") or 0) * _prod_rate(p, 1, rate) for p in dep) / wd
        return wc * 100.0
    # loan-yield family: balance-weighted Q1 loan yield (%)
    if fid in ("PRICE-USURY", "PRICE-LOWYIELD", "COUPLED-02"):
        wl = sum((p.get("opening_balance") or 0) for p in lend)
        if wl <= 0:
            return None
        wy = sum((p.get("opening_balance") or 0) * _prod_rate(p, 1, rate) for p in lend) / wl
        return wy * 100.0
    # reserve/loans: balance-weighted reserve rate (%)
    if fid == "RES-THIN":
        wl = sum((p.get("opening_balance") or 0) for p in lend)
        if wl <= 0:
            return None
        wr = sum((p.get("opening_balance") or 0) * (p.get("reserve_rate_pct_bal") or 0) for p in lend) / wl
        return wr * 100.0
    # provision/avg assets proxy: balance-weighted provision rate (%)
    if fid == "PROV-BELOW-CO":
        wl = sum((p.get("opening_balance") or 0) for p in lend)
        if wl <= 0:
            return None
        wp = sum((p.get("opening_balance") or 0) * (p.get("provision_rate_ann") or 0) for p in lend) / wl
        return wp * 100.0
    # deposit growth vs sustainable-growth band (%)
    if fid == "FUND-GROWTH":
        wd = sum((p.get("opening_balance") or 0) for p in dep)
        if wd <= 0:
            return None
        wg = sum((p.get("opening_balance") or 0) * (p.get("growth_q") or 0) for p in dep) / wd
        return wg * 100.0
    # charge-off vs NPL proxy: balance-weighted charge-off (%)
    if fid in ("BAND-CO-HI", "BAND-CO-LO"):
        wl = sum((p.get("opening_balance") or 0) for p in lend)
        if wl <= 0:
            return None
        wco = sum((p.get("opening_balance") or 0) * (p.get("charge_off_ann") or 0) for p in lend) / wl
        return wco * 100.0
    return None


def peer_annotate(flags, cfg, cohort="broad"):
    """Enrich already-fired flags with peer-percentile evidence where the metric
    resolves. Returns a NEW list (originals untouched). Fail-closed everywhere."""
    out = []
    for flag in flags:
        f = dict(flag)
        fid = f.get("id", "")
        # map both the exact id and the two-part prefix (BAND-CO-HI -> BAND-CO)
        parts = fid.split("-")
        two = "-".join(parts[:2]) if len(parts) >= 2 else fid
        mapped = FLAG_METRIC_MAP.get(fid) or FLAG_METRIC_MAP.get(two)
        candidates = _resolve_mapped(mapped)
        if not candidates:
            out.append(f); continue
        val = _flag_client_value(flag, cfg)
        if val is None:
            out.append(f); continue
        # try each candidate in preference order — the first that resolves wins, so a
        # flag auto-upgrades from a proxy to the real metric the moment it lands.
        band, metric, tier = None, None, None
        for cand_metric, cand_tier in candidates:
            try:
                parsed, source = get_bands(cand_metric, cohort)
            except Exception:
                continue
            b = parsed["bands"][-1] if parsed.get("bands") else None
            if b:
                band, metric, tier = b, cand_metric, cand_tier
                break
        if band is None:
            out.append(f); continue           # no candidate resolved -> static text stands
        pos = corridor_position(val, band)
        label = _corridor_to_pctlabel(pos)
        proxy = ""
        if tier == "proxy_growth":
            proxy = " (vs sustainable-growth band \u2014 a capacity proxy)"
        elif tier == "proxy_credit":
            proxy = " (vs NPL band \u2014 a credit-quality proxy, not net charge-offs)"
        n = band.get("n")
        ntxt = f", n={n}" if n else ""
        # vintage is the band's OWN quarter (honest: what the data actually is),
        # not a hardcoded tier label. tier only distinguishes clean vs proxy.
        real_q = band.get("quarter") or "latest"
        f["peer"] = {"metric": metric, "position": pos, "band_metric": metric,
                     "p50": band.get("p50"), "n": n, "tier": tier,
                     "vintage": real_q + (" (proxy)" if tier.startswith("proxy") else "")}
        f["text"] = f["text"] + f" Against real peers, this sits {label}{proxy}{ntxt}."
        out.append(f)
    return out
