"""Regression tests for customer-Series-driven loan balances.

Run: python3 -m foundry.v2.tests_linked_loan_balance
"""
import copy
import json

from .engine_q_a import run_pf_a
from .loan_balance import normalize_linked_loan_balance, resolve_linked_loan_balance


def _close(a, b, tol=1e-8):
    return abs(float(a) - float(b)) <= tol


def _cfg():
    cfg = json.load(open("foundry/fixtures/core_bank_test_base.json"))
    a = cfg["assumptions"]
    a["cac_feeds"] = {"ubl": {
        "series_id": "cac-ubl-auc", "customer_count_series_id": "cac-ubl-mab",
        "beginning_customers": 100, "beginning_auc": 0,
        "attrition_rate": 0, "channels": [],
    }}
    p = copy.deepcopy(a["lending_products"][0])
    p.update({
        "name": "Unsecured business loans", "opening_balance": 0,
        "balance_mode": "linked_customer_level", "structure": "revolving",
        "mortgage_banking": None, "rate_type": "fixed", "yield_ann": .12,
        "runoff_per_period": 0, "charge_off_ann": 0,
        "reserve_rate_pct_bal": .01,
        "balance_driver": {
            "source": "customer_acquisition_count", "series_id": "cac-ubl-mab",
            "measure": "period_end",
            "average_balance_per_customer_spec": {
                "source": "entered", "trajectory": "flat", "value": 100_000,
            },
        },
    })
    a["lending_products"] = [p]
    return cfg


def main():
    cfg = _cfg()
    out = run_pf_a(copy.deepcopy(cfg))
    p = next(x for x in out["products"] if x["name"] == "Unsecured business loans")
    assert p["balanceMode"] == "linked_customer_level"
    assert p["balanceDriverCount"] == [100.0] * 12
    assert p["averageBalancePerCustomer"] == [100_000.0] * 12
    assert p["linkedBalanceTarget"] == [10_000_000.0] * 12
    assert p["bal"][1:] == [10_000_000.0] * 12
    assert _close(p["avg"][0], 5_000_000) and _close(p["avg"][1], 10_000_000)
    assert _close(p["interest"][0], 150_000) and _close(p["interest"][1], 300_000)
    assert _close(p["origq"][0], 10_000_000) and _close(p["origq"][1], 0)
    assert p["alll"] == [100_000.0] * 12

    # Explicit average lending is a level Series and resolves at the engine cadence.
    prod = cfg["assumptions"]["lending_products"][0]
    prod["balance_driver"]["average_balance_per_customer_spec"] = {
        "source": "entered", "trajectory": "explicit", "cadence": "year",
        "values": [100_000, 120_000], "extend": "hold", "resolution": "step",
    }
    counts = {"cac-ubl-mab": {"period_end": [100] * 8, "period_average": [90] * 8}}
    resolved = resolve_linked_loan_balance(prod, cfg["assumptions"], counts, 8, 4)
    assert resolved["ending_balance"] == [10_000_000.0] * 4 + [12_000_000.0] * 4

    # Period-average MAB is an explicit choice, not an implicit reinterpretation.
    prod["balance_driver"]["measure"] = "period_average"
    resolved = resolve_linked_loan_balance(prod, cfg["assumptions"], counts, 8, 4)
    assert resolved["ending_balance"][:4] == [9_000_000.0] * 4

    # Legacy products remain byte-for-byte equivalent when the default mode is stated.
    legacy = json.load(open("foundry/fixtures/core_bank_test_base.json"))
    before = run_pf_a(copy.deepcopy(legacy))
    for loan in legacy["assumptions"]["lending_products"]:
        loan["balance_mode"] = "rollforward"
    after = run_pf_a(copy.deepcopy(legacy))
    assert before == after

    # Invalid links and incompatible mechanics fail closed.
    bad = copy.deepcopy(cfg["assumptions"]["lending_products"][0])
    bad["balance_driver"]["series_id"] = "missing"
    try:
        normalize_linked_loan_balance(bad, cfg["assumptions"])
        raise AssertionError("missing customer Series was accepted")
    except ValueError:
        pass
    bad = copy.deepcopy(cfg["assumptions"]["lending_products"][0])
    bad["structure"] = "term"
    try:
        normalize_linked_loan_balance(bad, cfg["assumptions"])
        raise AssertionError("linked term-cohort loan was accepted")
    except ValueError:
        pass

    html = open("web/console_v2.html").read()
    for token in ("Balance authoring", "MAB Series × average lending / MAB",
                  "Customer-count measure", "Average lending / MAB", "$000s / unit"):
        assert token in html
    print("PASS linked loan balance suite")


if __name__ == "__main__":
    main()
