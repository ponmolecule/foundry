"""r499 acceptance checks: supported-input registry, immutable archived evidence, one reporting window,
annual Tables X and Y, three capital-threshold tiers with cushions and dates, primary-case reporting.

Each check names the review requirement it covers.
"""
import copy
import json
import os
import shutil
import tempfile
from pathlib import Path

from . import stress, stress_report as R
from .tests_r498_stress import BANK, key_for, sc

ROOT = Path(__file__).resolve().parents[2]
results = []


def ck(name, ok, detail=""):
    results.append(bool(ok))
    print(("  PASS  " if ok else "  FAIL  ") + name + ("" if ok else f" :: {str(detail)[:400]}"))


def near(a, b, tol=1e-6):
    return a is not None and b is not None and abs(a - b) <= tol * max(1.0, abs(a), abs(b))


def raises(fn, text):
    try:
        fn()
        return False
    except stress.StressError as e:
        return text in str(e)


def rows_by_key(rows):
    return {r["key"]: r for r in rows if r.get("kind") != "group"}


def main():
    c = copy.deepcopy(BANK)
    k_co = key_for(c, lambda r: r["product_name"] == "Commercial Real Estate" and r["field"] == "charge_off_ann")

    # ------------------------------------------------------------ registry enforced in the backend
    ck("n_periods is rejected by backend resolution (not a stress input)",
       raises(lambda: stress.resolve_target(c, "bank:assumptions:n_periods"), "not a supported stress input"))
    ck("periods_per_year is rejected by backend resolution",
       raises(lambda: stress.resolve_target(c, "bank:assumptions:periods_per_year"), "not a supported stress input"))
    bad = sc([dict(target="bank:assumptions:n_periods", op="replace", value=24, start=1)])
    chk = stress.check_scenario(c, bad)
    ck("a scenario targeting n_periods fails structural validation by name", not chk["ok"] and any("n_periods" in e for e in chk["errors"]), chk)
    reg = stress.registry(c)
    ck("registry entries carry units, bounds and permitted operations",
       reg and all({"key", "unit_kind", "ops", "bounds"} <= set(e) for e in reg) and all(e["key"] in stress.registry_keys(c) for e in reg))
    rate_key = next((e["key"] for e in reg if e["unit_kind"] == "rate" and e["kind"] == "series"), None)
    over = sc([dict(target=rate_key, op="add", value=5.0, start=1)])
    ck("a stressed rate outside the supported range is rejected by name",
       rate_key and raises(lambda: stress.build_config(c, over, "moderate", modes={rate_key: "level"}), "outside the supported range"))

    # ------------------------------------------------------------ reporting settings never touch the base
    c2 = copy.deepcopy(c)
    c2["stress_reporting"] = {"policy_minimums": {"cet1_rwa": 9.0}, "window_periods": 30}
    ck("stress_reporting is excluded from the base fingerprint", stress.base_fingerprint(c2) == stress.base_fingerprint(c))
    from .run_q import run_v2
    h1, h2 = run_v2(copy.deepcopy(c)), run_v2(copy.deepcopy(c2))
    ck("stress_reporting is excluded from config_hash and run_hash",
       h1["config_hash"] == h2["config_hash"] and h1["run_hash"] == h2["run_hash"])

    # ------------------------------------------------------------ one reporting window
    w = R.report_window(c2)
    ck("window narrows to 30 periods; Year 3 is flagged partial",
       w["periods"] == 30 and [y["partial"] for y in w["years"]] == [False, False, True] and w["label"] == "M1 to M30")
    sco = sc([dict(target=k_co, op="multiply", value=2, start=1)])
    c2["stress_scenarios"] = [sco]
    rec_w = stress.run_scenario(c2, sco)[0]
    ni = rec_w["base"]["series"]["ni"]
    ck("metrics and attribution use the reporting window",
       rec_w["window"]["periods"] == 30 and near(rec_w["base"]["metrics"]["cum_ni"], sum(ni[:30]))
       and "M1 to M30" in rec_w["attribution"]["metric"]
       and near(rec_w["attribution"]["total"], rec_w["stress"]["metrics"]["cum_ni"] - rec_w["base"]["metrics"]["cum_ni"], 1e-6))

    # ------------------------------------------------------------ archive, immutability, reproduction
    c["stress_scenarios"] = [sco]
    rec = stress.run_scenario(c, sco, keep_results=True)[0]
    res = rec.pop("_results")
    tmp = tempfile.mkdtemp()
    os.environ["FOUNDRY_DATA_DIR"] = tmp
    try:
        import importlib
        from foundry import store
        importlib.reload(store)
        store.save_stress_run("eng", rec, user="u1", results=res)
        saved = store.load_stress_run("eng", rec["run_id"], user="u1")
        parts = {k: store.load_stress_archive("eng", saved, k, user="u1") for k in ("baseline", "base_result", "stress_cfg", "stress_result")}
        ck("baseline config, base result, stressed config and stressed result are archived", all(parts.values()), list(parts))
        ck("archived baseline excludes stored scenarios and reporting settings",
           not any(k in parts["baseline"] for k in R.STRESS_KEYS) and stress.base_fingerprint(parts["baseline"]) == rec["base_fingerprint"])
        try:
            store.save_stress_run("eng", rec, user="u1", results=res)
            immut = False
        except ValueError as e:
            immut = "never overwritten" in str(e)
        ck("a stored record is never overwritten", immut)
        rep = stress.rerun_from_archive(parts["baseline"], saved)
        ck("rerun from the archived baseline reproduces the same result hash", rep["reproduced"], rep)
        rec2 = stress.run_scenario(c, sco)[0]
        store.save_stress_run("eng", rec2, user="u1")
        ck("a second run is a new record; the first is preserved",
           len(store.list_stress_runs("eng", user="u1")) == 2)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # ------------------------------------------------------------ Tables X and Y
    rp = R.report(res["base_cfg"], res["base_res"], res["stress_cfg"], res["stress_res"], settings_cfg=c)
    X, Y = rows_by_key(rp["X"]), rows_by_key(rp["Y"])
    yrs = len(rp["years"])
    ck("three annual columns for a 36-month window", yrs == 3 and [y["label"] for y in rp["years"]] == ["Year 1", "Year 2", "Year 3"])
    ok = True
    for case in ("base", "stress"):
        for i in range(yrs):
            assets = sum(X[k][case][i] for k in ("cash", "afs", "htm", "hfs", "hfi", "acl", "premises", "intangibles", "other_assets") if k in X)
            # engine lines are stored to the cent per period, so annual identities hold to a few cents
            ok &= abs(assets - X["total_assets"][case][i]) < 0.01
            ok &= abs(X["total_liab"][case][i] + X["equity"][case][i] - X["total_assets"][case][i]) < 0.05
            ok &= abs(Y["ii_loans"][case][i] + Y["ii_cash"][case][i] + Y["ii_sec"][case][i] - Y["ii"][case][i]) < 0.05
            ok &= abs(Y["ii"][case][i] - Y["ie"][case][i] - Y["nii"][case][i]) < 0.12
            ok &= abs(Y["nii"][case][i] - Y["prov"][case][i] + Y["nonii"][case][i] - Y["nie"][case][i] - Y["pretax"][case][i]) < 0.12
            ok &= abs(Y["pretax"][case][i] - Y["tax"][case][i] - Y["ni"][case][i]) < 0.12
            ok &= abs(Y["salaries"][case][i] + Y["premises_x"][case][i] + Y["nie_other"][case][i] - Y["nie"][case][i]) < 0.01
            ok &= abs(Y["svc"][case][i] + Y["nonii_other"][case][i] - Y["nonii"][case][i]) < 0.01
    ck("Table X and Y rows add up to their totals in both cases and every year (no double counting)", ok)
    ck("annual net income sums to the run's cumulative net income over the window",
       near(sum(Y["ni"]["base"]), rec["base"]["metrics"]["cum_ni"], 1e-4) and near(sum(Y["ni"]["stress"]), rec["stress"]["metrics"]["cum_ni"], 1e-4))
    ck("every change column is stress minus base",
       all(near(r["delta"][i], r["stress"][i] - r["base"][i], 1e-6) for r in X.values() if r["available"] for i in range(yrs)))
    ck("Year 1 stock equals the period-12 balance; Year 1 flow equals the sum of periods 1 to 12",
       near(X["total_assets"]["base"][0], res["base_res"]["financials"]["bs"]["totalAssets"][12], 1e-4)
       and near(Y["ni"]["base"][0], sum(res["base_res"]["financials"]["is"]["ni"][:12]), 1e-4))
    ck("unclassified deposits: the split is not shown and total deposits are", not X["nib"]["available"] and not X["ib"]["available"]
       and X["deposits"]["available"] and rp["unclassified_deposits"] == 6)
    ck("intangible assets carry their configured value", X["intangibles"]["available"])
    ck("ratio rows are percentages and their changes are differences in points",
       X["leverage"]["unit"] == "pct" and near(X["leverage"]["delta"][2], X["leverage"]["stress"][2] - X["leverage"]["base"][2]))

    # deposits: explicit, user-confirmed
    cd = copy.deepcopy(c)
    dc = R.deposit_classification(cd)
    ck("a suggestion is offered per deposit product but nothing is classified until confirmed",
       all(d["suggested"] in ("ib", "nib") and d["class"] is None for d in dc))
    cd["stress_reporting"] = {"deposit_classes": {d["key"]: ("nib" if d["name"] == "Retail Demand" else "ib") for d in dc}}
    rp2 = R.report(res["base_cfg"], res["base_res"], res["stress_cfg"], res["stress_res"], settings_cfg=cd)
    X2 = rows_by_key(rp2["X"])
    ck("classifying Retail Demand as noninterest-bearing overrides the rate-based suggestion",
       next(d for d in dc if d["name"] == "Retail Demand")["suggested"] == "ib" and X2["nib"]["available"])
    ck("interest-bearing plus noninterest-bearing deposits equal total deposits",
       all(abs(X2["nib"][k][i] + X2["ib"][k][i] - X["deposits"][k][i]) < 0.05 for k in ("base", "stress") for i in range(yrs)))

    # expenses: reporting mapping only
    ce = copy.deepcopy(cd)
    ex = R.expense_classification(ce)
    ce["stress_reporting"]["expense_classes"] = {ex[1]["key"]: "premises"}
    rp3 = R.report(res["base_cfg"], res["base_res"], res["stress_cfg"], res["stress_res"], settings_cfg=ce)
    Y3 = rows_by_key(rp3["Y"])
    ck("mapping an expense category to premises moves it from Other without changing total expense",
       Y3["premises_x"]["base"][0] > Y["premises_x"]["base"][0] and near(Y3["nie"]["base"][0], Y["nie"]["base"][0], 1e-12)
       and near(Y3["premises_x"]["base"][0] + Y3["nie_other"]["base"][0], Y["premises_x"]["base"][0] + Y["nie_other"]["base"][0], 1e-9))

    # ------------------------------------------------------------ ROAA convention, one definition
    ann = res["base_res"]["annual"]
    ck("engine annual ROA equals the table's ROAA (time-weighted average assets)",
       all(near(round(Y["roaa"]["base"][i], 2), ann["roa"][i], 1e-9) for i in range(yrs)), (Y["roaa"]["base"], ann["roa"]))
    ck("engine annual ROE and efficiency equal the table's ROAE and efficiency",
       all(near(round(Y["roae"]["base"][i], 2), ann["roe"][i]) and near(round(Y["eff"]["base"][i], 2), ann["eff"][i]) for i in range(yrs)))
    ck("ROAE uses equity, not assets", not near(Y["roae"]["base"][0], Y["roaa"]["base"][0]))

    # ------------------------------------------------------------ capital: three tiers, cushions, dates
    cap = rp["capital"]["base"]["ratios"]
    lev = cap["leverage"]
    ck("all four capital ratios are assessed", all(cap[r]["available"] for r, _ in R.RATIOS))
    ck("regulatory and commitment tiers are reported separately; policy is blank until entered",
       lev["tiers"]["regulatory"] and lev["tiers"]["commitment"] and lev["tiers"]["policy"] is None
       and lev["tiers"]["regulatory"]["floor"] != lev["tiers"]["commitment"]["floor"])
    capr = res["base_res"]["capital"]
    t = lev["tiers"]["commitment"]
    i = t["min_cushion_period"] - 1
    ck("leverage cushion = Tier 1 less floor x average assets at the reported period",
       near(t["min_cushion"], capr["rows"]["tier1"][i] - t["floor"] / 100 * capr["rows"]["avg_assets_net"][i], 1e-6))
    ck("the lowest cushion and the lowest ratio carry their own dates", lev["min_period"] != t["min_cushion_period"], (lev["min_period"], t["min_cushion_period"]))
    cr = cap["total_rwa"]["tiers"]["regulatory"]
    j = cr["min_cushion_period"] - 1
    st = capr["standardized"]
    ck("total capital cushion uses total capital and RWA",
       near(cr["min_cushion"], st["total"][j] - 0.10 * st["rwa"][j], 1e-6))
    cp = copy.deepcopy(c)
    cp["stress_reporting"] = {"policy_minimums": {"leverage": {"value": 30.0, "source": "Board policy 2026", "effective": "2026-01-01"}}}
    capP = R.capital_assessment(cp, res["base_res"])["ratios"]["leverage"]["tiers"]["policy"]
    ck("an entered policy minimum is its own tier with source, and its breach is dated",
       capP and capP["source"] == "Board policy 2026" and capP["first_breach_period"] is not None and capP["status"] == "below")
    fb = R.capital_assessment(cp, res["base_res"])["first_breach"]
    ck("first breach of any selected threshold names ratio, tier and period", fb and fb["tier"] == "policy" and fb["ratio"] == "leverage")
    ck("CBLR election is reported with the assessment", rp["capital"]["base"]["cblr_elected"] is True)

    # ------------------------------------------------------------ quarterly cadence
    q = json.loads((ROOT / "foundry/fixtures/parity/configs/pf_b_htm_securities.json").read_text())
    qr = stress._engine_run(copy.deepcopy(q))
    sq = R.statements(q, qr)
    Xq = {t[0].split(":")[-1]: t[2] for t in sq["X"] if t[0] != "g"}
    Yq = {t[0].split(":")[-1]: t[2] for t in sq["Y"] if t[0] != "g"}
    ck("quarterly model: years are four quarters; stocks at Q4, Q8, Q12",
       [y["label"] for y in sq["years"]] == ["Year 1", "Year 2", "Year 3"]
       and near(Xq["total_assets"][1], qr["financials"]["bs"]["totalAssets"][8 if len(qr["financials"]["bs"]["totalAssets"]) == 13 else 7], 1e-6))
    ck("quarterly model: annual net income is the sum of its four quarters",
       near(Yq["ni"][2], sum(qr["financials"]["is"]["ni"][8:12]), 1e-6))
    ck("quarterly model: HTM securities are shown on their own line", "htm" in Xq)

    # ------------------------------------------------------------ endpoints
    tmp = tempfile.mkdtemp()
    os.environ["FOUNDRY_DATA_DIR"] = tmp
    try:
        import importlib
        from fastapi.testclient import TestClient
        from foundry import store
        importlib.reload(store)
        import app as A
        A.app.dependency_overrides[A.gate] = lambda: "u1"
        cl = TestClient(A.app)
        body = {"cfg": c, "slug": "eng", "runs": [{"scenario_id": "s1"}], "attribution": False}
        rr = cl.post("/api/v31/stress/run", json=body).json()
        r0 = rr["records"][0]
        ck("run endpoint stores the record with its archive and returns its report",
           rr["stored"] and r0.get("archive") and r0.get("report") and r0["report"]["X"])
        rep = cl.post("/api/v31/stress/report", json={"cfg": c, "slug": "eng", "run_id": r0["run_id"]}).json()
        ck("report from the archive equals the report computed at run time", rep["report"] == r0["report"])
        cd2 = dict(c, stress_reporting=cd["stress_reporting"])
        rep2 = cl.post("/api/v31/stress/report", json={"cfg": cd2, "slug": "eng", "run_id": r0["run_id"]}).json()
        ck("report uses the current classification without rerunning", rows_by_key(rep2["report"]["X"])["nib"]["available"]
           and rep2["state"] == "current")
        rp_ = cl.post("/api/v31/stress/reproduce", json={"slug": "eng", "run_id": r0["run_id"]}).json()
        ck("reproduce endpoint confirms the archived run", rp_.get("reproduced") is True, rp_)
        reg_ = cl.post("/api/v31/stress/registry", json={"cfg": c}).json()
        ck("registry endpoint lists supported inputs only", reg_["registry"] and not any("n_periods" in e["key"] for e in reg_["registry"]))
        x = cl.post("/api/v31/stress/export", json={"cfg": c, "slug": "eng", "run_ids": [r0["run_id"]], "report_run_id": r0["run_id"]})
        import io
        from openpyxl import load_workbook
        wb = load_workbook(io.BytesIO(x.content))
        ck("export adds Tables X and Y and the capital sheet for the primary case",
           {"Table X Balance Sheet", "Table Y Income Statement", "Capital vs Thresholds"} <= set(wb.sheetnames), wb.sheetnames)
        c_changed = copy.deepcopy(c)
        c_changed["assumptions"]["tax_rate"] = (c_changed["assumptions"].get("tax_rate") or 0.21) + 0.01
        st_ = cl.post("/api/v31/stress/report", json={"cfg": c_changed, "slug": "eng", "run_id": r0["run_id"]}).json()
        ck("a primary run goes stale when the base changes", st_["state"] == "stale")
        A.app.dependency_overrides.clear()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print(f"\n{sum(results)} passed, {len(results) - sum(results)} failed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
