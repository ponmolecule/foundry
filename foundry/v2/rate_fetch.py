"""Reference-rate curve fetch (FRED) for the multi-curve feature.

Design invariants (do NOT weaken):
  * The network is touched ONLY here, and ONLY on an explicit user action ("Update all curves").
    Runs never call this — curves are pinned into the config with a vintage stamp, so a given
    engagement at a given vintage always reproduces the same run (deterministic on a vintage basis).
  * The HTTP getter is injectable (`http_get`) so unit/golden tests run fully offline with a mock.
    No test may depend on api.stlouisfed.org.
  * On any failure the caller keeps the existing pinned curves — this module raises, it never
    returns fabricated or partial data.

FRED series used:
  * SOFR   — Secured Overnight Financing Rate (observed).
  * EFFR   — Effective Federal Funds Rate (observed, NY Fed volume-weighted median).
  * DPRIME — Bank Prime Loan Rate (WSJ convention, observed).
Each is an observed rate (per the standing correction: EFFR/Prime are NOT derived from a formula).
"""

import json
import datetime as _dt

FRED_SERIES = {"sofr": "SOFR", "effr": "EFFR", "prime": "DPRIME"}
FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"


def _default_http_get(url):  # pragma: no cover - real network path, exercised only in prod
    import urllib.request
    with urllib.request.urlopen(url, timeout=15) as r:
        return r.read().decode("utf-8")


def _observations(series_id, api_key, http_get):
    """Return the most recent non-missing observations for a FRED series (desc, small window)."""
    url = (f"{FRED_BASE}?series_id={series_id}&api_key={api_key}&file_type=json"
           f"&sort_order=desc&limit=400")
    raw = http_get(url)
    data = json.loads(raw)
    obs = data.get("observations") or []
    out = []
    for o in obs:
        v = o.get("value")
        if v in (None, ".", ""):
            continue
        try:
            out.append((o["date"], float(v) / 100.0))  # FRED gives percent; store decimal
        except (KeyError, ValueError):
            continue
    return out  # newest first


def _quarterize(obs):
    """Collapse daily observations into a flat 12-quarter forward path + longer-run.

    A de novo forward projection off a spot rate: FRED gives the CURRENT observed level; we hold it
    flat across the 12-quarter horizon (the engine's own glide handles beyond Q12). This is a
    deliberate simplification — the observed spot is the honest 'current vintage' anchor; the user
    can then edit the path by hand if they want a shaped forecast. longer_run = same spot.
    """
    if not obs:
        raise ValueError("no observations")
    spot = obs[0][1]
    return [spot] * 12, spot


def fetch_curves(api_key, http_get=None, today=None):
    """Fetch all three curves. Returns {curve: {vintage, path_q[12], longer_run, edited:False}}.

    Raises on any failure (missing key, network error, empty series) — never returns partial or
    fabricated data. The caller keeps existing pinned curves on exception.
    """
    if not api_key:
        raise ValueError("FRED api_key is required")
    http_get = http_get or _default_http_get
    today = today or _dt.date.today().isoformat()
    out = {}
    for curve, series_id in FRED_SERIES.items():
        obs = _observations(series_id, api_key, http_get)
        path_q, lr = _quarterize(obs)
        latest_date = obs[0][0]  # the vintage of the newest observation
        out[curve] = {
            "vintage": f"FRED {series_id} {latest_date}",
            "path_q": path_q,
            "longer_run": lr,
            "edited": False,
            "fetched": today,
        }
    return out
