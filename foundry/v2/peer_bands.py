"""Peer percentile bands — the substrate consumption path (F-121).

The CharterIQ substrate computes per-quarter percentile bands (p10/p25/p50/
p75/p90) over identity-gated Call Report values, EXTRACTED RAW: no winsorizing,
no outlier trimming (verified against Klaros published values to two decimals,
e.g. a trust company's tier1_ratio of 74283.33%). Extreme tails are real
institutions with near-nil denominators (trusts, special-purpose charters),
not corrupt values — so the remedy for a distorted tail is COHORT HYGIENE
(exclude non-lending peers), never capping the raw data. Bands arrive with
provenance (basis, certified, computed_at) and n per point. Until the live
endpoint ships, checked-in fixtures — REAL substrate output, provisional until
Deliverable D — serve the same shape; the response's `source` field says which.

Small-n honesty: curated cohorts (Konrad bands, 6-10 named certs) live near the
degenerate-percentile regime — with n=3, p10 approximates the minimum and p90
the maximum, and the "distribution" is really a range. SMALL_N_THRESHOLD marks
where the UI must say so.
"""
import os, json, re

SMALL_N_THRESHOLD = 8
FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "..", "fixtures", "substrate")
POINTS = ("p10", "p25", "p50", "p75", "p90")


class BandsError(ValueError):
    pass


def parse_bands_response(doc):
    """Fail-closed validation of a substrate bands response."""
    errs = []
    for k in ("metric", "cohort", "provenance", "bands"):
        if k not in doc:
            errs.append(f"missing key '{k}'")
    if errs:
        raise BandsError("; ".join(errs))
    prov = doc["provenance"]
    for k in ("basis", "certified", "computed_at"):
        if k not in prov:
            errs.append(f"provenance missing '{k}'")
    if not isinstance(doc["bands"], list) or not doc["bands"]:
        errs.append("bands must be a non-empty list")
    for b in doc.get("bands", []):
        q = b.get("quarter", "?")
        if not all(p in b for p in POINTS):
            errs.append(f"{q}: missing percentile points")
            continue
        vals = [b[p] for p in POINTS]
        if any(vals[i] > vals[i + 1] for i in range(len(vals) - 1)):
            errs.append(f"{q}: percentiles not monotonic")
        if not isinstance(b.get("n"), int) or b["n"] < 1:
            errs.append(f"{q}: n missing or < 1")
    if errs:
        raise BandsError("; ".join(errs))
    return {"metric": doc["metric"], "cohort": doc["cohort"], "provenance": prov,
            "bands": doc["bands"],
            "small_n": any(b["n"] < SMALL_N_THRESHOLD for b in doc["bands"])}


def corridor_position(value, band):
    """Which corridor a modeled value occupies for one quarter's band."""
    if value < band["p10"]: return "below p10"
    if value < band["p25"]: return "p10-p25"
    if value < band["p50"]: return "p25-p50"
    if value < band["p75"]: return "p50-p75"
    if value < band["p90"]: return "p75-p90"
    return "above p90"


def _cohort_key(cohort):
    if cohort == "broad":
        return "broad"
    if isinstance(cohort, str):
        return cohort  # a named cohort (asset band / stored group_id) — verbatim
    return "curated_" + "_".join(str(c) for c in sorted(int(x) for x in cohort))


# Stored cohorts live as group_id rows in peer_percentiles and are read by the
# ONE database connection (CHARTERIQ_DATABASE_URL) that every other feature uses.
# The only thing the database cannot serve is an ARBITRARY cert-list cohort (the
# Konrad shape): the table holds no precomputed row for an ad-hoc set of banks,
# so those — and only those — go to the research HTTP endpoint when configured.
# That is the entire, one-sentence reason the HTTP path still exists.
_STORED_COHORTS = {"broad", "all_universe", "under_200M", "200M_500M",
                   "500M_2B", "2B_10B", "10B_50B", "over_50B", "all_failed",
                   "all_sponsors"}


def _is_stored(cohort):
    return isinstance(cohort, str) and cohort in _STORED_COHORTS


def _db_bands(metric, cohort):
    """Read a stored cohort's bands from the peer_percentiles table via the single
    CHARTERIQ_DATABASE_URL client. Returns parsed dict or None (not configured /
    no rows). group_id maps 'broad' -> 'all_universe'."""
    from foundry.charteriq_client import CharterIQClient
    cl = CharterIQClient()
    if not cl.configured():
        return None
    gid = "all_universe" if cohort == "broad" else cohort
    # peer_percentiles is a PER-BANK table (~18M rows): every bank in a group
    # carries the SAME group distribution, so one row per (year, quarter) is the
    # whole band. DISTINCT ON collapses the thousands of identical rows per
    # quarter to one each — mirroring the proven LIMIT-1 pattern in
    # get_peer_percentiles, but across the quarter series. Without this the query
    # scans and sorts millions of duplicate rows and hangs the request.
    try:
        rows = cl._run(
            "SELECT DISTINCT ON (year, quarter) "
            "year, quarter, peer_p10, peer_p25, peer_p50, peer_p75, peer_p90, peer_count "
            "FROM peer_percentiles WHERE metric_name = %s AND group_id = %s "
            "ORDER BY year, quarter", (metric, gid))
    except Exception:
        # timeout, connection drop, or query error -> treat as 'no rows' so the
        # caller degrades to its honest fallback (refusal / static threshold),
        # never a 500 that hangs the page. The failure is real; the response is
        # graceful.
        return None
    if not rows:
        return None
    bands = [{"quarter": f"{r[0]}Q{r[1]}", "p10": float(r[2]), "p25": float(r[3]),
              "p50": float(r[4]), "p75": float(r[5]), "p90": float(r[6]),
              "n": int(r[7]) if r[7] is not None else None} for r in rows]
    return {"metric": metric, "cohort": cohort,
            "provenance": {"basis": "identity-gated", "certified": False,
                           "computed_at": None,
                           "tail_policy": "extract-raw (no winsorizing); extreme "
                           "tails are real near-nil-denominator filers, addressed by "
                           "cohort hygiene not capping"},
            "bands": bands}


def get_bands(metric, cohort):
    """Resolve percentile bands, preferring the ONE database connection.

    Order: (1) stored cohort -> CHARTERIQ_DATABASE_URL (SQL, the same client every
    other feature uses); (2) arbitrary cert-list cohort -> the research HTTP
    endpoint (CHARTERIQ_SUBSTRATE_URL) IF set, since the table has no ad-hoc row;
    (3) checked-in provisional fixtures. Returns (parsed, source).
    """
    # (1) stored cohorts: the database serves these directly
    if _is_stored(cohort):
        parsed = _db_bands(metric, cohort)
        if parsed is not None:
            return parsed, "substrate (db)"
    # (2) arbitrary cert-list cohort: only the research endpoint can compute an
    #     ad-hoc distribution the table does not precompute
    else:
        base = os.environ.get("CHARTERIQ_SUBSTRATE_URL")
        if base:
            import urllib.request
            payload = json.dumps({"metric": metric, "cohort": cohort,
                                   "points": [10, 25, 50, 75, 90]}).encode()
            req = urllib.request.Request(base.rstrip("/") + "/api/v1/research/percentile-bands",
                                          data=payload, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=20) as r:
                return parse_bands_response(json.loads(r.read().decode())), "substrate (research endpoint)"
    # (3) fixtures — OPT-IN ONLY, never a silent production fallback.
    # A silent synthetic fallback is a landmine: a coverage gap then looks
    # identical to real data, and the system's honesty depends on someone
    # noticing a tell. So: if a database connection EXISTS, a miss is a
    # REFUSAL, not a substitution — the caller learns the truth (no rows for
    # this metric/cohort) instead of receiving fabricated numbers. Fixtures
    # are served only when explicitly allowed (FOUNDRY_ALLOW_FIXTURE_BANDS=1),
    # for offline development, and never when a live DB is configured.
    db_configured = bool(os.environ.get("CHARTERIQ_DATABASE_URL"))
    allow_fixtures = os.environ.get("FOUNDRY_ALLOW_FIXTURE_BANDS") == "1"
    if db_configured and not allow_fixtures:
        raise BandsError(
            f"no substrate rows for metric '{metric}' / cohort '{cohort}'. "
            "The database is connected but has no distribution for this "
            "metric/cohort (a real coverage gap \u2014 e.g. a funding metric "
            "pending M6a, or a cohort with no filed peers). Refusing rather "
            "than serving synthetic fixture data. To use fixtures for offline "
            "testing, set FOUNDRY_ALLOW_FIXTURE_BANDS=1 (never in production).")
    if not (db_configured or allow_fixtures):
        # fully offline (no DB, no explicit opt-in): fixtures are the only
        # possible source, but they are still labelled provisional loudly.
        pass
    metric_safe = re.sub(r"[^a-z0-9_]", "", str(metric).lower())
    path = os.path.join(FIXTURE_DIR, f"bands_{metric_safe}_{_cohort_key(cohort)}.json")
    if not os.path.exists(path):
        raise BandsError(
            f"bands unavailable for metric '{metric}' / this cohort \u2014 no "
            "database rows and no provisional fixture. This is an honest gap, "
            "not an error to paper over.")
    with open(path, encoding="utf-8") as fh:
        return parse_bands_response(json.load(fh)), "fixture (PROVISIONAL \u2014 NOT LIVE DATA)"
