"""r502 acceptance checks: liquidity stress (redemption books, resources ladder, stress-day intraday test,
30-day run, LCR as a management measure, contingency line) on a projection it never changes.
Hand-computed cases check the arithmetic independently of the module.
"""
import copy
import os
import shutil
import tempfile

from . import liquidity as LQ, stress
from .stress_report import _cap_series, _model, _pkey
from .tests_r498_stress import BANK, key_for

results = []


def ck(name, ok, detail=""):
    results.append(bool(ok))
    print(("  PASS  " if ok else "  FAIL  ") + name + ("" if ok else f" :: {str(detail)[:400]}"))


def trust_bank():
    c = copy.deepcopy(BANK)
    c["charter_profile"]["charter_type"] = "national_trust"
    t = LQ.template(c)
    t["books"][0]["balance"] = {"deposit_keys": ["name:Sweep / Program", "name:Institutional"]}
    t["books"].append(dict(id="fund", type="fund_settlement", name="Fund share settlement", balance={"entered": 50000}, repaid_after_days=2,
                           severities={"severe": {"day1": 0.015, "days2_30": 0.03}}, hourly=[1, 1, 2, 3, 3, 2, 2, 1, 1],
                           calibration={"status": "draft", "source": "operations"}))
    t["resources"].append(dict(id="mmf", name="MMF shares", balance={"entered": 3000}, available="15:00", haircut=0, hqla=None))
    t["line"] = dict(capacity=5000, available="14:00", cutoff="16:00", available_from=1, term="over_30", collateral_hqla=1000)
    c["liquidity_stress"] = t
    return c


def base_of(c):
    return {k: v for k, v in c.items() if k not in stress.STRESS_KEYS}


def main():
    c = trust_bank()
    plain = copy.deepcopy(c); plain.pop("liquidity_stress")
    # ------------------------------------------------------------ the base is never touched
    ck("liquidity settings never move the base fingerprint", stress.base_fingerprint(c) == stress.base_fingerprint(plain))
    r_with, r_plain = stress._engine_run(c), stress._engine_run(plain)
    ck("engine results are identical with and without liquidity settings (config and run hash)",
       r_with["config_hash"] == r_plain["config_hash"] and r_with["run_hash"] == r_plain["run_hash"])
    res = stress._engine_run(base_of(c))

    # ------------------------------------------------------------ template and validation
    t = LQ.template(c)
    ck("the template for a national trust bank starts with a custody-cash book, every rate flagged draft",
       t["books"][0]["type"] == "custody_cash" and all(b["calibration"]["status"] == "draft" for b in t["books"]) and t["lcr"]["requested"])
    ck("a valid setup has no structural errors", LQ.validate(c) == [], LQ.validate(c))
    for mut, why in ((lambda s: s["books"][0].update(hourly=[1, 2]), "hourly weights"),
                     (lambda s: s["books"][0]["severities"]["severe"].update(day1=1.4), "between 0% and 100%"),
                     (lambda s: s["books"][0]["severities"]["severe"].update(day1=0.7, days2_30=0.5), "cannot exceed 100%"),
                     (lambda s: s["line"].update(available="16:30"), "before its cutoff"),
                     (lambda s: s["books"][0].update(balance={"deposit_keys": ["nope"]}), "not in this engagement"),
                     (lambda s: s["resources"][0].update(hqla="3"), "HQLA level"),
                     (lambda s: s["stress_day"].update(month=99), "stress day")):
        cc = copy.deepcopy(c); mut(cc["liquidity_stress"])
        errs = LQ.validate(cc)
        ck(f"validation names the problem: {why}", any(why in e for e in errs), errs)
        try:
            LQ.run(cc, res); ok = False
        except LQ.LiquidityError:
            ok = True
        ck(f"an invalid setup is refused, not run ({why})", ok)

    # ------------------------------------------------------------ the run reads the projection
    out = LQ.run(c, res)
    bs = res["financials"]["bs"]
    lowest = min(range(1, 37), key=lambda i: (bs["cash"][i] + bs["sec"][i], i))
    ck("the lowest-cash month is the month with the least cash plus securities", out["month"] == lowest, (out["month"], lowest))
    m = _model(base_of(c), res)
    dep = sum(p["bal"][lowest] for p, cf in zip(m.dep, m.dep_cfg) if _pkey(cf) in ("name:Sweep / Program", "name:Institutional"))
    ck("a custody book's balance is the projected balance of its deposit products at the stress month", abs(out["books"][0]["balance"] - dep) < 1e-3)
    ck("resources read the projected balance sheet at the stress month", abs(out["ladder"][0]["amount"] - bs["cash"][lowest]) < 1e-3)
    ck("day-1 outflow is the balance times the day-1 run-off", abs(out["books"][0]["day1_outflow"] - dep * 0.25) < 1e-2)
    c12 = copy.deepcopy(c); c12["liquidity_stress"]["stress_day"]["month"] = 12
    ck("a chosen month is used as given", LQ.run(c12, res)["month"] == 12)

    # ------------------------------------------------------------ intraday, by hand
    d = LQ.intraday([(90.0, [1 / 9] * 9)], [(LQ._hm("08:00"), 20.0, "Cash"), (LQ._hm("11:30"), 100.0, "Repo")])
    w = d["windows"][0] if d["windows"] else {}
    ck("intraday: the shortfall starts when outflows pass the opening resources (10:01) and ends when the repo settles (11:30)",
       w.get("start") == "10:01" and w.get("end") == "11:30" and w.get("covered_by") == "Repo", w)
    ck("intraday: the lowest cushion is just before the repo, 20 less 10 an hour for 3h29m",
       abs(d["lowest_cushion"] - (20 - 10 * 209 / 60)) < 1e-3 and d["lowest_at"] == "11:29", (d["lowest_cushion"], d["lowest_at"]))
    ck("intraday: a short day that recovers is 'short intraday'", d["status"] == "short_intraday")
    d2 = LQ.intraday([(90.0, [1 / 9] * 9)], [(LQ._hm("08:00"), 20.0, "Cash")], line=(LQ._hm("14:00"), LQ._hm("16:00"), 100.0))
    ck("a line usable after the shortfall starts is reported as too late", "too late" in d2["line_note"] and d2["windows"][0]["covered_by"] == "Contingency line")
    d3 = LQ.intraday([(90.0, [1 / 9] * 9)], [(LQ._hm("08:00"), 20.0, "Cash")])
    ck("a shortfall still open at the close is 'short at close'", d3["status"] == "short_at_close" and d3["windows"][0]["end"] is None)
    d4 = LQ.intraday([(10.0, [1 / 9] * 9)], [(LQ._hm("08:00"), 20.0, "Cash")], line=(LQ._hm("16:30"), LQ._hm("16:00"), 5.0))
    ck("a line usable only after its cutoff cannot be drawn", "cannot be drawn" in d4["line_note"] and d4["status"] == "covered")
    ck("the chart runs 08:00 to 17:00 in five-minute steps", d["chart"][0]["t"] == "08:00" and d["chart"][-1]["t"] == "17:00" and len(d["chart"]) == 109)

    # ------------------------------------------------------------ 30-day run, by hand
    r30 = LQ.run_30([(10.0, 29.0, None)], 30.0, 10.0, 30)
    ck("30-day run: closes fall 10 on day 1 then 1 a day; the bank runs out after day 21",
       r30["closes"][0] == 20 and r30["closes"][20] == 0 and r30["survival_days"] == 21 and not r30["survives"], r30["closes"][:3])
    ck("30-day run: the line covers the 9 shortfall and the bank survives with it",
       r30["line_needed"] and r30["with_line"]["survives"] and abs(r30["with_line"]["draw"] - 9) < 1e-9)
    rf = LQ.run_30([(10.0, 0.0, 2)], 10.0, 0.0, 30)
    ck("settlement advances come back after the settlement lag", rf["inflows"][2] == 10 and rf["closes"][2] == 10 and rf["closes"][1] == 0)

    # ------------------------------------------------------------ LCR, by hand
    rows = [dict(outflow=100.0)]
    a = LQ.lcr(rows, [dict(level="1", counts=200.0)], 20.0)
    ck("LCR: HQLA over outflows less inflows", abs(a["lcr"] - 200 / 80) < 1e-9)
    b = LQ.lcr(rows, [dict(level="1", counts=200.0)], 100.0)
    ck("LCR: inflows count up to 75% of outflows", b["inflows_counted"] == 75 and abs(b["lcr"] - 200 / 25) < 1e-9 and b["cap_binding"])
    cc_ = LQ.lcr(rows, [dict(level="1", counts=30.0), dict(level="2A", counts=100.0)], 0.0)
    ck("LCR: level 2 is capped at 40% of the stock (2/3 of level 1)", abs(cc_["hqla"] - 50.0) < 1e-9 and cc_["caps_binding"])
    L = out["lcr"]
    ck("the LCR runs as a management measure below $100B, with the rule's 25% on operational custody cash",
       L["status"] == "calculated" and L["outflow_rows"][0]["rate"] == 0.25 and L["outflow_rows"][0]["source"] == "rule"
       and next(x for x in out["applicability"] if x["test"] == "lcr")["applies"] == "management measure")
    ck("money market fund shares are listed but are not HQLA", any(x["name"] == "MMF shares" for x in L["not_hqla"]) and all(x["name"] != "MMF shares" for x in L["hqla_rows"]))
    ck("settlement advances use the engagement's 30-day stress rate and are tagged as an engagement assumption",
       any(r["category"] == "Fund share settlement" and r["source"] == "engagement" and abs(r["rate"] - 0.045) < 1e-9 for r in L["outflow_rows"]))
    ld, bf = L["line_draw"], L["before"]
    net = bf["net_outflows"]
    ck("line draw repaid after 30 days: HQLA rises by the draw less the pledged HQLA",
       abs(ld["lcr"]["over_30"] - (bf["hqla"] + 5000 - 1000) / net) < 1e-6, (ld["lcr"], bf))
    o2 = bf["outflows"] + 5000
    net2 = o2 - min(bf["inflows"], 0.75 * o2)
    ck("line draw due within 30 days also adds a 100% outflow", abs(ld["lcr"]["within_30"] - (bf["hqla"] + 4000) / net2) < 1e-6)
    cap = _cap_series(res)
    t1, avg = cap["leverage"][1][out["month"] - 1], cap["leverage"][2][out["month"] - 1]
    ck("leverage after the draw: Tier 1 over average assets plus the draw; CET1 / RWA unchanged (cash is 0% risk weight)",
       abs(ld["leverage"]["after"] - t1 / (avg + 5000)) < 1e-12 and ld["cet1_rwa"]["before"] == ld["cet1_rwa"]["after"])

    # ------------------------------------------------------------ applicability and honesty about missing inputs
    cm = copy.deepcopy(c); cm["liquidity_stress"]["books"][1]["severities"]["severe"]["days2_30"] = None
    om = LQ.run(cm, res)
    ap = {x["test"]: x for x in om["applicability"]}
    ck("a missing days-2-to-30 rate stops the 30-day test (not filled with an invented value) and names the input",
       om["run_30"]["status"] == "inputs_missing" and "Fund share settlement" in om["run_30"]["missing"][0] and ap["run_30"]["inputs"] == "missing")
    ck("the intraday test still runs: it needs only day-1 inputs", om["intraday"].get("status") in ("covered", "short_intraday", "short_at_close"))
    ck("stablecoin is not applicable when the engagement issues none", ap["stablecoin_reserves"]["applies"] == "not applicable" and out["stablecoin"] == [])
    cs = copy.deepcopy(c)
    cs["liquidity_stress"]["books"].append(dict(id="coin", type="stablecoin", name="Stablecoin", balance={"entered": 1000},
                                                severities={"severe": {"day1": 0.2, "days2_30": 0.3}}, hourly=[1] * 9,
                                                reserves=[dict(name="T-bills", amount=900, haircut=0.0, same_day=False), dict(name="Cash", amount=150, haircut=0, same_day=True)]))
    co = LQ.run(cs, res)["stablecoin"][0]
    ck("stablecoin reserves: coverage after haircuts and same-day reserves against day-1 redemptions",
       abs(co["coverage"] - 1.05) < 1e-9 and co["same_day_reserves"] == 150 and co["day1_redemptions"] == 200 and co["same_day_covers_day1"] is False)
    cl_ = copy.deepcopy(c); cl_["liquidity_stress"]["line"]["available_from"] = 36; cl_["liquidity_stress"]["stress_day"]["month"] = 3
    ol = LQ.run(cl_, res)
    ck("a line not yet available in the stress month is left out and says so", "after the stress month" in ol.get("line_note", "") and not any(s["name"] == "Contingency line" for s in ol["intraday"]["steps"]))

    # ------------------------------------------------------------ endpoints, records, staleness
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
        su = cl.post("/api/v31/stress/liquidity/setup", json={"cfg": c}).json()
        ck("setup support lists the deposit products, the draft template and the LCR categories",
           len(su["deposit_products"]) == 6 and su["template"]["books"] and su["lcr_categories"]["operational"]["rate"] == 0.25 and su["errors"] == [])
        ex = cl.post("/api/v31/stress/liquidity", json={"cfg": c, "slug": "eng"}).json()
        ck("without store the result is returned and nothing is kept", ex["stored"] is False and not store.list_stress_runs("eng", user="u1"))
        ck("the endpoint result equals the module result", ex["result"]["intraday"]["lowest_cushion"] == out["intraday"]["lowest_cushion"])
        fm = cl.post("/api/v31/stress/liquidity", json={"cfg": c, "slug": "eng", "store": True}).json()
        rec = fm["record"]
        ck("a stored liquidity run is a record with its baseline archived, current on the same settings",
           rec["record_type"] == "liquidity" and rec["state"] == "current" and rec.get("archive") and rec["liquidity_fingerprint"] == LQ.fingerprint(c))
        c2 = copy.deepcopy(c); c2["liquidity_stress"]["books"][0]["severities"]["severe"]["day1"] = 0.3
        ck("it goes stale when the liquidity settings change", stress.run_state(rec, c2) == "stale")
        c3 = copy.deepcopy(c); c3["liquidity_stress"]["version"] = 99
        ck("a version bump alone does not make it stale (identity is the settings, not the counter)", stress.run_state(rec, c3) == "current")
        c4 = copy.deepcopy(c); c4["assumptions"]["tax_rate"] = (c4["assumptions"].get("tax_rate") or .21) + .01
        ck("it goes stale when the base changes", stress.run_state(rec, c4) == "stale")
        lst = cl.post("/api/v31/stress/runs", json={"cfg": c, "slug": "eng"}).json()["records"]
        ck("liquidity records are listed with the stress runs", any(r["run_id"] == rec["run_id"] and r["state"] == "current" for r in lst))
        # on a stored stress run: the stressed balance sheet is the projection
        k_co = key_for(c, lambda r: r["product_name"] == "Commercial Real Estate" and r["field"] == "charge_off_ann")
        sc = dict(id="cre", name="CRE", kind="idiosyncratic", version=1, funding="inherit",
                  severities=[dict(id="severe", label="Severe", overrides=[dict(target=k_co, op="multiply", value=25, start=1, end=None)])])
        c["stress_scenarios"] = [sc]
        run = cl.post("/api/v31/stress/run", json={"cfg": c, "slug": "eng", "runs": [{"scenario_id": "cre"}], "attribution": False}).json()["records"][0]
        sr = cl.post("/api/v31/stress/liquidity", json={"cfg": c, "slug": "eng", "run_id": run["run_id"], "store": True}).json()
        srec = sr["record"]
        ck("on a stress run, the projection is the stored stressed result and the record links to it",
           srec["parent_run_id"] == run["run_id"] and sr["result"]["projection"].startswith("CRE") and srec["state"] == "current")
        sbs = store.load_stress_archive("eng", run, "stress_result", user="u1")["financials"]["bs"]
        mm = sr["result"]["month"]
        ck("stressed resources come from the stressed balance sheet", abs(sr["result"]["ladder"][0]["amount"] - sbs["cash"][mm]) < 1e-3)
        c5 = copy.deepcopy(c); c5["stress_scenarios"][0]["severities"][0]["overrides"][0]["value"] = 30
        ck("a liquidity run on a stress run goes stale when that scenario changes", stress.run_state(srec, c5) == "stale")
        bad = cl.post("/api/v31/stress/liquidity", json={"cfg": c, "slug": "eng", "run_id": "nope"})
        ck("an unknown projection run is refused", bad.status_code == 404)
        cbad = copy.deepcopy(c); cbad["liquidity_stress"]["books"][0]["hourly"] = [1]
        bad2 = cl.post("/api/v31/stress/liquidity", json={"cfg": cbad, "slug": "eng"})
        ck("an invalid setup is refused by name at the endpoint", bad2.status_code == 422 and "hourly" in bad2.json()["error"])
        A.app.dependency_overrides.clear()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print(f"\n{sum(results)} passed, {len(results) - sum(results)} failed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
