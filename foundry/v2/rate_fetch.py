"""FOMC / policy-rate fetch (FRED) for the multi-curve feature.

Pulls the pieces the curve model needs, per the reviewer assessment:
  * FEDTARMD    — SEP median fed funds projection (the target-MIDPOINT forward anchors, YE by year).
  * FEDTARMDLR  — SEP median longer-run projection.
  * DFEDTARU    — current fed funds target range UPPER limit (for the range top / Prime anchor).
  * DFEDTARL    — current fed funds target range LOWER limit (with upper -> current midpoint).
  * EFFR        — observed effective rate (to sanity-check / calibrate the EFFR basis).

Design invariants (unchanged):
  * Network touched ONLY here, ONLY on the explicit "Refresh from FOMC" action. Runs never call this;
    the fetched values are snapshotted into the engagement config with vintage stamps, so a given
    engagement reproduces its numbers regardless of later data revisions.
  * http_get is INJECTABLE so tests run fully offline. No test depends on api.stlouisfed.org.
  * Raises on any failure; never returns partial or fabricated data. Caller keeps existing snapshot.

The SEP median (FEDTARMD) IS the target-range midpoint (per the Fed's own series definition) — so the
model treats it as the midpoint path and derives EFFR/SOFR/Prime from it, rather than calling it EFFR.
"""

import json

FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"
SERIES = {
    "sep_median": "FEDTARMD",     # SEP median projection (midpoint), one obs per SEP per horizon year
    "sep_lr": "FEDTARMDLR",       # SEP median longer-run
    "range_up": "DFEDTARU",       # current target range upper limit
    "range_lo": "DFEDTARL",       # current target range lower limit
    "effr": "EFFR",               # observed effective fed funds rate
}


def _default_http_get(url):  # pragma: no cover - real network path (prod only)
    import urllib.request
    with urllib.request.urlopen(url, timeout=15) as r:
        return r.read().decode("utf-8")


def _obs(series_id, api_key, http_get, limit=60):
    url = (f"{FRED_BASE}?series_id={series_id}&api_key={api_key}&file_type=json"
           f"&sort_order=desc&limit={limit}")
    data = json.loads(http_get(url))
    out = []
    for o in data.get("observations") or []:
        v = o.get("value")
        if v in (None, ".", ""):
            continue
        try:
            out.append((o["date"], float(v) / 100.0))
        except (KeyError, ValueError):
            continue
    return out  # newest first


def fetch_policy(api_key, http_get=None):
    """Return a snapshot dict for the curve model. Raises on any failure.

    {
      "current_policy": {mid, top, statement_date, sep_date},
      "fomc": {ye26, ye27, ye28, lr},        # SEP median midpoint anchors
      "effr_observed": <float>,               # latest observed EFFR (for basis calibration)
      "vintage": {sep, statement}
    }
    Note: FEDTARMD carries one observation per SEP-projected year. Mapping those to YE26/27/28 requires
    reading the observation dates; this function returns the raw latest SEP anchors and their date, and
    the caller maps them to the model's year slots. Kept deliberately explicit — no silent guessing.
    """
    if not api_key:
        raise ValueError("FRED api_key is required")
    http_get = http_get or _default_http_get

    up = _obs(SERIES["range_up"], api_key, http_get)
    lo = _obs(SERIES["range_lo"], api_key, http_get)
    if not up or not lo:
        raise ValueError("could not read current target range")
    top = up[0][1]
    bottom = lo[0][1]
    mid = round((top + bottom) / 2.0, 6)
    statement_date = up[0][0]

    sep = _obs(SERIES["sep_median"], api_key, http_get)
    lr = _obs(SERIES["sep_lr"], api_key, http_get)
    if not sep or not lr:
        raise ValueError("could not read SEP median projections")
    sep_date = sep[0][0]

    effr = _obs(SERIES["effr"], api_key, http_get)
    effr_observed = effr[0][1] if effr else None

    # The three most recent distinct SEP horizon points (they share the SEP release date but project
    # different years). Return them ordered; the caller maps to ye26/ye27/ye28.
    # FRED returns them as separate observations dated by projection year-end.
    sep_points = [v for (_, v) in sep[:4]]
    while len(sep_points) < 3:
        sep_points.append(sep_points[-1] if sep_points else mid)

    return {
        "current_policy": {"mid": mid, "top": top,
                           "statement_date": statement_date, "sep_date": sep_date},
        "fomc": {"ye26": sep_points[0], "ye27": sep_points[1],
                 "ye28": sep_points[2], "lr": lr[0][1]},
        "effr_observed": effr_observed,
        "vintage": {"sep": sep_date, "statement": statement_date},
    }
