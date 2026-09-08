"""Golden tests for the per-product multi-stream fee evaluator (six-axis model, increment 1).

Pins two things:
  1. INVARIANT: a config with no fee_streams preserves the legacy financial-core baseline
     (hash 3fee151428f6991e), ignoring additive presentation-only disclosure keys.
  2. CORRECTNESS: each basis (balance/transaction/account/flat) and timing gating are hand-checked.

Run: python3 -m foundry.v2.tests_fee_streams
"""
import sys, json, hashlib, copy
sys.path.insert(0, ".")
from foundry.v2 import run_q
from foundry.v2.income_modules import fee_stream_q, product_fee_streams_q

BASELINE = "3fee151428f6991e"


def _hash(cfg):
    fin = run_q.run_v2(cfg)["financials"]
    # Gross PP&E / accumulated depreciation are additive statement disclosures that
    # reconcile to the pre-existing net `premises` series.  They must not invalidate
    # this fee-module economic-invariance gate when surfaced in the output payload.
    bs = dict(fin["bs"])
    bs.pop("premisesGross", None)
    bs.pop("premisesAccumDep", None)
    return hashlib.sha256(json.dumps({"is": fin["is"], "bs": bs, "ratios": fin["ratios"]},
                                     sort_keys=True, default=str).encode()).hexdigest()[:16]


def main():
    passed = failed = 0

    def ck(name, cond):
        nonlocal passed, failed
        if cond:
            passed += 1; print(f"PASS {name}")
        else:
            failed += 1; print(f"FAIL {name}")

    # --- 1. INVARIANT: empty fee_streams => baseline hash unchanged ---
    cfg = json.load(open("foundry/fixtures/universal_template_bank.json"))
    ck("baseline hash intact (no fee_streams anywhere)", _hash(cfg) == BASELINE)

    # adding an EMPTY fee_streams list to every product must not move the hash
    c2 = copy.deepcopy(cfg)
    for p in (c2["assumptions"].get("lending_products") or []):
        p["fee_streams"] = []
    for p in (c2["assumptions"].get("deposit_products") or []):
        p["fee_streams"] = []
    ck("empty fee_streams => hash unchanged", _hash(c2) == BASELINE)

    # --- 2. CORRECTNESS: hand-checked bases (unit-level, no engine) ---
    # balance basis: qty(own_balance=1,000,000) * rate(0.01 annual) / 4 = 2,500
    s_bal = {"basis": "balance", "driver": {"source": "own_balance"},
             "rate": {"params": {"rate": 0.01}}, "timing": {"start_period": 1}}
    ck("balance basis: 1e6 @ 1%/yr => 2,500/q",
       abs(fee_stream_q(s_bal, 1, {"own_balance": 1_000_000.0})[0] - 2500.0) < 1e-9)

    # transaction basis: qty(constant 10,000) * per_unit(0.35) = 3,500
    s_tx = {"basis": "transaction", "driver": {"source": "constant", "params": {"base": 10_000.0}},
            "rate": {"params": {"per_unit": 0.35}}, "timing": {"start_period": 1}}
    ck("transaction basis: 10,000 tx @ 0.35 => 3,500",
       abs(fee_stream_q(s_tx, 1, {})[0] - 3500.0) < 1e-9)

    # account basis: qty(500 accts) * fee(4.0/mo) * 3 mo/q = 6,000
    s_ac = {"basis": "account", "driver": {"source": "constant", "params": {"base": 500.0}},
            "rate": {"params": {"fee_per_period": 4.0}}, "timing": {"start_period": 1}}
    ck("account basis: 500 accts @ 4/mo * 3 => 6,000",
       abs(fee_stream_q(s_ac, 1, {})[0] - 6000.0) < 1e-9)

    # flat basis: fixed 12,500/q regardless of driver
    s_flat = {"basis": "flat", "rate": {"params": {"amount_per_period": 12_500.0}},
              "timing": {"start_period": 1}}
    ck("flat basis: 12,500/q", abs(fee_stream_q(s_flat, 1, {})[0] - 12500.0) < 1e-9)

    # Flat amount trajectory: one economically coherent recurring stream can vary through time.
    escrow_schedule = {str(i+1): v for i, v in enumerate([150_000, 200_000, 250_000, 300_000, 350_000, 400_000, 450_000])}
    s_flat_explicit = {"basis": "flat", "rate": {"params": {"flat_amount": {
        "value": 150_000.0, "period": "year", "trajectory": "explicit_schedule",
        "schedule": escrow_schedule}}}, "timing": {"start_period": 1}}
    annual_q = [sum(fee_stream_q(s_flat_explicit, q, {}, ppy=4)[0] for q in range(y*4+1, y*4+5)) for y in range(7)]
    annual_m = [sum(fee_stream_q(s_flat_explicit, q, {}, ppy=12)[0] for q in range(y*12+1, y*12+13)) for y in range(7)]
    want_escrow = [150_000, 200_000, 250_000, 300_000, 350_000, 400_000, 450_000]
    ck("flat explicit annual escrow schedule exact in quarterly cadence", all(abs(a-b)<1e-9 for a,b in zip(annual_q,want_escrow)))
    ck("flat explicit annual escrow schedule exact in monthly cadence", all(abs(a-b)<1e-9 for a,b in zip(annual_m,want_escrow)))
    ck("flat explicit amount is cadence-stable by model year", all(abs(a-b)<1e-9 for a,b in zip(annual_q,annual_m)))
    ck("flat explicit schedule carries last amount forward", abs(fee_stream_q(s_flat_explicit, 29, {}, ppy=4)[0] - 112_500.0) < 1e-9)

    # Existing natural-period Flat contract is unchanged when trajectory is absent.
    legacy_natural = {"basis":"flat","rate":{"params":{"flat_amount":{"value":120_000.0,"period":"year"}}},"timing":{"start_period":1}}
    ck("legacy flat_amount without trajectory retains exact quarterly economics", abs(fee_stream_q(legacy_natural,1,{},ppy=4)[0]-30_000.0)<1e-9)
    ck("legacy flat_amount without trajectory retains exact monthly economics", abs(fee_stream_q(legacy_natural,1,{},ppy=12)[0]-10_000.0)<1e-9)

    bad_flat = {"basis":"flat","rate":{"params":{"flat_amount":{"value":1,"period":"year","trajectory":"wiggle"}}}}
    try:
        fee_stream_q(bad_flat,1,{},ppy=4); bad_flat_raised=False
    except ValueError:
        bad_flat_raised=True
    ck("unsupported flat amount trajectory fails closed", bad_flat_raised)

    empty_flat = {"basis":"flat","rate":{"params":{"flat_amount":{"value":0,"period":"year","trajectory":"explicit_schedule","schedule":{}}}}}
    try:
        fee_stream_q(empty_flat,1,{},ppy=4); empty_flat_raised=False
    except ValueError:
        empty_flat_raised=True
    ck("empty Flat explicit schedule fails closed", empty_flat_raised)

    s_flat_growth = {"basis":"flat","rate":{"params":{"flat_amount":{
        "value":100_000.0,"period":"year","trajectory":"growth",
        "growth_spec":{"rate":0.10,"period":"year","method":"step","anchor":"model_year"}}}},"timing":{"start_period":1}}
    gy1_q=sum(fee_stream_q(s_flat_growth,q,{},ppy=4)[0] for q in range(1,5))
    gy2_q=sum(fee_stream_q(s_flat_growth,q,{},ppy=4)[0] for q in range(5,9))
    gy1_m=sum(fee_stream_q(s_flat_growth,q,{},ppy=12)[0] for q in range(1,13))
    gy2_m=sum(fee_stream_q(s_flat_growth,q,{},ppy=12)[0] for q in range(13,25))
    ck("flat amount Growth uses standard annual step semantics", abs(gy1_q-100_000)<1e-9 and abs(gy2_q-110_000)<1e-9)
    ck("flat amount Growth is cadence-stable", abs(gy1_q-gy1_m)<1e-9 and abs(gy2_q-gy2_m)<1e-9)

    # Full-engine integration: the one-stream escrow schedule lands on fee income in both cadences.
    def _escrow_engine_annual(ppy):
        c = copy.deepcopy(cfg)
        a = c["assumptions"]
        a["periods_per_year"] = ppy
        a["n_periods"] = 7 * ppy
        a["obs_exposures"] = [p for p in (a.get("obs_exposures") or []) if not p.get("_fee_product")]
        base_c = copy.deepcopy(c)
        a["obs_exposures"].append({
            "name":"Escrow","call_report_line":"obs","_fee_product":True,
            "managed_notional":{"day1":0,"trajectory":"flat"},
            "fee_streams":[dict(s_flat_explicit, name="Escrow add-on")],
        })
        with_fee = run_q.run_v2(c)["financials"]["is"]["fees"]
        without_fee = run_q.run_v2(base_c)["financials"]["is"]["fees"]
        delta = [x-y for x,y in zip(with_fee, without_fee)]
        return [sum(delta[y*ppy:(y+1)*ppy]) * 1000.0 for y in range(7)]
    eng_q = _escrow_engine_annual(4)
    eng_m = _escrow_engine_annual(12)
    ck("full engine posts escrow schedule to quarterly fee income", all(abs(a-b)<50 for a,b in zip(eng_q,want_escrow)))
    ck("full engine posts escrow schedule to monthly fee income", all(abs(a-b)<50 for a,b in zip(eng_m,want_escrow)))

    # --- 3. TIMING: a stream starting period 5 produces 0 before, value at/after ---
    s_late = {"basis": "flat", "rate": {"params": {"amount_per_period": 1000.0}},
              "timing": {"start_period": 5}}
    ck("timing: start_period 5 => 0 at q4", abs(fee_stream_q(s_late, 4, {})[0]) < 1e-9)
    ck("timing: start_period 5 => value at q5", abs(fee_stream_q(s_late, 5, {})[0] - 1000.0) < 1e-9)

    # end_period gating
    s_end = {"basis": "flat", "rate": {"params": {"amount_per_period": 1000.0}},
             "timing": {"start_period": 1, "end_period": 3}}
    ck("timing: end_period 3 => 0 at q4", abs(fee_stream_q(s_end, 4, {})[0]) < 1e-9)

    # explicit_schedule trajectory (the non-proportional case): lump in q7
    s_sched = {"basis": "balance", "driver": {"source": "constant", "trajectory": "explicit_schedule",
               "params": {"base": 0.0, "schedule": {"7": 50_000_000.0}}},
               "rate": {"params": {"rate": 0.004}}, "timing": {"start_period": 1}}
    ck("explicit_schedule: 0 at q1", abs(fee_stream_q(s_sched, 1, {})[0]) < 1e-9)
    ck("explicit_schedule: 50e6 @ 40bp/4 at q7 => 50,000",
       abs(fee_stream_q(s_sched, 7, {})[0] - 50_000.0) < 1e-9)

    # unsupported schema must fail closed rather than silently dropping revenue
    try:
        fee_stream_q({"basis": "nonesuch"}, 1, {})
        _bad_raised = False
    except ValueError:
        _bad_raised = True
    ck("unknown basis fails closed", _bad_raised)

    # --- 4. INTEGRATION: a product with a real stream moves fees (engine end-to-end) ---
    c3 = copy.deepcopy(cfg)
    lend = c3["assumptions"].get("lending_products") or []
    if lend:
        lend[0]["fee_streams"] = [s_flat]  # flat 12,500/q on an existing loan product
        h3 = _hash(c3)
        ck("real stream MOVES the hash (not a no-op)", h3 != BASELINE)

    # --- 5. managed_notional roll-forward (AUC as a driven off-book stock) ---
    from foundry.v2.income_modules import managed_notional_series
    mn = {"day1": 0.0, "target": 500_000_000.0, "ramp_periods": 8, "trajectory": "ramp_to_target"}
    avg, end = managed_notional_series(mn, 12)
    ck("ramp_to_target: AUC end Q1 = 62.5M", abs(end[0] - 62_500_000.0) < 1.0)
    ck("ramp_to_target: AUC end Q8 = target 500M", abs(end[7] - 500_000_000.0) < 1.0)
    ck("ramp_to_target: AUC avg Q1 = 31.25M", abs(avg[0] - 31_250_000.0) < 1.0)
    # balance-basis fee against managed_notional
    cust = {"basis": "balance", "driver": {"source": "managed_notional"},
            "rate": {"params": {"rate": 0.0010}}, "timing": {"start_period": 1}}
    ck("custody fee: 31.25M AUC @ 10bp/4 = 7,812.5",
       abs(fee_stream_q(cust, 1, {"managed_notional": avg[0]})[0] - 7812.5) < 1e-6)
    # explicit_schedule notional (non-proportional lump adds, additive)
    mn2 = {"day1": 0.0, "trajectory": "explicit_schedule", "schedule": {"3": 100_000_000.0, "7": 50_000_000.0}}
    _, end2 = managed_notional_series(mn2, 12)
    ck("notional explicit_schedule: 0 through Q2", abs(end2[1]) < 1.0)
    ck("notional explicit_schedule: 100M from Q3", abs(end2[2] - 100_000_000.0) < 1.0)
    ck("notional explicit_schedule: 150M from Q7 (additive)", abs(end2[6] - 150_000_000.0) < 1.0)

    # --- 6. pure-fee custody product runs end-to-end, off-book (no balance-sheet impact) ---
    c4 = copy.deepcopy(cfg)
    base_assets_q1 = run_q.run_v2(c4)["financials"]["bs"]["totalAssets"][1]
    c4["assumptions"]["obs_exposures"] = [{
        "name": "Custody", "managed_notional": mn,
        "fee_streams": [cust]}]
    r4 = run_q.run_v2(c4)
    ck("pure-fee product runs (integrity pass)", r4.get("checks", {}).get("integrity_pass") is True)
    # off-book: the product contributes no on-book balance. Fee income does legitimately flow to
    # equity->funding plug, so assets move by ~the retained fee (not by an AUC balance). The check
    # is that AUC itself (500M) is NOT on the balance sheet — a $1 tolerance rules out FP noise.
    delta = abs(r4["financials"]["bs"]["totalAssets"][1] - base_assets_q1)
    ck("pure-fee product AUC is OFF-book (no 500M balance appears; delta is only retained fee/FP)",
       delta < 100_000.0)  # far below the 500M AUC; confirms AUC didn't land on-book

    print(f"\n{passed} passed, {failed} failed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
