"""Canonical custody/trust six-stream Fee Product reference case.

Seeded by the Claude/GPT/Ponmile design review and deliberately extended in-place.
The pre-remediation reference behavior was independently verified 10/10 on 5b31198.
This file is the golden contract for natural-period fee semantics across quarterly/monthly cadence.
"""
import sys
sys.path.insert(0, ".")
from foundry.v2.income_modules import fee_stream_q, product_fee_streams_q

AUC = 120_000_000.0
CTX = {"managed_notional": AUC}


def _annual(stream, ppy, year=1):
    lo = (year - 1) * ppy + 1
    hi = year * ppy
    return sum(fee_stream_q(stream, i, dict(CTX), ppy)[0] for i in range(lo, hi + 1))


def _product_annual(product, ppy, year=1):
    lo = (year - 1) * ppy + 1
    hi = year * ppy
    return sum(product_fee_streams_q(product, i, dict(CTX), ppy)[0] for i in range(lo, hi + 1))


def _bal_derived(mult=None, pct=None, rate=0.0):
    """Legacy arithmetic reference: balance basis on raw derived stock/annualized quantity."""
    p = {}
    if mult is not None:
        p["multiple"] = mult
    if pct is not None:
        p["pct"] = pct
    return {
        "basis": "balance",
        "driver": {"source": "managed_notional", "trajectory": "derived", "params": p},
        "rate": {"behavior": "flat", "params": {"rate": rate}},
        "cost": {"kind": "none", "params": {}},
    }


def _tx_flow(*, kind, value, period="year", per_unit=0.0, trajectory="flat", schedule=None, growth_spec=None):
    c = {"kind": kind, "value": value, "period": period, "trajectory": trajectory}
    if schedule is not None:
        c["schedule"] = schedule
    if growth_spec is not None:
        c["growth_spec"] = growth_spec
    return {
        "basis": "transaction",
        "driver": {"source": "managed_notional", "trajectory": "derived", "params": {"coefficient": c}},
        "rate": {"behavior": "flat", "params": {"per_unit": per_unit}},
        "cost": {"kind": "none", "params": {}},
    }


def _account_annual(value=12_000.0, count=10):
    return {
        "basis": "account",
        "driver": {"source": "constant", "trajectory": "flat", "params": {"base": count}},
        "rate": {"behavior": "flat", "params": {"unit_fee": {"value": value, "period": "year"}}},
        "cost": {"kind": "none", "params": {}},
    }


def _flat_annual(value=120_000.0):
    return {
        "basis": "flat",
        "driver": {"source": "constant", "trajectory": "flat", "params": {}},
        "rate": {"behavior": "flat", "params": {"flat_amount": {"value": value, "period": "year"}}},
        "cost": {"kind": "none", "params": {}},
    }


def main():
    P = F = 0

    def ck(n, c, d=""):
        nonlocal P, F
        if c:
            P += 1
            print(f"  PASS  {n}")
        else:
            F += 1
            print(f"  FAIL  {n}  {d}")

    # 1) Preserve the independently-verified pre-change arithmetic reference.
    legacy_flows = [
        ("custody", _bal_derived(rate=0.0020), AUC * 0.0020),
        ("settlement legacy balance workaround", _bal_derived(mult=4.0, rate=0.0005), AUC * 4.0 * 0.0005),
        ("reserve", _bal_derived(pct=0.10, rate=0.0025), AUC * 0.10 * 0.0025),
        ("conversion legacy balance workaround", _bal_derived(pct=0.24, rate=0.0050), AUC * 0.24 * 0.0050),
    ]
    for name, st, exp in legacy_flows:
        q = _annual(st, 4)
        m = _annual(st, 12)
        ck(f"{name}: hand-calc == quarterly annual (${exp:,.0f})", abs(q - exp) < 1, f"got {q:,.0f}")
        ck(f"{name}: cadence-stable (quarterly == monthly)", abs(q - m) < 1, f"q={q:,.0f} m={m:,.0f}")

    # 2) New explicit natural-period flow semantics: transaction basis, annual coefficient.
    settlement = _tx_flow(kind="multiple", value=4.0, period="year", per_unit=0.0005)
    conversion = _tx_flow(kind="pct", value=0.24, period="year", per_unit=0.0050)
    for name, st, exp in [
        ("settlement natural-period transaction", settlement, AUC * 4.0 * 0.0005),
        ("conversion natural-period transaction", conversion, AUC * 0.24 * 0.0050),
    ]:
        q = _annual(st, 4)
        m = _annual(st, 12)
        ck(f"{name}: hand-calc exact", abs(q - exp) < 1, f"got {q:,.0f}")
        ck(f"{name}: quarterly == monthly (no cadence multiplication)", abs(q - m) < 1, f"q={q:,.0f} m={m:,.0f}")

    # 3) Absence of the marker freezes legacy raw-per-engine-period transaction behavior.
    legacy_tx = {
        "basis": "transaction",
        "driver": {"source": "managed_notional", "trajectory": "derived", "params": {"multiple": 4.0}},
        "rate": {"behavior": "flat", "params": {"per_unit": 0.0005}},
        "cost": {"kind": "none", "params": {}},
    }
    ck("legacy transaction multiple remains raw per engine period when coefficient marker is absent",
       abs(_annual(legacy_tx, 4) - AUC * 4.0 * 0.0005 * 4) < 1
       and abs(_annual(legacy_tx, 12) - AUC * 4.0 * 0.0005 * 12) < 1)

    # 4) Account / flat natural units.
    retainer = _account_annual()
    escrow = _flat_annual()
    for name, st, exp in [
        ("trustee retainer $12k/mandate/year x10", retainer, 120_000.0),
        ("escrow add-on $120k/year", escrow, 120_000.0),
    ]:
        q = _annual(st, 4)
        m = _annual(st, 12)
        ck(f"{name}: natural annual entry is correct", abs(q - exp) < 1, f"q={q:,.0f}")
        ck(f"{name}: cadence-stable", abs(q - m) < 1, f"q={q:,.0f} m={m:,.0f}")

    # 5) Explicit annual coefficient trajectory: turns can ramp then normalize.
    turns = _tx_flow(kind="multiple", value=1.5, period="year", per_unit=0.0005,
                     trajectory="explicit_schedule", schedule={"1": 1.5, "2": 2.4, "3": 3.2, "4": 2.8})
    for yr, mult in [(1, 1.5), (2, 2.4), (3, 3.2), (4, 2.8)]:
        exp = AUC * mult * 0.0005
        q = _annual(turns, 4, yr)
        m = _annual(turns, 12, yr)
        ck(f"turns schedule year {yr}: hand-calc exact", abs(q - exp) < 1, f"q={q:,.0f} exp={exp:,.0f}")
        ck(f"turns schedule year {yr}: quarterly == monthly", abs(q - m) < 1, f"q={q:,.0f} m={m:,.0f}")

    # 5b) Growth trajectory on the natural-period coefficient is cadence-stable.
    growing_turns = _tx_flow(kind="multiple", value=2.0, period="year", per_unit=0.0005,
                             trajectory="growth", growth_spec={"rate": 0.10, "period": "year", "method": "step", "anchor": "model_year"})
    for yr in (1, 2, 3):
        exp = AUC * 2.0 * (1.10 ** (yr - 1)) * 0.0005
        q = _annual(growing_turns, 4, yr); m = _annual(growing_turns, 12, yr)
        ck(f"coefficient growth year {yr}: hand-calc exact", abs(q-exp)<1, f"q={q:,.0f} exp={exp:,.0f}")
        ck(f"coefficient growth year {yr}: quarterly == monthly", abs(q-m)<1, f"q={q:,.0f} m={m:,.0f}")

    # 5c) The legacy periods_per_q=3 field is retired/ignored: cadence derives from ppy.
    legacy_account_landmine = {
        "basis": "account",
        "driver": {"source": "constant", "trajectory": "flat", "params": {"base": 10}},
        "rate": {"behavior": "flat", "params": {"fee_per_period": 1000.0, "periods_per_q": 3.0}},
        "cost": {"kind": "none", "params": {}},
    }
    laq=_annual(legacy_account_landmine,4); lam=_annual(legacy_account_landmine,12)
    ck("legacy periods_per_q no longer overrides cadence-derived account timing",
       abs(laq-120_000)<1 and abs(lam-120_000)<1, f"q={laq:,.0f} m={lam:,.0f}")

    # 6) Aggregate contract: all six streams in ONE product / ONE AUC context.
    product = {"fee_streams": [
        _bal_derived(rate=0.0020),
        settlement,
        _flat_annual(120_000.0),
        _account_annual(12_000.0, 10),
        _bal_derived(pct=0.10, rate=0.0025),
        conversion,
    ]}
    total_expected = 240_000 + 240_000 + 120_000 + 120_000 + 30_000 + 144_000
    pq = _product_annual(product, 4)
    pm = _product_annual(product, 12)
    ck("aggregate six-stream product == hand-calculated $894k", abs(pq - total_expected) < 1, f"got {pq:,.0f}")
    ck("aggregate six-stream product cadence-stable", abs(pq - pm) < 1, f"q={pq:,.0f} m={pm:,.0f}")

    # 7) Structural double-periodization guard: a natural-period coefficient is a FLOW
    # contract and must not be fed through balance basis (which annualizes stock rates itself).
    bad_double = _bal_derived(rate=0.0005)
    bad_double["driver"]["params"] = {"coefficient": {"kind": "multiple", "value": 4.0, "period": "year"}}
    try:
        fee_stream_q(bad_double, 1, dict(CTX), 12)
        raised = False
    except ValueError:
        raised = True
    ck("natural-period coefficient on balance basis fails closed (prevents /ppy^2)", raised)

    # 8) Unsupported schema fails closed at execution, not silent-zero/flat fallback.
    bad_cases = [
        {"basis": "nonesuch"},
        {"basis": "flat", "driver": {"source": "nonesuch"}},
        {"basis": "flat", "driver": {"source": "constant", "trajectory": "nonesuch"}},
        {"basis": "flat", "rate": {"behavior": "nonesuch"}},
        {"basis": "flat", "cost": {"kind": "nonesuch"}},
        {"basis": "account", "rate": {"behavior": "annual_change", "params": {"rate": 0.01}}},
        {"basis": "transaction", "rate": {"behavior": "scheduled", "params": {"schedule": {"1": 0.01}}}},
        {"basis": "balance", "cost": {"kind": "per_unit", "params": {"cost_per_unit": 1.0}}},
    ]
    fail_closed = True
    for st in bad_cases:
        try:
            fee_stream_q(st, 1, {}, 4)
            fail_closed = False
        except ValueError:
            pass
    ck("unsupported fee schema and unsupported basis/rate/cost combinations fail closed", fail_closed)

    # 9) Public configuration validation also fails closed before a run.
    import copy, json
    from foundry.v2.validate_q import validate_config_v2, ConfigErrorV2
    cfg = json.load(open("foundry/fixtures/universal_template_bank.json"))
    badcfg = copy.deepcopy(cfg)
    badcfg["assumptions"].setdefault("obs_exposures", []).append({
        "name":"Bad fee","managed_notional":{"day1":1.0,"trajectory":"flat"},
        "fee_streams":[{"basis":"nonesuch"}]})
    try:
        validate_config_v2(badcfg); validation_raised=False
    except ConfigErrorV2:
        validation_raised=True
    ck("configuration validator rejects unsupported fee schema before execution", validation_raised)

    print(f"\n{P} passed, {F} failed")
    return 0 if F == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
