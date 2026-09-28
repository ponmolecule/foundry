"""Run with python -m foundry.v2.tests_loan_allocation."""
import copy
import json

from .engine_q_a import run_pf_a
from .loan_allocation import allocate_loan_levels
from .validate_q import validate_errors_v2
from .parity import run_parity
from .audit_workbook import _product_rows
from .audit_workbook import calculation_audit_workbook
from .run_q import run_v2


def main():
    c = json.load(open("foundry/fixtures/core_bank_test_base.json"))
    a = c["assumptions"]
    base = copy.deepcopy(a["lending_products"][0])
    a["lending_products"] = []
    for name, target in (("Loan A", 100_000), ("Loan B", 300_000)):
        p = copy.deepcopy(base)
        p.update(name=name, opening_balance=0, structure="revolving",
                 mortgage_banking=None, runoff_per_period=0, charge_off_ann=0,
                 balance_mode="explicit_level", allocation_group_id="credit_cap",
                 allocation_target_id="credit-"+name.lower().replace(' ', '-'),
                 interest_balance_measure="period_end", rate_type="fixed",
                 yield_ann=.12, fee_yield_ann=0, ending_balance_spec={"source": "entered",
                 "trajectory": "flat", "value": target})
        a["lending_products"].append(p)
    a["loan_allocation_groups"] = [{"id": "credit_cap", "cap_source": "entered",
        "cap_spec": {"source": "entered", "trajectory": "flat", "value": 200_000}}]
    assert not validate_errors_v2(c), validate_errors_v2(c)
    out = run_pf_a(copy.deepcopy(c))
    group = out["loan_allocation_groups"]["credit_cap"]
    assert group["factor"] == [.5] * 12
    loans = {p["name"]: p for p in out["products"] if p["family"] == "lending"}
    assert loans["Loan A"]["bal"][1] == 50_000
    assert loans["Loan B"]["bal"][1] == 150_000
    assert loans["Loan A"]["distributedBalance"][0] == 50_000
    assert loans["Loan B"]["distributedBalance"][0] == 150_000
    assert loans["Loan A"]["interest"][0] == 1_500
    assert loans["Loan B"]["interest"][0] == 4_500
    four = copy.deepcopy(c)
    for name, target in (("Loan C", 100_000), ("Loan D", 100_000)):
        p = copy.deepcopy(four["assumptions"]["lending_products"][0])
        p.update(name=name, allocation_target_id="credit-"+name.lower().replace(' ', '-'),
                 ending_balance_spec={"source": "entered", "trajectory": "flat", "value": target})
        four["assumptions"]["lending_products"].append(p)
    four_out = run_pf_a(copy.deepcopy(four))
    assert abs(four_out["loan_allocation_groups"]["credit_cap"]["factor"][0] - 1 / 3) < 1e-12
    four["assumptions"]["lending_products"][0]["ending_balance_spec"]["value"] = 200_000
    shifted = run_pf_a(four)
    assert shifted["loan_allocation_groups"]["credit_cap"]["factor"][0] < 1 / 3
    assert (next(p for p in shifted["products"] if p["name"] == "Loan B")["bal"][1]
            < next(p for p in four_out["products"] if p["name"] == "Loan B")["bal"][1])
    a["lending_products"][0]["fee_streams"] = [
        {"name": "Funded volume fee", "basis": "transaction",
         "driver": {"source": "constant", "trajectory": "flat", "params": {
             "flow_path": {"unit_kind": "money_flow", "period": "month",
                           "trajectory": "flat", "value": 1_000_000}}},
         "rate": {"behavior": "flat", "params": {
             "pricing_basis": "pct_of_throughput", "per_unit": .002}},
         "cost": {"kind": "none", "params": {}}},
        {"name": "Distributed servicing", "basis": "balance",
         "driver": {"source": "distributed_balance", "trajectory": "flat", "params": {}},
         "rate": {"behavior": "flat", "params": {"rate_path": {"value": .12,
             "trajectory": "flat", "period": "year"}}},
         "cost": {"kind": "none", "params": {}}},
    ]
    fee_run = run_pf_a(copy.deepcopy(c))
    loan_a = next(p for p in fee_run["products"] if p["name"] == "Loan A")
    assert abs(loan_a["fees"][0] - 7_500) < 1e-8  # three monthly flows + quarterly servicing
    assert loan_a["bal"][1] == 50_000
    # Native-period funded volume derives a retained target, before the shared cap.
    a["lending_products"][1].update(balance_mode="funded_flow_level",
        funded_flow_driver={"source": "entered", "flow_path": {
            "unit_kind": "money_flow", "trajectory": "flat", "period": "month",
            "value": 1_000_000}}, term_days=30, day_count=365,
        reserve_share=0, target_retention_share=.5, charge_off_ann=.12,
        charge_off_balance_measure="period_end", allowance_mode="loss_rate_term",
        credit_loss_factor_spec={"source": "entered", "trajectory": "flat", "value": 2})
    a["lending_products"][1]["fee_streams"] = [{
        "name": "Funded facility fee", "basis": "transaction",
        "driver": {"source": "product_funded_flow", "trajectory": "flat", "params": {}},
        "rate": {"behavior": "flat", "params": {"pricing_basis": "pct_of_throughput",
            "per_unit": .002}}, "cost": {"kind": "none", "params": {}}}]
    a["loan_allocation_groups"][0]["cap_spec"]["value"] = 1_000_000
    derived = run_pf_a(copy.deepcopy(c))
    b = next(p for p in derived["products"] if p["name"] == "Loan B")
    expected = 3_000_000 * 4 * 30 / 365 * .5
    assert abs(b["fundedVolume"][0] - 3_000_000) < 1e-8
    assert abs(b["calculatedOutstanding"][0] - expected * 2) < 1e-8
    assert abs(b["bal"][1] - expected) < 1e-8
    assert abs(b["fees"][0] - 6_000) < 1e-8
    assert abs(b["co"][0] - expected * .12 * 2 / 4) < 1e-8
    assert abs(b["alll"][0] - expected * .12 * 2 * 30 / 365) < 1e-8
    public = run_parity(copy.deepcopy(c))
    assert public["loan_allocation_groups"]["credit_cap"]["factor"][0] == 1
    public_b = next(p for p in public["products"] if p["name"] == "Loan B")
    assert public_b["creditLossFactor"][0] == 2
    assert abs(public_b["fundedVolume"][0] - 3_000) < 1e-8
    audit = _product_rows(public, 12, exact=derived)
    assert any(row[0] == "Loan allocation · credit_cap" and row[2] == "factor"
               and row[4][0] == 1 for row in audit)
    assert any(row[0] == "lending · Loan B" and row[2] == "interestBasis"
               and "period_end" in row[1] for row in audit)
    # The same balance path can observe a stable upstream monetary fee-stream
    # quantity; changing the upstream flow then changes the loan exposure.
    a["obs_exposures"][0].setdefault("fee_streams", []).append({
        "name": "Upstream funded flow", "quantity_series_id": "upstream-flow-1",
        "basis": "transaction", "driver": {"source": "constant", "trajectory": "flat",
            "params": {"flow_path": {"unit_kind": "money_flow", "period": "month",
                "trajectory": "flat", "value": 1_000_000}}},
        "rate": {"behavior": "flat", "params": {"pricing_basis": "pct_of_throughput",
            "per_unit": 0}}, "cost": {"kind": "none", "params": {}}})
    a["lending_products"][1]["funded_flow_driver"] = {
        "source": "fee_stream_quantity", "series_id": "upstream-flow-1"}
    linked = run_pf_a(copy.deepcopy(c))
    b_linked = next(p for p in linked["products"] if p["name"] == "Loan B")
    assert b_linked["fundedVolume"] == b["fundedVolume"]
    assert b_linked["bal"] == b["bal"]
    a["obs_exposures"][0]["fee_streams"].pop()
    monthly = copy.deepcopy(c)
    monthly["assumptions"]["periods_per_year"] = 12
    monthly["assumptions"]["capital_raises"] = []
    monthly["assumptions"]["lending_products"][1]["funded_flow_driver"] = {
        "source": "entered", "flow_path": {"unit_kind": "money_flow",
            "period": "month", "trajectory": "flat", "value": 1_000_000}}
    monthly["assumptions"]["lending_products"][1]["reserve_share"] = .01
    monthly["assumptions"]["loan_allocation_groups"][0]["cap_spec"]["value"] = 2_000_000
    m = run_pf_a(monthly)
    m_loan = next(p for p in m["products"] if p["name"] == "Loan B")
    m_target = 1_000_000 * 12 * 30 / 365 * .99 * .5
    assert abs(m_loan["fundedVolume"][0] - 1_000_000) < 1e-8
    assert abs(m_loan["bal"][1] - m_target) < 1e-8
    assert abs(m_loan["interest"][0] - m_target * .12 / 12) < 1e-8
    assert abs(m_loan["fees"][0] - 2_000) < 1e-8
    rendered = run_v2(copy.deepcopy(monthly))
    rendered_b = next(p for p in rendered["products"] if p["name"] == "Loan B")
    assert abs(rendered_b["fundedVolume"][0] - 1_000) < 1e-8
    assert rendered["loan_allocation_groups"]["credit_cap"]["factor"][0] == 1
    workbook = calculation_audit_workbook(monthly, rendered)
    assert "Product Calculations" in workbook.sheetnames
    assert "Fee Stream Economics" in workbook.sheetnames
    a["lending_products"][1].pop("funded_flow_driver")
    for key in ("term_days", "day_count", "reserve_share", "target_retention_share",
                "charge_off_balance_measure", "allowance_mode", "credit_loss_factor_spec"):
        a["lending_products"][1].pop(key)
    a["lending_products"][1]["charge_off_ann"] = 0
    a["lending_products"][1]["balance_mode"] = "explicit_level"
    a["lending_products"][1].pop("fee_streams")
    a["loan_allocation_groups"][0]["cap_spec"]["value"] = 200_000
    a["lending_products"][0]["interest_balance_measure"] = "period_average"
    avg = run_pf_a(copy.deepcopy(c))
    first = next(p for p in avg["products"] if p["name"] == "Loan A")
    assert first["interest"][0] == 750
    a["loan_allocation_groups"][0]["cap_spec"]["value"] = -1
    assert validate_errors_v2(copy.deepcopy(c))
    try:
        run_pf_a(c)
    except ValueError:
        pass
    else:
        raise AssertionError("negative allocation cap accepted")
    assert allocate_loan_levels({"A": [0]}, [0])["factor"] == [1]
    invalid = copy.deepcopy(monthly)
    invalid["assumptions"]["lending_products"][1]["funded_flow_driver"] = {
        "source": "fee_stream_quantity", "series_id": "nonexistent"}
    assert validate_errors_v2(invalid)
    invalid = copy.deepcopy(monthly)
    invalid["assumptions"]["lending_products"][1]["reserve_share"] = 1.1
    assert validate_errors_v2(invalid)
    invalid = copy.deepcopy(monthly)
    invalid["assumptions"]["lending_products"][1]["funded_flow_driver"]["flow_path"].update(
        trajectory="explicit_schedule", schedule={"1": 1_000_000})
    try:
        run_pf_a(invalid)
    except ValueError as e:
        assert "missing source period 2" in str(e)
    else:
        raise AssertionError("incomplete funded-volume schedule accepted")
    print("PASS loan allocation suite")


if __name__ == "__main__":
    main()
