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


def test_curated_vintage_reports_unmatched_and_labels_thin_ages():
    out = build_curated_vintage_corridor(
        CharterIQClient(executor=_fake), [11, 22, 99], ["roa"], min_n=2)
    assert out["coverage"]["unmatched_certs"] == [99]
    age4 = out["corridor"]["roa"]["ages"][3]
    assert age4["n"] == 1 and age4["thin_sample"] is True
    assert age4["band_type"] == "single observation"


def test_mmddyyyy_and_young_bank_do_not_empty_older_bank_q10():
    def fake(sql, params):
        if "FROM institutions" in sql:
            return [(59194, "A", "07/01/2019", 2019),
                    (59337, "B", "01/01/2023", 2023),
                    (59363, "C", "07/01/2024", 2024)]
        rows = []
        starts = {59194: (2019, 3, 12), 59337: (2023, 1, 12),
                  59363: (2024, 3, 7)}
        for cert, (y0, q0, count) in starts.items():
            for i in range(count):
                offset = q0 - 1 + i
                rows.append((cert, "nim", y0 + offset // 4,
                             offset % 4 + 1, float(cert % 100 + i)))
        return rows

    out = build_curated_vintage_corridor(
        CharterIQClient(executor=fake), [59194, 59337, 59363], ["nim"])
    ages = out["corridor"]["nim"]["ages"]
    assert ages[6]["n"] == 3                 # all three reach Q7
    assert ages[9]["n"] == 2                 # youngest does not erase Q10
    assert ages[9]["band_type"] == "thin sample — observed range"
    assert ages[9]["low"] is not None and ages[9]["high"] is not None
    coverage = {b["cert"]: b for b in out["coverage"]["banks"]}
    assert coverage[59363]["q10_eligible_by_metric"]["nim"] is False
    assert coverage[59194]["vintage_anchor_q"] == "2019Q3"


def test_truncated_history_is_not_mislabeled_as_opening_vintage():
    def fake(sql, params):
        if "FROM institutions" in sql:
            return [(1, "Old bank", "01/01/1990", 1990)]
        return [(1, "nim", 2020, 1, 4.0)]

    out = build_curated_vintage_corridor(
        CharterIQClient(executor=fake), [1], ["nim"])
    bank = out["coverage"]["banks"][0]
    assert bank["vintage_anchor_q"] is None
    assert "not treated as an opening vintage" in bank["status"]
    assert out["corridor"]["nim"]["ages"][0]["n"] == 0


def test_first_filing_is_used_when_legal_opening_is_null():
    def fake(sql, params):
        if "FROM institutions" in sql:
            return [(59194, "ADP Trust", None, None),
                    (59337, "Dayforce", None, None),
                    (59363, "Paycom", None, None)]
        rows = []
        starts = {59194: (2019, 3, 12), 59337: (2023, 1, 12),
                  59363: (2024, 3, 7)}
        for cert, (y0, q0, count) in starts.items():
            for i in range(count):
                offset = q0 - 1 + i
                rows.append((cert, "nim", y0 + offset // 4,
                             offset % 4 + 1, 1.0 + i))
        return rows

    out = build_curated_vintage_corridor(
        CharterIQClient(executor=fake), [59194, 59337, 59363], ["nim"])
    ages = out["corridor"]["nim"]["ages"]
    assert ages[6]["n"] == 3 and ages[9]["n"] == 2
    for bank in out["coverage"]["banks"]:
        assert bank["vintage_anchor_q"] == bank["first_filing_q"]
        assert "legal opening date unavailable" in bank["status"]
