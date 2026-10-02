"""r240 regression gate: Peer Cohort batching, caching, min/max and the Excel export."""
import io, json, os, sys


def main():
    sys.path.insert(0, ".")
    p = f = 0
    def ck(name, cond, detail=""):
        nonlocal p, f
        if cond: p += 1; print("  PASS ", name + (f" — {detail}" if detail else ""))
        else: f += 1; print("  FAIL ", name + (f" — {detail}" if detail else ""))

    # 1. live percentile queries carry min/max, and still accept the older 8-column rows
    from foundry.charteriq_client import CharterIQClient
    seen = []
    def ex10(sql, params):
        seen.append(sql)
        if "percentile_cont" in sql: return [(2026, 2, 1.0, 2.0, 3.0, 4.0, 5.0, 40, 0.5, 6.0)]
        return [(2026, 2)]
    def ex8(sql, params):
        if "percentile_cont" in sql: return [(2026, 2, 1.0, 2.0, 3.0, 4.0, 5.0, 40)]
        return [(2026, 2)]
    b10 = CharterIQClient(executor=ex10).get_cohort_bands("roa", [1, 2, 3])
    b8 = CharterIQClient(executor=ex8).get_cohort_bands("roa", [1, 2, 3])
    ck("cohort bands carry min/max from the same query", b10 and b10[-1].get("min") == 0.5 and b10[-1].get("max") == 6.0
       and any("MIN(value) AS vmin" in s for s in seen))
    ck("cohort bands still parse 8-column rows (no min/max)", b8 and "min" not in b8[-1] and b8[-1]["p50"] == 3.0)

    # 2. stored-band extremes are withheld when they contradict the stored percentiles
    from foundry.v2 import peer_bands as pb
    class Fake:
        def __init__(self, row): self.row = row
        def configured(self): return True
        def _run(self, sql, params): return [self.row]
    doc = {"bands": [{"year": 2026, "q": 2, "p10": 1.0, "p90": 5.0}]}
    ck("stored-band extremes attached when consistent", pb.attach_extremes(doc, "roa", "under_200M", Fake((0.2, 9.0, 300))) == "attached"
       and doc["bands"][-1]["min"] == 0.2)
    doc2 = {"bands": [{"year": 2026, "q": 2, "p10": 1.0, "p90": 5.0}]}
    ck("stored-band extremes withheld when inconsistent", pb.attach_extremes(doc2, "roa", "under_200M", Fake((1.5, 9.0, 300))) == "withheld"
       and "min" not in doc2["bands"][-1])

    # 3. batch endpoint: one request, one retry on 502, cached successes, failures not cached
    for k, v in (("FOUNDRY_USER", "klaros"), ("FOUNDRY_PASS", "test123"), ("FOUNDRY_COOKIE_SECURE", "0"), ("FOUNDRY_DATA_DIR", "/tmp/fdata_t240")):
        os.environ.setdefault(k, v)
    import app as A
    from fastapi.responses import JSONResponse
    calls, flaky = [], {"nim"}
    def fake(metric="roa", cohort="broad", user=None):
        calls.append(metric)
        if metric in flaky:
            flaky.discard(metric); return JSONResponse({"error": "dropped"}, status_code=502)
        if metric == "nco": return JSONResponse({"error": "no percentile rows"}, status_code=404)
        return JSONResponse({"metric": metric, "bands": [{"quarter": "2026Q2", "year": 2026, "q": 2, "p10": 1, "p25": 2, "p50": 3,
                                                          "p75": 4, "p90": 5, "n": 9, "min": 0.5, "max": 6}]})
    orig = A.v31_peer_bands; A.v31_peer_bands = fake; A._PB_CACHE.clear()
    A.app.dependency_overrides[A.gate] = lambda: {"user": "test"}
    try:
        from fastapi.testclient import TestClient
        c = TestClient(A.app)
        q = "/api/v31/peer-bands/batch?metrics=roa,nim,nco&cohort=t240"
        r1 = c.get(q).json()["results"]
        ck("batch returns every metric in one request, retrying a transient failure once",
           [x["metric"] for x in r1] == ["roa", "nim", "nco"] and "d" in r1[1] and calls.count("nim") == 2)
        calls.clear(); r2 = c.get(q).json()["results"]
        ck("batch serves successes from cache and re-asks only failures", calls == ["nco"] and r2[0].get("cached") is True)
        r = c.post("/api/v31/peer-export", json={"cohort_label": "t", "corridor": [{"metric": "roa", "label": "ROA", "basis": "Flow",
                    "modeled": 3.5, "n": 9, "min": 0.5, "p10": 1, "p25": 2, "p50": 3, "p75": 4, "p90": 5, "max": 6}]})
        ck("export returns a workbook named in Central time", r.status_code == 200 and "Foundry_Peer_Cohort_t_" in r.headers.get("content-disposition", ""))
    finally:
        A.v31_peer_bands = orig; A.app.dependency_overrides.clear()

    # 4. workbook: curated sheets compute aggregates and placement as formulas over the peer columns
    from foundry.v2.peer_export import build_workbook
    import openpyxl
    data = build_workbook({"cohort_label": "c", "corridor": [], "vintage": {"corridor": {"roa": {"ages": [{"age_q": 1, "n": 2}]}},
                           "series_by_cert": {"roa": {"1": {"1": 2.0}, "2": {"1": 4.0}}}}, "vintage_modeled": {"roa": {"1": 5.0}}})
    ws = openpyxl.load_workbook(io.BytesIO(data))["ROA"]   # r241: sheets named in mixed case
    row = [c.value for c in ws[5]]
    ck("curated sheet: peer values as inputs, min/median/max as formulas, placement formula",
       row[1] == 2.0 and row[2] == 4.0 and str(row[3]).startswith('=IF(COUNT(B5:C5)=0,"",MIN(B5:C5))')
       and 'MEDIAN(B5:C5)' in str(row[6]) and str(row[-1]).startswith("=IF(OR("))
    # r241: vintage corridor filters by asset band; workbook charts style each series distinctly
    from foundry.charteriq_client import build_vintage_corridor
    sqls = []
    def exv(sql, params):
        sqls.append((sql, params))
        if "FROM institutions" in sql: return [(1, 2019, None, None)]
        return [(1, "roa", 2019, q, 1.0) for q in (1, 2, 3, 4)]
    class C:
        def _run(self, sql, params=()): return exv(sql, params)
    try:
        build_vintage_corridor(C(), 2018, 2023, metrics=["roa"], min_n=1, asset_band="2B_10B")
    except Exception:
        pass
    inst = [x for x in sqls if "FROM institutions" in x[0]]
    mq = [x for x in sqls if "FROM metrics" in x[0]]
    ck("vintage data query is bounded to the years the corridor can use",
       bool(mq) and "year BETWEEN %s AND %s" in mq[0][0] and 2018 in mq[0][1] and 2030 in mq[0][1])
    ck("vintage corridor filters membership by the selected asset band",
       bool(inst) and "asset_size_mm >= %s" in inst[0][0] and 2000 in inst[0][1] and 10000 in inst[0][1])
    data = build_workbook({"cohort_label": "c", "corridor": [], "vintage": {"corridor": {"roa": {"ages": [{"age_q": a, "n": 2} for a in (1, 2, 3)]}},
                           "series_by_cert": {"roa": {"1": {"1": 2.0, "2": 3.0, "3": 4.0}, "2": {"1": 4.0, "2": 5.0, "3": 6.0}}}},
                           "vintage_modeled": {"roa": {"1": 5.0, "3": 6.0}}})
    import zipfile, re as _re
    z = zipfile.ZipFile(io.BytesIO(data)); charts = [n for n in z.namelist() if n.startswith("xl/charts/chart")]
    xml = z.read(charts[0]).decode() if charts else ""
    colors = _re.findall(r'<a:ln[^>]*><a:solidFill><a:srgbClr val="([0-9a-fA-F]{6})"', xml)   # namespace-prefix agnostic
    ck("workbook has a chart per corridor sheet plus a Charts sheet, each series styled distinctly",
       len(charts) >= 2 and len(set(c.lower() for c in colors)) >= 4 and "ROA" in openpyxl.load_workbook(io.BytesIO(data)).sheetnames)
    from foundry.charteriq_client import accuracy_label
    ck("earnings metrics carry the migrated label; unconfirmed metrics keep the cautious one",
       "migrated" in accuracy_label("roa") and "migrated" in accuracy_label("efficiency_ratio")
       and "pending" in accuracy_label("net_charge_off_rate"))
    print(f"\n{p} passed, {f} failed")
    return 0 if f == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
