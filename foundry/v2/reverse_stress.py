"""r501: reverse stress on the same deterministic runner as forward stress.

The question is backwards: how far must one named variable move before capital breaches a selected
threshold? The variable is either one change to a supported input (multiply, add, delay, or the rate
path shift) or a whole scenario severity scaled by lambda. Every evaluation is a recorded engine run on a
copy of the base; the base is never modified.

Search: a grid across the user's bounds, then bisection inside every interval where the breach status
changes. Several crossings, or none, are reported as found. A breaking point is never claimed outside the
searched bounds, and a non-monotonic response is said to be one.
"""
from __future__ import annotations

import copy
import time
import uuid

from . import stress
from .solver import bisect_x, grid, monotonic, sign_changes
from .stress_report import RATIOS, TIERS, base_only, capital_assessment, report_window

CRITERIA = ("any_threshold", "leverage_only")


def _criterion_margin(cap, criterion, tiers):
    """Smallest (lowest ratio - floor) across the selected ratios and tiers, in percentage points,
    with the binding ratio, tier and the period of that ratio's lowest point."""
    best = None
    for r, _lab in RATIOS:
        if criterion == "leverage_only" and r != "leverage":
            continue
        x = cap["ratios"].get(r) or {}
        if not x.get("available"):
            continue
        for t, _tl in TIERS:
            if t not in tiers or not x["tiers"].get(t):
                continue
            v = x["tiers"][t]
            m = x["min"] - v["floor"]
            if best is None or m < best["margin"]:
                best = dict(margin=round(m, 6), ratio=r, tier=t, floor=v["floor"], lowest=x["min"], period=x["min_period"],
                            first_breach_period=v["first_breach_period"])
    return best


def _scaled_scenario(sc, severity_id, lam):
    """Every change in one severity scaled by lambda: multiplicative changes scale their deviation from 1,
    additive changes and the rate shift scale their size, delays scale and round their length."""
    sev = next(s for s in sc.get("severities") or [] if s.get("id") == severity_id)
    out = []
    for o in sev.get("overrides") or []:
        v = float(o["value"])
        if o["op"] == "multiply":
            nv = 1.0 + lam * (v - 1.0)
        elif o["op"] == "add":
            nv = lam * v
        elif o["op"] == "delay":
            nv = int(round(lam * v))
            if nv < 1:
                continue
        else:
            raise stress.StressError(f"{o.get('target')}: a replaced value cannot be scaled; use multiply or add for reverse stress")
        out.append(dict(o, value=max(nv, 0.0) if o["op"] == "multiply" else nv))
    return dict(sc, id=f"{sc.get('id')}-x{lam:g}", severities=[dict(sev, overrides=out)])


def _one_change_scenario(spec, x):
    o = dict(target=spec["target"], op=spec["op"], value=(int(round(x)) if spec["op"] == "delay" else x),
             start=int(spec.get("start") or 1), end=spec.get("end"))
    return dict(id="reverse", name="Reverse stress", kind="sensitivity", funding=spec.get("funding", "inherit"), version=1,
                severities=[dict(id="x", label="x", overrides=[o] if not (spec["op"] == "delay" and o["value"] < 1) else [])])


def describe(spec, cfg) -> str:
    if spec["kind"] == "scale":
        sc = next((s for s in cfg.get("stress_scenarios") or [] if s.get("id") == spec["scenario_id"]), {})
        sev = next((v for v in sc.get("severities") or [] if v.get("id") == spec["severity_id"]), {})
        return f"{sc.get('name', 'scenario')} · {sev.get('label', '')}, scaled by λ"
    t = next((r for r in stress.targets(cfg) if r.get("key") == spec["target"]), None)
    lab = f"{t['product_name']} · {t['label']}" if t else spec["target"]
    return f"{lab}, {dict(multiply='multiplier', add='added amount', delay='delay in periods').get(spec['op'], spec['op'])}"


def validate(spec, cfg):
    k = spec.get("kind")
    if k not in ("change", "scale"):
        raise stress.StressError("choose one change or a whole scenario to scale")
    lo, hi = spec.get("lo"), spec.get("hi")
    if not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in (lo, hi)) or not lo < hi:
        raise stress.StressError("enter search bounds with the lower bound below the upper bound")
    if spec.get("criterion", "any_threshold") not in CRITERIA:
        raise stress.StressError("criterion must be any_threshold or leverage_only")
    n = int(spec.get("grid") or 9)
    if n < 3 or n > 41:
        raise stress.StressError("use between 3 and 41 grid points")
    if k == "change":
        stress.resolve_target(cfg, spec.get("target"))
        if spec.get("op") not in ("multiply", "add", "delay"):
            raise stress.StressError("reverse stress moves a multiplier, an added amount or a delay")
        if spec["target"] == stress.RATE_KEY and spec["op"] != "add":
            raise stress.StressError("the rate path moves by an added number of basis points")
        if spec["op"] == "multiply" and lo < 0:
            raise stress.StressError("a multiplier cannot be negative")
        if spec["op"] == "delay" and (lo < 0 or hi >= int((cfg.get("assumptions") or {}).get("n_periods") or 12)):
            raise stress.StressError("a delay runs from 0 to fewer periods than the horizon")
    else:
        sc = next((s for s in cfg.get("stress_scenarios") or [] if s.get("id") == spec.get("scenario_id")), None)
        if sc is None or not any(v.get("id") == spec.get("severity_id") for v in sc.get("severities") or []):
            raise stress.StressError("the scenario to scale is not saved in this configuration")
    return n


def run(cfg, spec, *, base_res=None, max_evals=60) -> dict:
    """Grid then bisection. Returns the full evidence: every evaluation, crossings, status, limitations."""
    n = validate(spec, cfg)
    t0 = time.time()
    base_cfg = base_only(cfg)
    before = stress._canon(base_cfg)
    base_res = base_res or stress._engine_run(base_cfg)
    rcfg = dict(base_cfg, stress_reporting=cfg.get("stress_reporting"))
    win = report_window(rcfg)
    tiers = tuple(spec.get("tiers") or ("regulatory", "commitment", "policy"))
    crit = spec.get("criterion", "any_threshold")
    modes = {}
    if spec["kind"] == "change" and spec["target"] != stress.RATE_KEY:
        pr = stress.probe_target(cfg, spec["target"])
        if not pr["ok"]:
            raise stress.StressError(f"this input cannot be stressed yet: {pr['reason']}")
        modes[spec["target"]] = pr["mode"]
    elif spec["kind"] == "scale":
        sc0 = next(s for s in cfg["stress_scenarios"] if s.get("id") == spec["scenario_id"])
        sev0 = next(v for v in sc0["severities"] if v.get("id") == spec["severity_id"])
        for o in sev0.get("overrides") or []:
            if o["target"] != stress.RATE_KEY:
                pr = stress.probe_target(cfg, o["target"])
                if not pr["ok"]:
                    raise stress.StressError(f"{o['target']}: cannot be stressed yet: {pr['reason']}")
                modes[o["target"]] = pr["mode"]
    evals, cache = [], {}

    def margin_at(x):
        key = round(float(x), 9)
        if key in cache:
            return cache[key]
        try:
            if spec["kind"] == "scale":
                sc = _scaled_scenario(sc0, spec["severity_id"], x)
                sid = spec["severity_id"]
            else:
                sc = _one_change_scenario(spec, x)
                sid = "x"
            c, _ = stress.build_config(cfg, sc, sid, modes=modes)
            res = stress._engine_run(c)
            cap = capital_assessment(dict(c, stress_reporting=cfg.get("stress_reporting")), res, win)
            b = _criterion_margin(cap, crit, tiers)
            ni = sum(float(v or 0) for v in res["financials"]["is"]["ni"][:win["periods"]])
            if b is None:   # no capital measure or no applicable threshold: this evaluation cannot say "no breach"
                row = dict(x=round(float(x), 9), margin=None, breach=None, binding=None, cum_ni=round(ni, 3),
                           error="no capital measure with an applicable threshold for the selected ratios and tiers")
            else:
                row = dict(x=round(float(x), 9), margin=b["margin"], breach=b["margin"] < 0, binding=b, cum_ni=round(ni, 3))
        except Exception as e:   # any failed evaluation is recorded as failed, never as "no breach"
            row = dict(x=round(float(x), 9), margin=None, breach=None, binding=None, error=(str(e) or type(e).__name__)[:200])
        evals.append(row)
        cache[key] = row
        return row

    budget = lambda: len(evals) < max_evals
    pts = [(x, margin_at(x)["margin"]) for x in grid(spec["lo"], spec["hi"], n)]
    xtol = float(spec.get("tolerance") or (spec["hi"] - spec["lo"]) / 200.0)
    if spec.get("kind") == "change" and spec.get("op") == "delay":
        xtol = max(xtol, 1.0)
    crossings = []
    x0 = 0.0 if spec["kind"] == "scale" or spec.get("op") in ("add", "delay") else 1.0
    for (a, fa), (b, fb) in sign_changes(pts):
        lo_, hi_ = bisect_x(lambda x: margin_at(x)["margin"], a, b, fa, xtol=xtol, budget=budget)
        ra, rb = cache[round(float(lo_), 9)], cache[round(float(hi_), 9)]
        far, near = (ra, rb) if hi_ <= x0 else (rb, ra)          # moving away from the unstressed value
        brk = far if far["breach"] else near
        crossings.append(dict(between=[round(lo_, 9), round(hi_, 9)], x=brk["x"],
                              direction="into breach" if far["breach"] else "out of breach", binding=brk["binding"]))
    into = [c for c in crossings if c["direction"] == "into breach"] or crossings
    first = min(into, key=lambda c: abs(c["x"] - x0)) if into else None
    valid = [r for r in evals if r["breach"] is not None]
    failed = [r for r in evals if r["breach"] is None]
    all_breach = bool(valid) and all(r["breach"] for r in valid)
    none_breach = bool(valid) and not any(r["breach"] for r in valid)
    if not valid:
        status = "search_failed"            # nothing was evaluated: no conclusion of any kind
    elif none_breach and failed:
        status = "inconclusive"             # no breach where it could be measured, but part of the range was not
    elif none_breach:
        status = "no_breach_within_bounds"
    elif all_breach and not crossings:
        status = "breach_throughout_bounds"
    else:
        status = "multiple_crossings" if len(crossings) > 1 else "breach_found"
    lim = [f"Searched {spec['lo']:g} to {spec['hi']:g} only; nothing is claimed outside these bounds.",
           f"Grid of {n} points, then bisection to {xtol:g}; a breach confined between two grid points could be missed."]
    if not monotonic(pts):
        lim.append("The response is not monotonic across the grid (for example slower asset growth can first raise leverage).")
    if failed:
        lim.insert(0, f"{len(failed)} of {len(evals)} evaluations failed or had no applicable threshold (first: {failed[0]['error']}); "
                      f"no conclusion is drawn where nothing was measured.")
    if len(evals) >= max_evals:
        lim.append(f"Stopped at the evaluation budget of {max_evals} engine runs.")
    if stress._canon(base_cfg) != before:
        raise RuntimeError("reverse stress modified the base configuration")
    return dict(spec=copy.deepcopy(spec), variable=describe(spec, cfg), criterion=crit, tiers=list(tiers),
                window=dict(periods=win["periods"], label=win["label"]), grid_points=n, tolerance=xtol,
                evaluations=sorted(evals, key=lambda r: r["x"]), crossings=sorted(crossings, key=lambda c: c["x"]),
                breaking_point=first, status=status, failed_evaluations=len(failed), valid_evaluations=len(valid), monotonic=monotonic(pts), limitations=lim,
                engine_runs=len(evals) + 1, seconds=round(time.time() - t0, 2))


def record(cfg, result) -> dict:
    """A formal reverse-stress record: evidence on the frozen baseline, stored like any stress run."""
    bp = result.get("breaking_point")
    return dict(run_id=uuid.uuid4().hex[:12], record_type="reverse_stress", status="completed", scenario_name="Reverse stress: " + result["variable"], severity_id="reverse",
                severity_label={"breach_found": "breaking point found", "multiple_crossings": "several crossings",
                                "no_breach_within_bounds": "no breach within bounds",
                                "inconclusive": "inconclusive: some evaluations failed", "search_failed": "search failed",
                                "breach_throughout_bounds": "breached throughout bounds"}[result["status"]],
                kind="reverse_stress", base_fingerprint=stress.base_fingerprint(cfg), engine=stress.engine_identity(),
                started_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), checks=dict(structural="passed", zero_shock="not applicable"),
                errors=[], reverse=result, window=result["window"], breaking_point=bp,
                **_scale_identity(cfg, result["spec"]))


def _scale_identity(cfg, spec):
    if spec.get("kind") != "scale":
        return {}
    sc = next((s for s in cfg.get("stress_scenarios") or [] if s.get("id") == spec.get("scenario_id")), {})
    return dict(scenario_id=sc.get("id"), scenario_version=sc.get("version"), scenario_fingerprint=stress.scenario_fingerprint(sc))
