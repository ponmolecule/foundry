from foundry.charteriq_client import CharterIQClient
from foundry.v2.peer_intelligence_vintage import build_curated_vintage_corridor


def _fake(sql, params):
    if "FROM institutions" in sql:
        return [(11, "A", "20200115", 2020), (22, "B", "20210701", 2021)]
    if "FROM metrics" in sql:
        rows = []
        for i in range(12):
            y, q = 2020 + i // 4, i % 4 + 1
            rows.append((11, "roa", y, q, i + 1.0))
        for i in range(12):
            # Bank B opens in 2021Q3; omit age Q4 to prove Q5 stays Q5.
            if i == 3:
                continue
            idx = 2 + i
            y, q = 2021 + idx // 4, idx % 4 + 1
            rows.append((22, "roa", y, q, 101.0 + i))
        return rows
    return []


def test_curated_vintage_reclocks_by_opening_quarter_without_shifting_gaps():
    out = build_curated_vintage_corridor(
        CharterIQClient(executor=_fake), [11, 22], ["roa"], min_n=1)
    ages = out["corridor"]["roa"]["ages"]
    assert ages[9]["n"] == 2                 # both banks' own Q10
    assert ages[9]["p50"] == 60.0            # median of 10 and 110
    assert ages[3]["n"] == 1                 # missing B Q4 preserved
    assert ages[4]["n"] == 2                 # B Q5 did not slide into Q4
    assert len(ages) == 12


def test_curated_vintage_reports_unmatched_and_suppresses_thin_ages():
    out = build_curated_vintage_corridor(
        CharterIQClient(executor=_fake), [11, 22, 99], ["roa"], min_n=2)
    assert out["coverage"]["unmatched_certs"] == [99]
    assert out["corridor"]["roa"]["ages"][3]["suppressed"] is True
