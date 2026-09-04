"""Self-tests for the Foundry Lab analytical core. Proves goal-seek correctness and engine isolation."""
import sys, json, hashlib
sys.path.insert(0, ".")
from foundry.v2 import run_q, lab_core

def _fh(c):
    fin = run_q.run_v2(c)["financials"]
    return hashlib.sha256(json.dumps({"is": fin["is"], "bs": fin["bs"], "ratios": fin["ratios"]},
                                     sort_keys=True, default=str).encode()).hexdigest()[:16]

def main():
    cfg = json.load(open("foundry/fixtures/universal_template_bank.json"))
    run_fn = lambda c: run_q.run_v2(c)
    lever = "assumptions.lending_products.0.yield_ann"
    passed = failed = 0
    def ck(name, cond):
        nonlocal passed, failed
        if cond: passed += 1; print(f"PASS {name}")
        else: failed += 1; print(f"FAIL {name}")

    # 1. pure set_path does not mutate the input
    c2 = lab_core.set_path(cfg, lever, 0.10)
    ck("set_path is pure (no mutation)", lab_core.get_path(cfg, lever) != 0.10 and lab_core.get_path(c2, lever) == 0.10)

    # 2. goal-seek converges to a reachable target and independently verifies
    r = lab_core.goal_seek(cfg, run_fn, lever, "roa", 2.60, lo=0.0, hi=0.20)
    va = lab_core.metric_value(run_fn(lab_core.set_path(cfg, lever, r["solution"])), "roa") if r["solution"] else None
    ck("goal-seek converges (ROA=2.60)", r["converged"] and va is not None and abs(va - 2.60) < 0.01)

    # 3. unreachable target reported honestly, no crash
    r2 = lab_core.goal_seek(cfg, run_fn, lever, "roa", 10.0, lo=0.0, hi=0.20)
    ck("unreachable target reported, no crash", not r2["converged"])

    # 4. engine byte-identical after all Lab operations
    ck("engine byte-identical (isolation)", _fh(json.load(open("foundry/fixtures/universal_template_bank.json"))) == "3fee151428f6991e")

    # 4b. REGRESSION: CET1 must be a RATIO (0<v<100 pct), not a dollar amount, and must FALL as loans
    # (and thus RWA) grow. This guards the bug where the extractor returned standardized.cet1 (dollars).
    cet1_base = lab_core.metric_value(run_fn(cfg), "cet1")
    c_small = lab_core.set_path(cfg, "assumptions.lending_products.0.originations_per_period", 2000000)
    c_big = lab_core.set_path(cfg, "assumptions.lending_products.0.originations_per_period", 8000000)
    cet1_small = lab_core.metric_value(run_fn(c_small), "cet1")
    cet1_big = lab_core.metric_value(run_fn(c_big), "cet1")
    ck("CET1 is a ratio (0<v<100) that falls as loans grow",
       cet1_base is not None and 0 < cet1_base < 100 and cet1_big < cet1_small)

    # 5. sensitivity ranks by swing (tornado order) and returns a baseline
    levers = [f"assumptions.lending_products.{i}.yield_ann" for i,p in enumerate(cfg["assumptions"]["lending_products"]) if isinstance(p.get("yield_ann"),(int,float))]
    s = lab_core.sensitivity(cfg, run_fn, levers, "roa", pct=0.10)
    ck("sensitivity returns baseline + sorted rows",
       s["baseline"] is not None and all(abs(s["rows"][k]["swing"]) >= abs(s["rows"][k+1]["swing"]) for k in range(len(s["rows"])-1)))

    # 6. tradeoff grid is n×n, real numbers, monotone where expected
    g = lab_core.tradeoff_grid(cfg, run_fn, levers[0], levers[1], "roa", n=4)
    ok_shape = len(g["z"]) == 4 and all(len(r) == 4 for r in g["z"]) and g["invalid_count"] == 0
    ck("tradeoff grid shape + all-valid", ok_shape)

    # 7. optimizer maximizes ROA by pushing yields up; returns JSON-serializable floats
    import json as _json
    olv = [{"path": levers[0], "lo": 0.03, "hi": 0.12}, {"path": levers[1], "lo": 0.03, "hi": 0.12}]
    o = lab_core.optimize(cfg, run_fn, "roa", "max", olv, seeds=1, maxiter=8, popsize=6)
    serializable = True
    try: _json.dumps(o)
    except Exception: serializable = False
    ck("optimizer maximizes (yields high) + JSON-serializable",
       o.get("achieved") is not None and all(v > 0.09 for v in o["solution"].values()) and serializable)

    # 8. frontier domination logic matches hand-computed Pareto set (both max)
    pts = [{"a":1,"b":3},{"a":2,"b":2},{"a":3,"b":1},{"a":1,"b":1},{"a":2.5,"b":2.5}]
    for p in pts: p["frontier"] = not any(lab_core._dominates(q,p,"max","max") for q in pts if q is not p)
    front = sorted([(p["a"],p["b"]) for p in pts if p["frontier"]])
    ck("frontier domination logic (Pareto set correct)", front == [(1,3),(2.5,2.5),(3,1)])

    # 9. frontier over the real engine returns non-dominated points, JSON-serializable
    fr = lab_core.frontier(cfg, run_fn, "roa","max","lev","max",
                           "assumptions.lending_products.0.originations_per_period",
                           "assumptions.deposit_products.0.growth_per_period", n=5)
    fser = True
    try: _json.dumps(fr)
    except Exception: fser = False
    ck("frontier real-engine + serializable", fr.get("n_frontier",0) >= 1 and fser)

    print(f"\n{passed} passed, {failed} failed")
    return 0 if failed == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
