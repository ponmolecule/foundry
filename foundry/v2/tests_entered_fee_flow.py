"""Focused regression checks for entered monetary Transaction-driver paths."""
from copy import deepcopy

from .income_modules import fee_stream_q, product_fee_streams_q


def ck(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + ((" :: " + detail) if detail else ""))
    if not ok:
        raise AssertionError(name)


def source(schedule):
    return {
        "name": "Platform interchange revenue",
        "basis": "transaction",
        "driver": {"source": "constant", "trajectory": "explicit_schedule", "params": {
            "flow_path": {"unit_kind": "money_flow", "value": 0, "period": "month",
                          "trajectory": "explicit_schedule", "schedule": schedule}
        }},
        "rate": {"behavior": "flat", "params": {"pricing_basis": "pct_of_throughput", "per_unit": 0}},
        "cost": {"kind": "none", "params": {}},
    }


def migrated(shares):
    return {
        "name": "Bank interchange revenue",
        "basis": "transaction",
        "driver": {"source": "stream_ref", "ref": "Platform interchange revenue",
                   "trajectory": "derived", "params": {"coefficient": {
                       "kind": "pct", "semantics": "share", "value": 0, "period": "month",
                       "trajectory": "explicit_schedule", "schedule": shares}}},
        "rate": {"behavior": "flat", "params": {"pricing_basis": "pct_of_throughput", "per_unit": 1}},
        "cost": {"kind": "none", "params": {}},
    }


def main():
    a = {"1": 100_000, "2": 200_000, "3": 300_000, "4": 400_000}
    b = {"1": .10, "2": .20, "3": .30, "4": .40}
    s, m = source(a), migrated(b)
    m1 = product_fee_streams_q({"fee_streams": [deepcopy(s), deepcopy(m)]}, 1, {}, 12)[0]
    q1 = product_fee_streams_q({"fee_streams": [deepcopy(s), deepcopy(m)]}, 1, {}, 4)[0]
    q2 = product_fee_streams_q({"fee_streams": [deepcopy(s), deepcopy(m)]}, 2, {}, 4)[0]
    ck("monthly source is non-posting and downstream receives A1*B1", abs(m1 - 10_000) < 1e-9, str(m1))
    ck("quarterly cadence computes SUM(A_m*B_m), not SUM(A_m)*one B", abs(q1 - 140_000) < 1e-9, str(q1))
    ck("explicit schedules carry forward after their final month", abs(q2 - 480_000) < 1e-9, str(q2))
    neg = source({"1": -50_000})
    neg_val = product_fee_streams_q({"fee_streams": [neg, migrated({"1": .25})]}, 1, {}, 12)[0]
    ck("negative entered flow remains contra-revenue downstream", abs(neg_val + 12_500) < 1e-9, str(neg_val))

    rebate = migrated({"1": .25})
    rebate["name"] = "Issuing Subscriber Rebate"
    rebate["revenue_presentation"] = "contra_revenue"
    rebate_val = product_fee_streams_q({"fee_streams": [source({"1": 50_000}), rebate]}, 1, {}, 12)[0]
    ck("explicit contra-revenue presentation posts positive authored rebate as negative fee income",
       abs(rebate_val + 12_500) < 1e-9, str(rebate_val))

    econ = {}
    source_stream = source({"1": 50_000})
    source_stream["quantity_series_id"] = "platform-source"
    rebate["quantity_series_id"] = "subscriber-rebate"
    product_fee_streams_q({"fee_streams": [source_stream, rebate]}, 1,
                          {"capture_stream_economics": econ}, 12)
    rec = econ["subscriber-rebate"]
    ck("explicit contra stream audit separates contra amount from gross revenue",
       abs(rec["gross_fee_revenue"][0]) < 1e-9
       and abs(rec["contra_revenue"][0] - 12_500) < 1e-9
       and abs(rec["reported_fee_income"][0] + 12_500) < 1e-9, str(rec))


if __name__ == "__main__":
    main()
