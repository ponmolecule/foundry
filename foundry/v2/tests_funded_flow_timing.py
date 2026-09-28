"""Run with python -m foundry.v2.tests_funded_flow_timing."""
import copy
import json

from .loan_balance import normalize_linked_loan_balance, resolve_linked_loan_balance
from .engine_q_a import run_pf_a
from .validate_q import validate_errors_v2
from .parity import run_parity
from .audit_workbook import _product_rows


def base():
    cfg = json.load(open("foundry/fixtures/core_bank_test_base.json"))
    a = cfg["assumptions"]
    p = copy.deepcopy(a["lending_products"][0])
    p.update(name="Timing test", opening_balance=0, balance_mode="funded_flow_level",
             structure="revolving", mortgage_banking=None, rate_type="fixed",
             yield_ann=.12, fee_yield_ann=0, charge_off_ann=0, runoff_per_period=0,
             funded_flow_driver={"source": "entered", "input_stage": "source_activity",
                 "start_period": 13, "ramp_periods": 6, "take_up_share": .2,
                 "flow_path": {"unit_kind": "money_flow", "period": "month",
                               "trajectory": "flat", "value": 120}},
             term_days=7, day_count=365, reserve_share=.005,
             target_retention_share=1, interest_balance_measure="period_end")
    a["lending_products"] = [p]
    return cfg, p


def check_error(fn, phrase):
    try:
        fn()
    except ValueError as e:
        assert phrase in str(e), str(e)
    else:
        raise AssertionError(f"expected {phrase}")


def main():
    cfg, p = base()
    a = cfg["assumptions"]
    r = resolve_linked_loan_balance(p, a, {}, 18, 12)
    assert r["source_activity"] == [120] * 18  # not overwritten by launch timing
    assert r["funded_volume"][:12] == [0] * 12
    assert r["funded_volume"][12:18] == [4, 8, 12, 16, 20, 24]
    assert abs(r["ending_balance"][12] - 4 * 12 * 7 / 365 * .995) < 1e-12

    # A linked upstream flow can exist before the product starts. It remains
    # available upstream and is gated only in this lending product.
    a["obs_exposures"][0].setdefault("fee_streams", []).append({
        "name": "Upstream TPV", "quantity_series_id": "tpv-1", "basis": "transaction",
        "driver": {"source": "constant", "params": {"flow_path": {
            "unit_kind": "money_flow", "period": "month", "trajectory": "flat", "value": 120}}},
        "rate": {"behavior": "flat", "params": {"pricing_basis": "pct_of_throughput", "per_unit": 0}}})
    p["funded_flow_driver"] = {"source": "fee_stream_quantity", "series_id": "tpv-1",
        "input_stage": "source_activity", "start_period": 13,
        "ramp_periods": 6, "take_up_share": .2}
    linked = resolve_linked_loan_balance(p, a, {}, 18, 12,
                                         fee_stream_quantities={"tpv-1": [120] * 18})
    assert linked["funded_volume"] == r["funded_volume"]
    p["funded_flow_driver"]["start_period"] = 14
    shifted = resolve_linked_loan_balance(p, a, {}, 18, 12,
                                          fee_stream_quantities={"tpv-1": [120] * 18})
    assert shifted["source_activity"] == linked["source_activity"]
    assert shifted["funded_volume"][12:15] == [0, 4, 8]
    p["funded_flow_driver"]["input_stage"] = "funded_volume"
    p["funded_flow_driver"]["ramp_periods"] = 1
    p["funded_flow_driver"]["take_up_share"] = 1
    check_error(lambda: resolve_linked_loan_balance(p, a, {}, 18, 12,
                fee_stream_quantities={"tpv-1": [120] * 18}),
                "nonzero in model period 1 before start_period 14")

    # A final funded-volume path is already post take-up/ramp. Its nonzero
    # prelaunch values are a validation error, never silently dropped.
    p["funded_flow_driver"] = {"source": "entered", "input_stage": "funded_volume",
        "start_period": 13, "flow_path": {"unit_kind": "money_flow",
        "period": "month", "trajectory": "flat", "value": 120}}
    check_error(lambda: resolve_linked_loan_balance(p, a, {}, 18, 12),
                "nonzero in model period 1 before start_period 13")
    assert validate_errors_v2(cfg)
    schedule = {str(i): (0 if i < 13 else 4 * (i - 12)) for i in range(1, 19)}
    p["funded_flow_driver"]["flow_path"].update(trajectory="explicit_schedule", schedule=schedule)
    final = resolve_linked_loan_balance(p, a, {}, 18, 12)
    assert final["funded_volume"] == r["funded_volume"]
    schedule["12"] = 1
    check_error(lambda: resolve_linked_loan_balance(p, a, {}, 18, 12),
                "nonzero in model period 12")
    schedule["12"] = 0

    # Same semantics at quarterly cadence: timing uses engine periods.
    p["funded_flow_driver"] = {"source": "entered", "input_stage": "source_activity",
        "start_period": 3, "ramp_periods": 2, "take_up_share": .5,
        "flow_path": {"unit_kind": "money_flow", "period": "month",
                      "trajectory": "flat", "value": 120}}
    quarterly = resolve_linked_loan_balance(p, a, {}, 4, 4)
    assert quarterly["funded_volume"] == [0, 0, 90, 180]

    # Legacy r178/r181 drivers remain final funded volume with no timing gate.
    old = copy.deepcopy(p)
    old["funded_flow_driver"] = {"source": "entered", "flow_path": {
        "unit_kind": "money_flow", "period": "month", "trajectory": "flat", "value": 120}}
    assert resolve_linked_loan_balance(old, a, {}, 4, 4)["funded_volume"] == [360] * 4

    for key, bad, phrase in (("start_period", 0, "positive whole"),
                             ("start_period", 2.5, "positive whole"),
                             ("ramp_periods", 0, "positive whole"),
                             ("take_up_share", 1.1, "share in [0, 1]"),
                             ("input_stage", "unknown", "input_stage")):
        invalid = copy.deepcopy(p)
        invalid["funded_flow_driver"][key] = bad
        check_error(lambda: normalize_linked_loan_balance(invalid, a), phrase)
    p["funded_flow_driver"].update(input_stage="funded_volume", ramp_periods=2)
    check_error(lambda: normalize_linked_loan_balance(p, a), "already includes take-up and ramp")

    # Fee and balance use the transformed funded volume, not upstream activity.
    live, lp = base()
    live["assumptions"]["periods_per_year"] = 12
    live["assumptions"]["capital_raises"] = []
    lp["funded_flow_driver"].update(start_period=3, ramp_periods=2)
    lp["fee_streams"] = [{"name": "Flow fee", "basis": "transaction",
        "driver": {"source": "product_funded_flow", "params": {}},
        "rate": {"behavior": "flat", "params": {"pricing_basis": "pct_of_throughput",
            "per_unit": .1}}, "cost": {"kind": "none", "params": {}}}]
    assert not validate_errors_v2(live), validate_errors_v2(live)
    product = next(x for x in run_pf_a(live)["products"] if x["name"] == "Timing test")
    assert product["fundedInputVolume"][:4] == [120] * 4
    assert product["fundedVolume"][:4] == [0, 0, 12, 24]
    assert all(abs(x-y) < 1e-9 for x,y in zip(product["fees"][:4], [0, 0, 1.2, 2.4]))
    assert product["bal"][1] == product["bal"][2] == 0
    assert product["fundedStartPeriod"] == 3
    public = next(x for x in run_parity(live)["products"] if x["name"] == "Timing test")
    assert public["fundedInputVolume"][:4] == [0.12] * 4  # $000s
    assert public["fundedVolume"][:4] == [0, 0, .01, .02]  # public rounding
    rows = _product_rows(run_parity(live), 12, exact=run_pf_a(live))
    assert any(row[2] == "fundedInputVolume" and row[4][:4] == [.12] * 4 for row in rows)

    html = open("web/console_v2.html").read()
    for token in ("Input represents", "Starts in model", "Take-up share", "to full size",
                  "Final funded volume · already includes take-up and ramp"):
        assert token in html
    print("PASS funded-flow timing suite")


if __name__ == "__main__":
    main()
