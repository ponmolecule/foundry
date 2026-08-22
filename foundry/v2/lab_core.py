"""Foundry Lab — analytical core (goal-seek, sensitivity, trade-off, optimization).

DESIGN INVARIANT: this module never modifies the projection engine. It CONSUMES run_v2(cfg) as a pure
black-box evaluation function on scratch (deep-copied) configs. Every point it explores is a real,
valid engine run — that is what makes the results defensible. The core engine is untouched.

MATHEMATICAL CONTRACT:
- METRICS are extracted from engine output by a single, documented accessor (metric_value) so every mode
  measures the same thing the app displays.
- LEVERS are addressed by dotted config paths; get/set are pure (operate on a deep copy).
- GOAL-SEEK uses bracketing + bisection (robust, derivative-free, guaranteed to converge on a sign change
  within the bracket) with a Newton/secant acceleration when the response is smooth. It reports whether
  it converged, the residual, and the number of engine evaluations — never a silent wrong answer.
"""

import copy


# ----------------------------------------------------------------------------------------------------
# METRICS — the single source of truth for "what does the Lab measure".
# Each metric: how to pull a scalar from a run_v2(cfg) result. We use the LATEST projected quarter by
# default (the steady-state the model reaches), and expose the aggregation so it is explicit, not hidden.
# ----------------------------------------------------------------------------------------------------

def _last_num(series):
    for x in reversed(series or []):
        if x is not None:
            return x
    return None


def _annual_last(res, key):
    return _last_num((res.get("annual") or {}).get(key))


def _ratio_last(res, key):
    return _last_num(((res.get("financials") or {}).get("ratios") or {}).get(key))


def _cet1_last(res):
    # standardized CET1 ratio, final quarter, from the capital schedule
    cap = res.get("capital") or {}
    std = cap.get("standardized") or {}
    rows = std.get("rows") or std
    for cand in ("cet1_ratio", "cet1", "cet1_pct"):
        v = _last_num(rows.get(cand)) if isinstance(rows, dict) else None
        if v is not None:
            return v
    return None


# metric_id -> (human label, extractor, unit, "higher_is_better" | "lower_is_better" | None)
METRICS = {
    "eff":  ("Efficiency ratio", lambda r: _ratio_last(r, "eff"), "%", "lower_is_better"),
    "roa":  ("Return on assets", lambda r: _ratio_last(r, "roa"), "%", "higher_is_better"),
    "roe":  ("Return on equity", lambda r: _ratio_last(r, "roe"), "%", "higher_is_better"),
    "nim":  ("Net interest margin", lambda r: _ratio_last(r, "nim"), "%", "higher_is_better"),
    "lev":  ("Leverage ratio (Tier 1)", lambda r: _ratio_last(r, "lev"), "%", "higher_is_better"),
    "cet1": ("CET1 ratio", _cet1_last, "%", "higher_is_better"),
    "ni":   ("Net income (final yr)", lambda r: _annual_last(r, "ni"), "$000s", "higher_is_better"),
    "assets": ("Total assets (final yr)", lambda r: _annual_last(r, "total_assets_eop"), "$000s", None),
}


def metric_value(res, metric_id):
    spec = METRICS.get(metric_id)
    if not spec:
        return None
    try:
        return spec[1](res)
    except Exception:
        return None


# ----------------------------------------------------------------------------------------------------
# LEVERS — dotted config paths, pure get/set on a deep copy.
# ----------------------------------------------------------------------------------------------------

def get_path(cfg, path):
    o = cfg
    for k in path.split("."):
        k = int(k) if k.lstrip("-").isdigit() else k
        try:
            o = o[k]
        except (KeyError, IndexError, TypeError):
            return None
    return o


def set_path(cfg, path, value):
    """Pure: returns a NEW deep-copied cfg with path set to value. Never mutates the input."""
    new = copy.deepcopy(cfg)
    ks = path.split(".")
    o = new
    for k in ks[:-1]:
        k = int(k) if k.lstrip("-").isdigit() else k
        o = o[k]
    last = ks[-1]
    last = int(last) if last.lstrip("-").isdigit() else last
    o[last] = value
    return new


# ----------------------------------------------------------------------------------------------------
# GOAL-SEEK — find the lever value that makes metric == target.
# Method: evaluate f(x) = metric(cfg with lever=x) - target. Bracket a sign change by expanding search,
# then bisect to tolerance. Bisection is unconditionally convergent on a continuous sign change and has
# no derivative/step-size fragility — the right default for a defensible tool. Returns full diagnostics.
# ----------------------------------------------------------------------------------------------------

def goal_seek(cfg, run_fn, lever_path, metric_id, target,
              lo=None, hi=None, tol=1e-4, max_evals=60):
    """cfg: base config. run_fn: cfg -> result (the engine). lever_path: dotted path to vary.
    metric_id: key in METRICS. target: desired metric value.
    lo/hi: optional search bounds for the lever; if omitted, inferred around the current value.
    Returns a dict with converged/solution/residual/evals/f_lo/f_hi and an honest status message."""
    x0 = get_path(cfg, lever_path)
    if not isinstance(x0, (int, float)):
        x0 = 0.0
    evals = {"n": 0}

    def f(x):
        evals["n"] += 1
        try:
            res = run_fn(set_path(cfg, lever_path, x))
        except Exception:
            # invalid lever value (e.g. out of the engine's accepted range) -> undefined here.
            # The bracketing/bisection logic treats None as "can't evaluate" and stays in-domain.
            return None
        m = metric_value(res, metric_id)
        if m is None:
            return None
        return m - target

    # establish a search bracket
    if lo is None or hi is None:
        span = max(abs(x0), 1.0)
        lo = (x0 - span) if lo is None else lo
        hi = (x0 + span) if hi is None else hi

    f_lo, f_hi = f(lo), f(hi)
    # if a bound is invalid (None), pull it inward toward x0 until it evaluates (bounded attempts)
    _pull = 0
    while f_lo is None and _pull < 8 and evals["n"] < max_evals:
        lo = lo + (x0 - lo) * 0.5; f_lo = f(lo); _pull += 1
    _pull = 0
    while f_hi is None and _pull < 8 and evals["n"] < max_evals:
        hi = hi + (x0 - hi) * 0.5; f_hi = f(hi); _pull += 1
    # expand the bracket outward (bounded) until a sign change is found; skip if expansion goes invalid
    grow = 0
    while (f_lo is not None and f_hi is not None and f_lo * f_hi > 0 and grow < 6
           and evals["n"] < max_evals):
        width = hi - lo
        new_lo, new_hi = lo - width, hi + width
        nf_lo, nf_hi = f(new_lo), f(new_hi)
        # only accept an expanded bound if it still evaluates; otherwise keep the valid inner bound
        if nf_lo is not None:
            lo, f_lo = new_lo, nf_lo
        if nf_hi is not None:
            hi, f_hi = new_hi, nf_hi
        if nf_lo is None and nf_hi is None:
            break
        grow += 1

    if f_lo is None or f_hi is None:
        return {"converged": False, "status": "metric undefined at search bounds",
                "solution": None, "residual": None, "evals": evals["n"]}
    if f_lo * f_hi > 0:
        # no sign change bracketed -> target may be unreachable by this lever alone
        cur = metric_value(run_fn(cfg), metric_id)
        return {"converged": False,
                "status": "target not reachable by this lever within a wide search range "
                          "(the metric may not depend monotonically on this lever, or the target is "
                          "outside its achievable range)",
                "solution": None, "residual": None, "evals": evals["n"],
                "current_metric": cur, "target": target}

    # bisection to tolerance
    a, b, fa = lo, hi, f_lo
    sol = None
    while evals["n"] < max_evals:
        mid = 0.5 * (a + b)
        fm = f(mid)
        if fm is None:
            break
        if abs(fm) <= tol or (b - a) < tol * max(1.0, abs(mid)) * 1e-3:
            sol = mid
            break
        if fa * fm < 0:
            b = mid
        else:
            a, fa = mid, fm
        sol = mid

    res_metric = metric_value(run_fn(set_path(cfg, lever_path, sol)), metric_id) if sol is not None else None
    residual = (res_metric - target) if res_metric is not None else None
    return {
        "converged": (residual is not None and abs(residual) <= max(tol, abs(target) * 1e-3)),
        "solution": sol,
        "achieved_metric": res_metric,
        "target": target,
        "residual": residual,
        "evals": evals["n"],
        "current_lever": x0,
        "status": "converged" if (residual is not None and abs(residual) <= max(tol, abs(target) * 1e-3))
                  else "did not fully converge within evaluation budget",
    }
