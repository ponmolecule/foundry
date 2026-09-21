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


def test_nim_uses_native_earning_assets_and_window_endpoints():
    base, std = _fixture(12, 3)
    # A managed book is deliberately large. It must not be injected solely by
    # the Peer adapter when the native/source NIM denominator excludes it.
    base["bs"]["afsBook"] = [10_000.0] * 37
    out = build_peer_quarters(base, std, 12)
    q1 = out["quarters"][0]
    # M1-M3 NII = 6; earning assets are cash only: open=50, M3=53.
    expected = 6.0 * 4.0 / ((50.0 + 53.0) / 2.0) * 100.0
    assert abs(q1["filed_ytd"]["nim"] - expected) < 1e-12


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
    test_nim_uses_native_earning_assets_and_window_endpoints()
    test_quarterly_preserves_first_twelve_and_ignores_later_years()
    test_annual_fails_closed_instead_of_inventing_quarters()
    print("peer quarterly tests passed")
