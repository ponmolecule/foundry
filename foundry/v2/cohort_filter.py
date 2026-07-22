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
    """rec is a per-bank-quarter dict carrying denominators (rwa_dollars in $000s,
    asset_size_mm, revenue in $000s). Returns (qualifies, reason_if_not)."""
    H = REG_PARAMS["cohort_hygiene"]
    risk_based = metric in ("tier1_ratio", "cet1_ratio", "total_rbc_ratio")
    if risk_based:
        rwa = rec.get("rwa_000s")
        if rwa is None:
            return False, "no RWA denominator reported"
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
    if metric == "efficiency_ratio":
        rev = rec.get("revenue_000s")
        if rev is None or rev <= H["revenue_floor_000s"]:
            return False, "revenue base below floor"
        return True, None
    # roa/nim and others: asset-scaled, use the asset floor as a conservative default
    a = rec.get("assets_mm")
    if a is not None and a < H["assets_floor_mm"]:
        return False, f"assets {a}mm < floor {H['assets_floor_mm']}mm"
    return True, None


def _is_non_lending_charter(rec):
    ct = (rec.get("charter_type") or "").strip().lower()
    if ct in NON_LENDING_CHARTER_TYPES:
        return True, f"charter_type '{ct}' is not a lending peer"
    if rec.get("cert") in TRUST_SPECIAL_PURPOSE_EXCLUSIONS:
        return True, TRUST_SPECIAL_PURPOSE_EXCLUSIONS[rec["cert"]]
    return False, None


def filter_cohort(members, metric, apply_floor=True, apply_charter=True):
    """Filter a cohort's member records to lending-bank peers for `metric`.

    members: list of dicts, each carrying at least 'cert' and the denominators
             ('rwa_000s', 'assets_mm', 'revenue_000s', 'charter_type') as available.
    Returns (kept_certs, dropped) where dropped is a list of (cert, reason) — the
    exclusions are always auditable, never silent (spec: 'nothing hidden').
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
        "spec": floor["spec"],
    }
