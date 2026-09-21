from foundry.v2.trust_peer import METRICS, clean_certs, quarterize, registry_payload


def test_no_client_cohort_ships_in_registry():
    payload = registry_payload()
    assert "institutions" not in payload
    assert "certs" not in payload
    assert payload["cohort_contract"]["ownership"] == "engagement"


def test_clean_certs_deduplicates_and_rejects_noise():
    assert clean_certs([12345, "12345", " 67890 ", "name", -1, None]) == [12345, 67890]


def test_metric_registry_owns_definitions():
    assert METRICS["efficiency"]["quarterly_rule"] == "ratio_recompute"
    assert METRICS["assets"]["quarterly_rule"] == "quarter_end"


def test_quarterize_stock_flow_and_partial():
    assert [x["value"] for x in quarterize([1, 2, 3, 4, 5, 6], 2028, 1, "quarter_end")] == [3, 6]
    assert [x["value"] for x in quarterize([1, 2, 3, 4], 2028, 1, "sum")] == [6, 4]
    assert quarterize([1, 2, 3, 4], 2028, 1, "sum")[1]["partial"] is True


def test_monthly_ratio_is_refused():
    try:
        quarterize([1, 2, 3], 2028, 1, "ratio_recompute")
    except ValueError as e:
        assert "numerator and denominator" in str(e)
    else:
        raise AssertionError("monthly ratio should not be averaged")
