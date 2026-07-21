"""Peer percentile bands — the substrate consumption path (F-121).

The CharterIQ substrate computes per-quarter percentile bands (p10/p25/p50/
p75/p90) over identity-gated Call Report values: corrupt filer values were
quarantined at ingest by per-family reconciliation gates, so exclusion happens
before a value exists, not by post-hoc flag filtering. Bands arrive with
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
    return "curated_" + "_".join(str(c) for c in sorted(int(x) for x in cohort))


def get_bands(metric, cohort):
    """Live substrate when CHARTERIQ_SUBSTRATE_URL is set; fixtures otherwise.
    Returns (parsed, source) or raises BandsError with an honest reason."""
    base = os.environ.get("CHARTERIQ_SUBSTRATE_URL")
    if base:
        import urllib.request
        payload = json.dumps({"metric": metric, "cohort": cohort,
                               "points": [10, 25, 50, 75, 90]}).encode()
        req = urllib.request.Request(base.rstrip("/") + "/api/v1/research/percentile-bands",
                                      data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=20) as r:
            return parse_bands_response(json.loads(r.read().decode())), "substrate"
    metric_safe = re.sub(r"[^a-z0-9_]", "", str(metric).lower())
    path = os.path.join(FIXTURE_DIR, f"bands_{metric_safe}_{_cohort_key(cohort)}.json")
    if not os.path.exists(path):
        raise BandsError(
            f"bands unavailable for metric '{metric}' / this cohort — the substrate "
            "endpoint is pending; provisional fixtures cover roa (broad and the "
            "628/3511/7213 curated example)")
    with open(path, encoding="utf-8") as fh:
        return parse_bands_response(json.load(fh)), "fixture (provisional)"
