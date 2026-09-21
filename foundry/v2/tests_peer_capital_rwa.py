import copy
import json

from foundry.v2.audit_workbook import calculation_audit_workbook
from foundry.v2.run_q import run_v2
from foundry.v2.tests_interest_balances import _cfg as _cash_cfg


def _cfg():
    with open("foundry/fixtures/universal_template_bank.json", encoding="utf-8") as fh:
        return json.load(fh)


def test_cash_detail_drives_rwa_without_hidden_percentage():
    cfg = _cash_cfg()
    cfg["assumptions"]["n_periods"] = 36
    result = run_v2(cfg)
    st = result["capital"]["standardized"]
    bs = result["financials"]["bs"]
    i = 2  # M3 / regulatory Q1
    expected = (bs["affiliatedCash"][i + 1] + bs["operatingCash"][i + 1]) * 0.20
    assert abs(st["rwa_components"]["cash_at_depositories"][i] - expected) < 0.02
    assert abs(st["rwa"][i] - sum(v[i] for v in st["rwa_components"].values())) < 0.02


def test_peer_horizon_is_q12_even_when_model_is_seven_years():
    cfg = _cfg()
    cfg["assumptions"]["n_periods"] = 84
    result = run_v2(cfg)
    pq = result["peer_quarterly"]
    assert len(pq["quarters"]) == 12
    assert pq["quarters"][-1]["native_end"] == 36


def test_managed_sleeve_risk_weights_drive_securities_rwa():
    zero_cfg = _cfg()
    full_cfg = copy.deepcopy(zero_cfg)
    for portfolio in zero_cfg["assumptions"]["managed_securities_portfolios"]:
        for sleeve in portfolio["sleeves"]:
            sleeve["risk_weight"] = 0.0
    for portfolio in full_cfg["assumptions"]["managed_securities_portfolios"]:
        for sleeve in portfolio["sleeves"]:
            sleeve["risk_weight"] = 1.0
    zero = run_v2(zero_cfg)
    full = run_v2(full_cfg)
    i = 11
    managed_balance = sum(s["ending"][i] for p in full["managed_securities"] for s in p["sleeves"])
    rwa_delta = (full["capital"]["standardized"]["rwa_components"]["securities"][i]
                 - zero["capital"]["standardized"]["rwa_components"]["securities"][i])
    assert abs(rwa_delta - managed_balance) < 0.02


def test_audit_workbook_exposes_capital_and_rwa_bridge():
    cfg = _cfg()
    result = run_v2(cfg)
    wb = calculation_audit_workbook(cfg, result)
    assert "Capital & RWA" in wb.sheetnames
    labels = [r[1] for r in wb["Capital & RWA"].iter_rows(min_row=5, values_only=True)]
    assert "Tier 1 / RWA" in labels
    assert "Total capital / RWA" in labels
    assert "Cash at depository institutions" in labels


if __name__ == "__main__":
    test_cash_detail_drives_rwa_without_hidden_percentage()
    test_peer_horizon_is_q12_even_when_model_is_seven_years()
    test_managed_sleeve_risk_weights_drive_securities_rwa()
    test_audit_workbook_exposes_capital_and_rwa_bridge()
    print("peer capital/RWA tests passed")
