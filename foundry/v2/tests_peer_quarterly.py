from foundry.v2.peer_quarterly import build_peer_quarters


def _fixture(ppy=12, years=7):
    n = ppy * years
    # Stock paths include opening; flows do not.
    assets = [100.0 + i for i in range(n + 1)]
    cash = [50.0 + i for i in range(n + 1)]
    zeros_stock = [0.0] * (n + 1)
    base = {
        "bs": {"totalAssets": assets, "cash": cash, "grossLoans": zeros_stock,
               "sec": zeros_stock, "afsBook": zeros_stock, "htmBook": zeros_stock},
        "is": {"ni": [1.0] * n, "nii": [2.0] * n, "fees": [1.0] * n,
               "gos": [0.0] * n, "servNet": [0.0] * n,
               "prodOpex": [0.5] * n, "feeOpex": [0.25] * n,
               "overhead": [0.75] * n, "nco": [0.0] * n},
    }
    std = {"ratios": {"tier1_rwa": list(range(1, n + 1)),
                       "total_rwa": list(range(101, 101 + n)),
                       "leverage": list(range(201, 201 + n))}}
    return base, std


def test_monthly_rebuckets_and_caps_at_q12():
    base, std = _fixture(12, 7)
    out = build_peer_quarters(base, std, 12)
    assert out["available"] is True
    assert len(out["quarters"]) == 12
    assert out["quarters"][0]["native_start"] == 1
    assert out["quarters"][0]["native_end"] == 3
    assert out["quarters"][0]["standalone"]["tier1_ratio"] == 3
    assert out["quarters"][11]["standalone"]["tier1_ratio"] == 36
    assert out["quarters"][0]["standalone"]["efficiency_ratio"] == 50.0
    assert out["quarters"][1]["filed_ytd"]["efficiency_ratio"] == 50.0


def test_quarterly_preserves_first_twelve_and_ignores_later_years():
    base, std = _fixture(4, 7)
    out = build_peer_quarters(base, std, 4)
    assert len(out["quarters"]) == 12
    assert out["quarters"][11]["standalone"]["tier1_ratio"] == 12


def test_annual_fails_closed_instead_of_inventing_quarters():
    base, std = _fixture(1, 7)
    out = build_peer_quarters(base, std, 1)
    assert out["available"] is False and out["quarters"] == []


if __name__ == "__main__":
    test_monthly_rebuckets_and_caps_at_q12()
    test_quarterly_preserves_first_twelve_and_ignores_later_years()
    test_annual_fails_closed_instead_of_inventing_quarters()
    print("peer quarterly tests passed")
