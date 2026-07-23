"""Charter-filtered peer cohort for examiner-facing bands.

Per CHARTER_FILTERED_COHORT_SPEC (2026-07-21, Klaros-verified): five of six
asset bands are examiner-defensible as-is; the under_200M band's tail is lifted
by a DENSE CLUSTER of near-nil-denominator filers (trust companies with near-nil
RWA, special-purpose charters). Those values are REAL and Klaros-verified — the
fix is cohort hygiene (exclude non-lending peers), never winsorization.

Two independent, deterministic predicates (spec §A, §B):
  A. Denominator floor (mechanical, metric-agnostic): a bank-quarter qualifies
     only if the ratio's denominator clears a floor (REG_PARAMS.cohort_hygiene).
     Targets the MECHANISM (near-nil denominator), so it catches de novos,
     special-purpose, and any future thin filer uniformly.
  B. Charter-type exclusion (semantic, persistent class): trust companies carry
     structurally near-nil RWA PERMANENTLY (custody/fiduciary, not lending), so a
     first-quarters floor won't catch them (HSBC Trust appears at 74283%, 54082%,
     39693% across many years). Exclude by charter_type where the substrate
     carries it, plus a small curated exclusion cert-list.

Output is a FILTERED CERT LIST passed to /percentile-bands as an arbitrary cohort
(the existing arbitrary-cohort path — no new endpoint). Raw values stay raw; only
the peer group is refined. This never edits the substrate.
"""
from .regparams import REG_PARAMS

# Curated exclusion list: known trust / special-purpose charters that are not
# lending-bank peers. Kept small and documentable; extend as identified. Each
# entry carries a reason so the exclusion is auditable, never silent.
# (cert -> reason). The spec's exemplar: HSBC Trust Delaware NA.
TRUST_SPECIAL_PURPOSE_EXCLUSIONS = {
    # cert: reason  — populated as charters are identified; charter_type is the
    # primary filter, this list catches those the substrate doesn't tag.
}

# charter_type values (where the substrate carries them) that are not lending peers
NON_LENDING_CHARTER_TYPES = {"trust", "trust company", "special purpose",
                              "nondepository trust", "credit card bank"}


def _clears_denominator_floor(metric, rec):
    """Predicate 1 — denominator floor. rec carries per-bank-quarter denominators:
    rwa_000s (from the metrics table's rwa_dollars), assets_mm. Revenue is NOT stored
    as gross dollars, so efficiency uses the ratio-ceiling guard (predicate 2) instead
    of a revenue floor. Returns (qualifies, reason_if_not)."""
    H = REG_PARAMS["cohort_hygiene"]
    risk_based = metric in ("tier1_ratio", "cet1_ratio", "total_rbc_ratio")
    if risk_based:
        rwa = rec.get("rwa_000s")
        if rwa is None:
            # CBLR electors don't report RWA by design — they're correctly absent from
            # a risk-based-ratio cohort (they file leverage only). Treat missing RWA as
            # "not a risk-based-ratio peer", an honest exclusion, not an error.
            return False, "no RWA reported (CBLR elector — not a risk-based-ratio peer)"
        if rwa < H["rwa_floor_000s"]:
            return False, f"RWA {rwa} < floor {H['rwa_floor_000s']} ($000s)"
        return True, None
    if metric == "leverage_ratio":
        a = rec.get("assets_mm")
        if a is None:
            return False, "no asset denominator reported"
        if a < H["assets_floor_mm"]:
            return False, f"assets {a}mm < floor {H['assets_floor_mm']}mm"
        return True, None
    # efficiency and other revenue-scaled ratios: NO revenue floor (revenue dollars
    # not cleanly stored). The ratio-ceiling guard (predicate 2) handles these — it
    # needs no denominator. So the floor passes here; the ceiling does the work.
    if metric == "efficiency_ratio":
        return True, None
    # roa/nim and others: asset-scaled, use the asset floor as a conservative default
    a = rec.get("assets_mm")
    if a is not None and a < H["assets_floor_mm"]:
        return False, f"assets {a}mm < floor {H['assets_floor_mm']}mm"
    return True, None


def _clears_ratio_ceiling(metric, rec):
    """Predicate 2 — ratio-ceiling guard (denominator-agnostic). A near-nil-denominator
    artifact is self-identifying by its OUTPUT: a 54,700% efficiency ratio or a 74,283%
    tier1 ratio is obviously an artifact, no denominator lookup needed. Excludes a
    bank-quarter whose ratio VALUE exceeds the per-metric sanity ceiling. This catches
    artifacts regardless of WHICH denominator went to zero, and is the sole clean guard
    for efficiency (whose revenue denominator isn't stored). rec must carry 'value' (the
    bank's ratio for this metric). Returns (qualifies, reason_if_not)."""
    ceilings = REG_PARAMS["cohort_hygiene"].get("ratio_ceilings", {})
    ceiling = ceilings.get(metric, REG_PARAMS["cohort_hygiene"].get("ratio_ceiling_default"))
    if ceiling is None:
        return True, None                      # no ceiling defined for this metric (roa/nim)
    v = rec.get("value")
    if v is None:
        return True, None                      # no value to test — floor/charter handle it
    if v > ceiling:
        return False, f"{metric}={v:g} exceeds sanity ceiling {ceiling:g} (near-nil-denominator artifact)"
    return True, None


def _is_non_lending_charter(rec):
    ct = (rec.get("charter_type") or "").strip().lower()
    if ct in NON_LENDING_CHARTER_TYPES:
        return True, f"charter_type '{ct}' is not a lending peer"
    if rec.get("cert") in TRUST_SPECIAL_PURPOSE_EXCLUSIONS:
        return True, TRUST_SPECIAL_PURPOSE_EXCLUSIONS[rec["cert"]]
    return False, None


def filter_cohort(members, metric, apply_floor=True, apply_charter=True, apply_ceiling=True):
    """Filter a cohort's member records to lending-bank peers for `metric`, composing
    three deterministic predicates (spec §A/§B plus the ratio-ceiling):
      1. charter-type exclusion (trust/special-purpose), where charter_type is populated
      2. denominator floor (RWA >= $25M for risk-based; assets for leverage/asset-scaled)
      3. ratio-ceiling guard (denominator-agnostic artifact exclusion by output value)

    members: list of dicts, each carrying at least 'cert', the denominators available
             ('rwa_000s', 'assets_mm', 'charter_type'), and 'value' (the bank's ratio
             for this metric, for the ceiling guard).
    Returns (kept_certs, dropped) where dropped is a list of (cert, reason) — every
    exclusion auditable, never silent (spec: 'nothing hidden').
    """
    kept, dropped = [], []
    for rec in members:
        cert = rec.get("cert")
        if apply_charter:
            non_lending, reason = _is_non_lending_charter(rec)
            if non_lending:
                dropped.append((cert, reason)); continue
        if apply_floor:
            ok, reason = _clears_denominator_floor(metric, rec)
            if not ok:
                dropped.append((cert, reason)); continue
        if apply_ceiling:
            ok, reason = _clears_ratio_ceiling(metric, rec)
            if not ok:
                dropped.append((cert, reason)); continue
        kept.append(cert)
    return kept, dropped


def cohort_provenance(metric, band, kept_n, dropped):
    """Auditable provenance for the filtered cohort — states what was excluded and
    why, so an examiner sees the refinement, not a silent narrowing."""
    floor = REG_PARAMS["cohort_hygiene"]
    return {
        "base_band": band,
        "metric": metric,
        "lending_peers_kept": kept_n,
        "excluded_count": len(dropped),
        "exclusions": [{"cert": c, "reason": r} for c, r in dropped],
        "policy": ("examiner-facing lending-bank cohort: near-nil-denominator "
                   "and non-lending charters excluded so the comparison means "
                   "'banks like this applicant', not 'every filer in the band'. "
                   "Raw substrate values unchanged (extract-raw); this refines "
                   "the peer GROUP, not the data."),
        "floors": {"rwa_floor_000s": floor["rwa_floor_000s"],
                    "assets_floor_mm": floor["assets_floor_mm"]},
        "ratio_ceilings": floor.get("ratio_ceilings", {}),
        "predicates": ("charter-type exclusion (where populated) + RWA/asset denominator "
                       "floor + denominator-agnostic ratio ceiling (an out-of-range ratio "
                       "is self-identifying as a near-nil-denominator artifact, so revenue "
                       "need not be stored to exclude it)"),
        "spec": floor["spec"],
    }
