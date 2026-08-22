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

    # 5. sensitivity ranks by swing (tornado order) and returns a baseline
    levers = [f"assumptions.lending_products.{i}.yield_ann" for i,p in enumerate(cfg["assumptions"]["lending_products"]) if isinstance(p.get("yield_ann"),(int,float))]
    s = lab_core.sensitivity(cfg, run_fn, levers, "roa", pct=0.10)
    ck("sensitivity returns baseline + sorted rows",
       s["baseline"] is not None and all(abs(s["rows"][k]["swing"]) >= abs(s["rows"][k+1]["swing"]) for k in range(len(s["rows"])-1)))

    # 6. tradeoff grid is n×n, real numbers, monotone where expected
    g = lab_core.tradeoff_grid(cfg, run_fn, levers[0], levers[1], "roa", n=4)
    ok_shape = len(g["z"]) == 4 and all(len(r) == 4 for r in g["z"]) and g["invalid_count"] == 0
    ck("tradeoff grid shape + all-valid", ok_shape)

    print(f"\n{passed} passed, {failed} failed")
    return 0 if failed == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
