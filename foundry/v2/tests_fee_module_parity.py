"""GUT reproduces the legacy fee_modules formulas to the dollar (gates the fee_modules retirement).
Run: python3 -m foundry.v2.tests_fee_module_parity"""
import sys
sys.path.insert(0, ".")
from foundry.v2.income_modules import _g, fee_stream_q, managed_notional_series
Q = 12
def main():
    passed = failed = 0
    def ck(n, c):
        nonlocal passed, failed
        if c: passed += 1; print(f"PASS {n}")
        else: failed += 1; print(f"FAIL {n}")
    sv = {"accounts": 35000, "growth_q": 0.03, "fee_m": 11.0}
    old = [_g(sv["accounts"], sv["growth_q"], q) * sv["fee_m"] * 3.0 for q in range(1, Q + 1)]
    gut = {"basis": "account", "driver": {"source": "constant", "trajectory": "proportional",
           "params": {"base": 35000, "growth_q": 0.03}},
           "rate": {"params": {"fee_per_period": 11.0, "periods_per_q": 3.0}}, "timing": {"start_period": 1}}
    ck("service charges", all(abs(old[i] - fee_stream_q(gut, i + 1, {})[0]) < 1e-6 for i in range(Q)))
    rails = [{"vol_q": 300000, "growth_q": 0.04, "fee_per_tx": 0.30},
             {"vol_q": 12000, "growth_q": 0.03, "fee_per_tx": 18.0},
             {"vol_q": 40000, "growth_q": 0.08, "fee_per_tx": 0.50}]
    old = [sum(_g(r["vol_q"], r["growth_q"], q) * r["fee_per_tx"] for r in rails) for q in range(1, Q + 1)]
    gr = [{"basis": "transaction", "driver": {"source": "constant", "trajectory": "proportional",
           "params": {"base": r["vol_q"], "growth_q": r["growth_q"]}},
           "rate": {"params": {"per_unit": r["fee_per_tx"]}}, "timing": {"start_period": 1}} for r in rails]
    ck("payments (3 rails)", all(abs(old[i] - sum(fee_stream_q(s, i + 1, {})[0] for s in gr)) < 1e-6 for i in range(Q)))
    tr = {"aum_open": 60_000_000.0, "aum_growth_q": 0.04, "fee_bp_ann": 80.0}
    old = []; aum = tr["aum_open"]
    for q in range(1, Q + 1):
        e = aum * (1 + tr["aum_growth_q"]); old.append((aum + e) / 2.0 * tr["fee_bp_ann"] / 10000.0 / 4.0); aum = e
    avg, _ = managed_notional_series({"day1": 60_000_000.0, "trajectory": "proportional", "growth_q": 0.04}, Q)
    ck("trust", all(abs(old[i] - avg[i] * 80.0 / 10000.0 / 4.0) < 1e-3 for i in range(Q)))
    b = {"programs": 3, "accts_per_program": 12000, "growth_q": 0.06, "rev_per_acct_m": 2.75}
    old = [_g(b["programs"] * b["accts_per_program"], b["growth_q"], q) * b["rev_per_acct_m"] * 3.0 for q in range(1, Q + 1)]
    gut = {"basis": "account", "driver": {"source": "constant", "trajectory": "proportional",
           "params": {"base": 36000, "growth_q": 0.06}},
           "rate": {"params": {"fee_per_period": 2.75, "periods_per_q": 3.0}}, "timing": {"start_period": 1}}
    ck("baas", all(abs(old[i] - fee_stream_q(gut, i + 1, {})[0]) < 1e-6 for i in range(Q)))
    print(f"\n{passed} passed, {failed} failed")
    return 0 if failed == 0 else 1
if __name__ == "__main__":
    sys.exit(main())
