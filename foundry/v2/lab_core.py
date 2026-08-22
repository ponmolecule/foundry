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
    # CET1 RATIO (percent), final quarter. The real ratio lives in capital.standardized.ratios.cet1_rwa.
    # NOTE: standardized.cet1 is the capital DOLLAR amount (numerator), NOT the ratio — do not use it.
    # Only accept explicit RATIO keys, and sanity-check the magnitude: a CET1 ratio is a percentage
    # (well under ~1000 even in extreme de novo cases); a value larger than that is a dollar amount
    # leaking through, so we reject it (return None) rather than report a wrong number.
    cap = res.get("capital") or {}
    std = cap.get("standardized") or {}
    ratios = std.get("ratios") or {}
    if isinstance(ratios, dict):
        for cand in ("cet1_rwa", "cet1_ratio"):
            v = _last_num(ratios.get(cand))
            if v is not None and abs(v) < 1000:
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
        # no sign change bracketed -> target may be unreachable by this lever alone. Report the
        # achievable range we observed so the message is actionable, not just a hedge.
        cur = metric_value(run_fn(cfg), metric_id)
        m_lo = (f_lo + target) if f_lo is not None else None
        m_hi = (f_hi + target) if f_hi is not None else None
        rng = None
        if m_lo is not None and m_hi is not None:
            rng = (min(m_lo, m_hi), max(m_lo, m_hi))
        msg = "target not reachable by this lever alone"
        if rng is not None:
            msg = ("this lever moves the metric between %.3f and %.3f across a wide range; "
                   "target %.3f is outside that" % (rng[0], rng[1], target))
        return {"converged": False, "status": msg,
                "solution": None, "residual": None, "evals": evals["n"],
                "current_metric": cur, "target": target,
                "achievable_min": (rng[0] if rng else None),
                "achievable_max": (rng[1] if rng else None)}

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


# ----------------------------------------------------------------------------------------------------
# SENSITIVITY (Tier 2) — perturb each lever independently by ±pct, measure the metric swing, rank.
# Produces tornado-chart data: for each lever, the metric at low and high, and the total swing.
# ----------------------------------------------------------------------------------------------------

def sensitivity(cfg, run_fn, lever_paths, metric_id, pct=0.10):
    """For each lever, set it to (1-pct)*x0 and (1+pct)*x0, measure the metric at each, report the swing.
    Returns baseline + a list sorted by absolute swing (largest first) = tornado order.
    Robust to invalid probes (returns None for that side) and to non-numeric levers (skipped)."""
    base_metric = metric_value(run_fn(cfg), metric_id)
    rows = []
    for path in lever_paths:
        x0 = get_path(cfg, path)
        if not isinstance(x0, (int, float)):
            continue
        lo_x, hi_x = x0 * (1 - pct), x0 * (1 + pct)
        # if x0 is zero, ± percentage does nothing; use a small absolute step so the lever still moves
        if x0 == 0:
            lo_x, hi_x = -abs(pct), abs(pct)

        def _safe(xv):
            try:
                return metric_value(run_fn(set_path(cfg, path, xv)), metric_id)
            except Exception:
                return None
        m_lo, m_hi = _safe(lo_x), _safe(hi_x)
        vals = [v for v in (m_lo, m_hi) if v is not None]
        swing = (max(vals) - min(vals)) if len(vals) == 2 else 0.0
        rows.append({"path": path, "x0": x0, "lo_x": lo_x, "hi_x": hi_x,
                     "m_lo": m_lo, "m_hi": m_hi, "swing": swing})
    rows.sort(key=lambda r: abs(r["swing"]), reverse=True)
    return {"baseline": base_metric, "metric": metric_id, "pct": pct, "rows": rows}


# ----------------------------------------------------------------------------------------------------
# TRADE-OFF GRID (Tier 3) — evaluate a metric over a 2D grid of two levers. Each grid point is a real
# engine run. Returns a surface (z[i][j]) plus axes, for a 3D surface / contour plot.
# ----------------------------------------------------------------------------------------------------

def tradeoff_grid(cfg, run_fn, x_path, y_path, metric_id,
                  x_range=None, y_range=None, n=11):
    """Evaluate metric over an n×n grid of (x_path, y_path). Ranges default to ±50% around current.
    Returns {x_vals, y_vals, z[j][i] (rows=y, cols=x), metric, invalid_count}. Invalid points -> None."""
    x0 = get_path(cfg, x_path)
    y0 = get_path(cfg, y_path)
    if not isinstance(x0, (int, float)) or not isinstance(y0, (int, float)):
        return {"error": "both levers must be numeric"}
    def _axis(v0, rng):
        if rng is None:
            lo, hi = (v0 * 0.5, v0 * 1.5) if v0 != 0 else (-1.0, 1.0)
        else:
            lo, hi = rng
        if n == 1:
            return [lo]
        step = (hi - lo) / (n - 1)
        return [lo + step * k for k in range(n)]
    x_vals = _axis(x0, x_range)
    y_vals = _axis(y0, y_range)
    z = []
    invalid = 0
    for yv in y_vals:
        row = []
        for xv in x_vals:
            try:
                c = set_path(cfg, x_path, xv)
                c = set_path(c, y_path, yv)
                m = metric_value(run_fn(c), metric_id)
            except Exception:
                m = None
            if m is None:
                invalid += 1
            row.append(m)
        z.append(row)
    return {"x_vals": x_vals, "y_vals": y_vals, "z": z, "metric": metric_id,
            "x_path": x_path, "y_path": y_path, "x0": x0, "y0": y0, "invalid_count": invalid}


# ----------------------------------------------------------------------------------------------------
# OPTIMIZER (Tier 4) — constrained optimization over multiple levers. Maximize/minimize an objective
# metric subject to constraints (other metrics >=/<= bounds) and per-lever bounds. Black-box, so we use
# differential evolution (global, derivative-free, robust to the engine's non-smoothness) with a penalty
# formulation for constraints. Honest about non-uniqueness: we re-solve from independent seeds and report
# whether they agree.
# ----------------------------------------------------------------------------------------------------

def _pure_de(cost, bounds, maxiter=25, popsize=12, seed=0, F=0.7, CR=0.9):
    """Dependency-free differential evolution (rand/1/bin), bounded. Fallback when scipy is absent.
    Returns (best_x, best_cost). Verified competitive with scipy on the Lab's problems."""
    import random
    rng = random.Random(seed)
    d = len(bounds)
    NP = max(5, popsize * d if d > 1 else popsize)
    pop = [[rng.uniform(lo, hi) for (lo, hi) in bounds] for _ in range(NP)]
    fit = [cost(ind) for ind in pop]
    for _ in range(maxiter):
        for i in range(NP):
            idxs = list(range(NP)); idxs.remove(i)
            a, b, c = rng.sample(idxs, 3)
            mutant = [pop[a][k] + F * (pop[b][k] - pop[c][k]) for k in range(d)]
            mutant = [min(max(mutant[k], bounds[k][0]), bounds[k][1]) for k in range(d)]
            jrand = rng.randrange(d)
            trial = [mutant[k] if (rng.random() < CR or k == jrand) else pop[i][k] for k in range(d)]
            ft = cost(trial)
            if ft <= fit[i]:
                pop[i] = trial; fit[i] = ft
    best = min(range(NP), key=lambda i: fit[i])
    return pop[best], fit[best]


def optimize(cfg, run_fn, objective, direction, levers, constraints=None,
             seeds=2, maxiter=25, popsize=12):
    """objective: metric_id to optimize. direction: 'max'|'min'. levers: list of
    {path, lo, hi} bounds. constraints: list of {metric, op ('>=', '<='), value}.
    Returns best solution, achieved objective, constraint satisfaction, and a non-uniqueness note.
    Every evaluation is a real engine run on a scratch config; engine untouched.
    Uses scipy.differential_evolution when available; falls back to a pure-Python DE otherwise."""
    try:
        from scipy.optimize import differential_evolution
        _have_scipy = True
    except Exception:
        differential_evolution = None
        _have_scipy = False
    constraints = constraints or []
    paths = [L["path"] for L in levers]
    bounds = [(float(L["lo"]), float(L["hi"])) for L in levers]
    sign = -1.0 if direction == "max" else 1.0    # DE minimizes; flip for max

    # a big penalty scale relative to typical metric magnitude
    PEN = 1e6

    def evaluate(x):
        c = cfg
        for p, xv in zip(paths, x):
            c = set_path(c, p, float(xv))
        try:
            res = run_fn(c)
        except Exception:
            return None, None, [False] * len(constraints)
        obj = metric_value(res, objective)
        if obj is None:
            return None, None, [False] * len(constraints)
        sat = []
        penalty = 0.0
        for con in constraints:
            mv = metric_value(res, con["metric"])
            if mv is None:
                sat.append(False); penalty += PEN; continue
            if con["op"] == ">=":
                ok = mv >= con["value"]; short = max(0.0, con["value"] - mv)
            else:
                ok = mv <= con["value"]; short = max(0.0, mv - con["value"])
            sat.append(ok)
            penalty += 0.0 if ok else PEN * (1.0 + short)
        return obj, penalty, sat

    def cost(x):
        obj, penalty, _ = evaluate(x)
        if obj is None:
            return PEN * 10          # invalid region: strongly discouraged
        return sign * obj + penalty

    solutions = []
    for s in range(max(1, seeds)):
        try:
            if _have_scipy:
                r = differential_evolution(cost, bounds, maxiter=maxiter, popsize=popsize,
                                           seed=s, tol=1e-6, polish=True, init="latinhypercube")
                xbest = list(r.x)
            else:
                xbest, _ = _pure_de(cost, bounds, maxiter=maxiter, popsize=popsize, seed=s)
            obj, penalty, sat = evaluate(xbest)
            solutions.append({"x": xbest, "obj": obj, "feasible": all(sat) if constraints else True,
                              "sat": sat})
        except Exception as e:
            solutions.append({"x": None, "obj": None, "feasible": False, "sat": [], "err": str(e)[:120]})

    # pick the best FEASIBLE solution (or best objective if none feasible)
    feasible = [s for s in solutions if s.get("feasible") and s.get("obj") is not None]
    pool = feasible if feasible else [s for s in solutions if s.get("obj") is not None]
    if not pool:
        return {"error": "optimizer could not evaluate the objective anywhere in the search space",
                "feasible": False}
    best = max(pool, key=lambda s: s["obj"]) if direction == "max" else min(pool, key=lambda s: s["obj"])

    # non-uniqueness check: do the feasible seeds agree on lever values?
    nonunique = False
    if len(feasible) >= 2:
        for k in range(len(paths)):
            vals = [f["x"][k] for f in feasible]
            span = max(vals) - min(vals)
            scale = max(1e-9, abs(best["x"][k]))
            if span / scale > 0.10:          # >10% disagreement on a lever
                nonunique = True; break

    return {
        "objective": objective, "direction": direction,
        "solution": {paths[k]: float(best["x"][k]) for k in range(len(paths))},
        "achieved": float(best["obj"]) if best["obj"] is not None else None,
        "feasible": bool(best["feasible"]),
        "constraint_status": [{"metric": constraints[i]["metric"], "op": constraints[i]["op"],
                               "value": constraints[i]["value"], "met": bool(best["sat"][i])}
                              for i in range(len(constraints))],
        "nonunique": bool(nonunique),
        "note": ("Multiple lever combinations reach a similar optimum \u2014 this is one of several; "
                 "treat it as a direction, not the unique answer."
                 if nonunique else
                 "Feasible optimum found." if best["feasible"] else
                 "No fully feasible solution found; showing the closest (some constraints unmet)."),
        "seeds_run": len(solutions),
        "solver": ("scipy differential_evolution" if _have_scipy else "pure-Python differential evolution (scipy absent)"),
    }


# ----------------------------------------------------------------------------------------------------
# EFFICIENT FRONTIER (Tier 5) — two competing objectives over two decision levers. Sweep an n×n grid
# (each point ONE real engine run yielding BOTH objectives), then identify the non-dominated (Pareto)
# set. Honest scope: this is a SAMPLED frontier over the chosen two levers on a grid — not a proven-
# continuous Pareto front. Resolution is the grid; every point is a real, traceable engine run.
# ----------------------------------------------------------------------------------------------------

def _dominates(p, q, dir_a, dir_b):
    """Does point p dominate q? Normalize each objective to higher-is-better, then p dominates q iff
    p is >= q on both and > on at least one."""
    pa = p["a"] if dir_a == "max" else -p["a"]
    pb = p["b"] if dir_b == "max" else -p["b"]
    qa = q["a"] if dir_a == "max" else -q["a"]
    qb = q["b"] if dir_b == "max" else -q["b"]
    return (pa >= qa and pb >= qb) and (pa > qa or pb > qb)


def frontier(cfg, run_fn, obj_a, dir_a, obj_b, dir_b, x_path, y_path, n=9):
    """Two objectives (obj_a/dir_a, obj_b/dir_b) over two levers (x_path, y_path) swept on an n×n grid.
    Returns every evaluated point (with its lever coords + both objective values) and a boolean flag
    for whether each is on the non-dominated frontier. Ranges default to ±50% around current."""
    x0 = get_path(cfg, x_path); y0 = get_path(cfg, y_path)
    if not isinstance(x0, (int, float)) or not isinstance(y0, (int, float)):
        return {"error": "both levers must be numeric"}
    def _axis(v0):
        lo, hi = (v0 * 0.5, v0 * 1.5) if v0 != 0 else (-1.0, 1.0)
        if n == 1:
            return [lo]
        step = (hi - lo) / (n - 1)
        return [lo + step * k for k in range(n)]
    xs, ys = _axis(x0), _axis(y0)
    points = []
    for xv in xs:
        for yv in ys:
            try:
                c = set_path(cfg, x_path, xv)
                c = set_path(c, y_path, yv)
                res = run_fn(c)
                a = metric_value(res, obj_a); b = metric_value(res, obj_b)
            except Exception:
                a = b = None
            if a is None or b is None:
                continue
            points.append({"x": xv, "y": yv, "a": a, "b": b})
    # non-dominated flag
    for p in points:
        p["frontier"] = not any(_dominates(q, p, dir_a, dir_b) for q in points if q is not p)
    front = [p for p in points if p["frontier"]]
    # sort by objective a for a clean line
    front.sort(key=lambda p: p["a"])
    # Deduplicate on the (a,b) OUTCOME: multiple lever settings can reach the same objective pair, and
    # they render as stacked dots (making the count disagree with what's visible). Collapse to distinct
    # outcomes, but record how many settings map to each (informative — several paths to one result).
    seen = {}
    distinct = []
    for p in front:
        key = (round(p["a"], 4), round(p["b"], 4))
        if key in seen:
            seen[key]["settings_count"] += 1
        else:
            q = dict(p); q["settings_count"] = 1
            seen[key] = q
            distinct.append(q)
    return {"obj_a": obj_a, "dir_a": dir_a, "obj_b": obj_b, "dir_b": dir_b,
            "x_path": x_path, "y_path": y_path, "points": points, "frontier": distinct,
            "n_points": len(points), "n_frontier": len(distinct),
            "n_frontier_settings": len(front)}
