"""Golden tests for Axis-7 (conditional/threshold): the Durbin debit-interchange cap.
Run: python3 -m foundry.v2.tests_durbin"""
import sys, json, copy
sys.path.insert(0, ".")
from foundry.v2.income_modules import durbin_regulated_rate, durbin_effective_rate
from foundry.v2 import run_q


def main():
    passed = failed = 0
    def ck(n, c):
        nonlocal passed, failed
        (globals().__setitem__("passed", passed)) if False else None
        if c: passed += 1; print(f"PASS {n}")
        else: failed += 1; print(f"FAIL {n}")
    ck("cap on $40 ticket = 0.6%", abs(durbin_regulated_rate(40.0) - 0.006) < 1e-9)
    ck("zero ticket -> 0", durbin_regulated_rate(0.0) == 0.0)
    ck("below $10B: assumed passes", durbin_effective_rate(0.012, 40.0, 5_000_000.0) == 0.012)
    ck("at $10B: capped to 0.6%", abs(durbin_effective_rate(0.012, 40.0, 10_000_000.0) - 0.006) < 1e-9)
    ck("assumed below cap stays", durbin_effective_rate(0.003, 40.0, 12_000_000.0) == 0.003)
    ck("cap only reduces", durbin_effective_rate(0.004, 40.0, 20_000_000.0) == 0.004)
    cfg = json.load(open("foundry/fixtures/universal_template_bank.json"))
    r = run_q.run_v2(copy.deepcopy(cfg))
    ck("sub-$10B fixture integrity", r.get("checks", {}).get("integrity_pass") is True)
    print(f"\n{passed} passed, {failed} failed")
    return 0 if failed == 0 else 1
if __name__ == "__main__":
    sys.exit(main())
