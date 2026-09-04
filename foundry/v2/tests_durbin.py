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


def test_reg_ii_calendar_timing():
    """AUDIT Durbin timing: cap engages on the Reg II effective date (July 1 = Q3 start) of the year
    AFTER the calendar year-end at which assets first reach >=$10B — not immediately, not every
    quarter. Bank opens 2027-Q1, crosses $10B, so 2027 year-end triggers -> cap from 2028-Q3."""
    import json as _j, copy as _cp
    from foundry.v2 import run_q as _r
    base = _j.load(open("foundry/fixtures/universal_template_bank.json"))
    c = _cp.deepcopy(base)
    c["assumptions"]["periods_per_year"] = 4
    c["assumptions"]["n_periods"] = 12
    c["target_opening"] = "2027-Q1"
    c["assumptions"]["deposit_products"] = [{"name": "Big", "opening_balance": 11e9,
        "rate_type": "fixed", "rate_paid_ann": 0.0, "growth_per_period": 0.0,
        "runoff_per_period": 0.0, "fee_yield_ann": 0.0, "opex_pct_ann": 0.0,
        "opex_fixed_per_period": 0, "call_report_line": "depDDA",
        "measurement": "amortized"}] + base["assumptions"]["deposit_products"]
    ig, inet, tk = 0.0125, 0.002, 42.0
    c["assumptions"]["obs_exposures"] = [{"name": "IC", "call_report_line": "obs",
        "_fee_product": True, "fee_streams": [{"basis": "transaction",
        "driver": {"source": "constant", "trajectory": "proportional",
                   "params": {"base": 750000, "growth_per_period": 0.0}},
        "rate": {"behavior": "durbin_capped",
                 "params": {"per_unit": tk*(ig-inet), "rate": ig, "avg_ticket": tk}},
        "timing": {"start_period": 1}}]}]
    dc = _r.run_v2(c)["financials"]["is"].get("durbinCap") or []
    # 0-based output arrays: index 5 = period 6 (2028-Q2, still exempt); index 6 = period 7
    # (2028-Q3 = July 1, cap effective). So indices 0..5 must be None/0; index 6+ must be capped.
    pre = all((i >= len(dc)) or (not dc[i]) for i in range(0, 6))    # periods 1..6 uncapped
    post = len(dc) > 6 and bool(dc[6])                                # period 7 (2028-Q3) capped
    assert pre, f"cap engaged before the 2028-Q3 effective date: {dc[:6]}"
    assert post, f"cap did not engage at the 2028-Q3 effective date: {dc}"
    print("  PASS  Reg II calendar timing: cap engages 2028-Q3 (July 1) after 2027 year-end crossing")

if __name__ == "__main__":
    test_reg_ii_calendar_timing()
