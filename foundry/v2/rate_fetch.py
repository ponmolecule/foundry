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
    """Return an auditable policy/SEP snapshot. Raises on any failure.

    The important distinction is explicit:
      * `observation_date` is the FRED observation date of the current target range;
        it is NOT asserted to be the FOMC statement/release date;
      * SEP projection observations are *target dates*, not SEP release dates;
      * `fomc.anchors` therefore stores dated year-end projection anchors;
      * `retrieved_at` records when this snapshot was pulled;
      * `source_vintage` is left null unless an authoritative SEP release date is supplied
        elsewhere. We do not mislabel a projection target date as a source vintage.

    Legacy ye26/ye27/ye28 slots are intentionally retired from the canonical payload. The
    caller should use the dated `anchors` mapping and the engagement's actual calendar.
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
    observation_date = up[0][0]

    sep = _obs(SERIES["sep_median"], api_key, http_get)
    lr = _obs(SERIES["sep_lr"], api_key, http_get)
    if not sep or not lr:
        raise ValueError("could not read SEP median projections")

    # FEDTARMD observations are dated by the PROJECTION TARGET YEAR. Preserve those actual
    # dates instead of assigning them to positional labels (YE26/YE27/YE28), which both caused
    # the prior reversal bug and made the structure stale as calendar years roll forward.
    anchors = {}
    for d, v in sep:
        try:
            y = int(str(d)[:4])
        except Exception:
            continue
        # One anchor per target year; _obs is newest-first, so first valid observation wins.
        anchors.setdefault(f"{y:04d}-12-31", v)
    if not anchors:
        raise ValueError("SEP median series returned no dated projection anchors")

    effr = _obs(SERIES["effr"], api_key, http_get)
    effr_observed = effr[0][1] if effr else None

    import datetime as _dt
    retrieved = _dt.date.today().isoformat()
    return {
        "current_policy": {
            "mid": mid, "top": top, "bottom": bottom,
            "observation_date": observation_date,
            "statement_date": None,
        },
        "fomc": {
            "anchors": dict(sorted(anchors.items())),
            "lr": lr[0][1],
            # FRED's target-year observations do not identify the SEP publication date.
            "source_vintage": None,
        },
        "effr_observed": effr_observed,
        "retrieved_at": retrieved,
        "vintage": {"policy_observation": observation_date, "statement": None, "sep": None},
    }
