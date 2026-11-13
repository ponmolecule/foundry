"""r500 acceptance checks: scenario classes and coverage, calibration records, combined scenarios from frozen
parts, the reference-rate parallel shift with both directions, and the delay operation.

Each check names the plan item it covers.
"""
import copy

from . import stress
from .stress import RATE_KEY
from .tests_r498_stress import BANK, key_for, sc

results = []


def ck(name, ok, detail=""):
    results.append(bool(ok))
    print(("  PASS  " if ok else "  FAIL  ") + name + ("" if ok else f" :: {str(detail)[:400]}"))


def cal(**k):
    return dict(dict(rationale="Great Recession peak CRE losses", source="FDIC QBP 2009-2010", period="2009Q1-2010Q4",
                     applicability="CRE book", approval="reviewed"), **k)


def sev(overrides, sid="severe", label="Severe"):
    return dict(id=sid, label=label, overrides=overrides)


def scen(sid, kind, overrides, **kw):
    return dict(dict(id=sid, name=sid, kind=kind, version=1, funding="inherit", severities=[sev(overrides)]), **kw)


def cum_ni(res, n=36):
    return sum(float(x or 0) for x in res["financials"]["is"]["ni"][:n])


def main():
    c = copy.deepcopy(BANK)
    k_co = key_for(c, lambda r: r["product_name"] == "Commercial Real Estate" and r["field"] == "charge_off_ann")
    k_ch = key_for(c, lambda r: r["kind"] == "series" and r["field"].startswith("cac_feeds.") and r["unit_kind"] == "count")

    # ------------------------------------------------------------ rate path: parallel shift
    reg = {e["key"]: e for e in stress.registry(c)}
    ck("the reference rate path is a supported input (basis points, whole horizon)", RATE_KEY in reg and reg[RATE_KEY]["unit_kind"] == "bp")
    pr = stress.probe_target(c, RATE_KEY)
    ex = pr.get("exposure") or {}
    ck("rate exposure lists what reprices and what keeps its rate",
       pr["ok"] and any("MMDA" in x for x in ex.get("reprice", [])) and any("Time Deposits" in x for x in ex.get("fixed", []))
       and "Cash yield" in ex.get("bank_yields_shifted", []), ex)
    up = scen("rates", "macro", [dict(target=RATE_KEY, op="add", value=200, start=1, end=None, calibration=cal())])
    c["stress_scenarios"] = [up]
    rec = stress.run_scenario(c, up, keep_results=True)[0]
    res = rec.pop("_results")
    ck("a +200 bp shift runs with the zero-shock check passed", rec["status"] == "completed" and rec["checks"]["zero_shock"] == "passed", rec.get("errors"))
    direct = copy.deepcopy({k: v for k, v in c.items() if k not in stress.STRESS_KEYS})
    direct["scenario_overlays"] = {"rate_shock_bp": 200}
    dr = stress._engine_run(direct)
    ck("the shift reproduces the engine's own parallel rate shock exactly", stress._comparable(dr) == stress._comparable(res["stress_res"]))
    rd = rec.get("rate_direction") or {}
    a, m = rd.get("applied", {}), rd.get("mirrored", {})
    ck("both directions run; the mirrored shift is recorded", rd.get("applied_bp") == 200 and rd.get("mirrored_bp") == -200 and a and m, rd)
    ck("adverse direction is judged per measure from the two runs",
       rd["adverse_for_earnings"] == (200 if a["cum_ni"] <= m["cum_ni"] else -200)
       and rd["adverse_for_capital"] == (200 if a["min_leverage"] <= m["min_leverage"] else -200)
       and rd["agree"] == (rd["adverse_for_earnings"] == rd["adverse_for_capital"]))
    ck("this bank is asset-sensitive: the down shift is adverse for earnings", rd["adverse_for_earnings"] == -200)
    ro = rec["resolved_overrides"][0]
    ck("the resolved override carries the calibration record and the exposure note",
       ro["calibration"]["source"] == "FDIC QBP 2009-2010" and ro["mode"] == "rate" and "fixed-rate" in ro["note"])
    bad = []
    for o, why in ((dict(target=RATE_KEY, op="multiply", value=2, start=1), "basis points"),
                   (dict(target=RATE_KEY, op="add", value=200, start=13), "whole horizon"),
                   (dict(target=RATE_KEY, op="add", value=5000, start=1), "between -1000 and 1000")):
        chk = stress.check_scenario(c, scen("x", "macro", [o]))
        bad.append(not chk["ok"] and any(why in e for e in chk["errors"]))
    ck("rate shift rejects relative operations, partial windows and implausible sizes, by name", all(bad), bad)
    two = stress.check_scenario(c, scen("x", "macro", [dict(target=RATE_KEY, op="add", value=100, start=1),
                                                       dict(target=RATE_KEY, op="add", value=100, start=1)]))
    ck("two rate shifts in one severity conflict", not two["ok"] and any("overlaps" in e for e in two["errors"]))

    # ------------------------------------------------------------ delay
    ck("delay shifts the path right and fills vacated periods",
       stress._apply([1, 2, 3, 4, 5, 6], "delay", 2, 1, None, fill=0) == [0, 0, 1, 2, 3, 4]
       and stress._apply([1, 2, 3, 4, 5, 6], "delay", 2, 3, None, fill=9) == [1, 2, 9, 9, 3, 4])
    dl = scen("slow", "idiosyncratic", [dict(target=k_ch, op="delay", value=6, start=1, end=None, calibration=cal(rationale="EHR partner channel slips two quarters"))])
    c["stress_scenarios"] = [dl]
    dres = stress.run_scenario(c, dl, keep_results=True)[0]
    dd = dres.pop("_results")
    ck("a six-month acquisition delay runs with the zero-shock check passed", dres["status"] == "completed" and dres["checks"]["zero_shock"] == "passed", dres.get("errors"))
    disc = dres["resolved_overrides"][0].get("delay") or {}
    ck("the delay names its driver type, fill rule and what was shifted past the horizon",
       disc.get("periods") == 6 and disc.get("driver") in ("new-volume flow", "level path") and disc.get("fill") and "committed costs" in disc.get("note", ""), disc)
    mode = dres["resolved_overrides"][0]["mode"]
    base_path = stress._resolve_path(stress.resolve_target(dd["base_cfg"], k_ch)[2], mode, 36, 12)
    new_path = stress._resolve_path(stress.resolve_target(dd["stress_cfg"], k_ch)[2], mode, 36, 12)
    ck("the delayed path is the base path moved six periods later", new_path[6:] == base_path[:30] and all(abs(x - (0.0 if mode == "flow" else base_path[0])) < 1e-12 for x in new_path[:6]))
    if mode == "flow":
        ck("volume shifted past the horizon is disclosed and equals the base path's last six periods",
           abs(disc["shifted_past_horizon"] - sum(base_path[30:])) < 1e-6)
    ck("a delay changes results (it is not a no-op)", not dres["no_effect"])
    k_sc = key_for(c, lambda r: r["kind"] == "scalar" and r["family"] == "lending_products")
    for o, why in ((dict(target=k_sc, op="delay", value=3, start=1), "cannot be delayed"),
                   (dict(target=k_ch, op="delay", value=0, start=1), "whole number of periods"),
                   (dict(target=k_ch, op="delay", value=2.5, start=1), "whole number of periods"),
                   (dict(target=k_ch, op="delay", value=3, start=1, end=24), "runs to the horizon")):
        chk = stress.check_scenario(c, scen("x", "idiosyncratic", [o]))
        ck(f"delay validation: {why}", not chk["ok"] and any(why in e for e in chk["errors"]), chk["errors"])

    # ------------------------------------------------------------ classes, calibration, coverage
    for k in ("macro", "idiosyncratic", "combined", "sensitivity", "economic", "method_comparison"):
        assert stress.check_scenario(c, scen("x", k, [dict(target=k_co, op="multiply", value=2, start=1, calibration=cal())]))["ok"], k
    ck("all scenario classes are accepted", True)
    ck("an unknown class is rejected", not stress.check_scenario(c, scen("x", "doom", [dict(target=k_co, op="multiply", value=2, start=1)]))["ok"])
    w = stress.check_scenario(c, scen("x", "macro", [dict(target=k_co, op="multiply", value=2, start=1)]))
    ck("a missing calibration record is a warning, not an error", w["ok"] and any("calibration record" in x for x in w["warnings"]))
    ck("an invalid approval status is an error",
       not stress.check_scenario(c, scen("x", "macro", [dict(target=k_co, op="multiply", value=2, start=1, calibration=cal(approval="signed"))]))["ok"])
    macro_rates = scen("m1", "macro", [dict(target=RATE_KEY, op="add", value=-200, start=1, calibration=cal())])
    cv = stress.coverage(dict(c, stress_scenarios=[macro_rates]))
    ck("coverage warns when a macroeconomic scenario stresses rates alone",
       any("credit deterioration" in x for x in cv["warnings"]) and not cv["complete"])
    macro = scen("m2", "macro", [dict(target=RATE_KEY, op="add", value=-200, start=1, calibration=cal()),
                                 dict(target=k_co, op="multiply", value=2.5, start=1, calibration=cal())])
    idio = scen("i1", "idiosyncratic", [dict(target=k_ch, op="delay", value=6, start=1, calibration=cal())])
    idio_dup = scen("i2", "idiosyncratic", [dict(target=k_co, op="multiply", value=1.5, start=1, calibration=cal())])
    cv2 = stress.coverage(dict(c, stress_scenarios=[macro, idio, idio_dup]))
    ck("a macro scenario with credit deterioration passes; an idiosyncratic duplicate of a macro input is flagged",
       not any("credit deterioration" in x for x in cv2["warnings"]) and any("i2" in x and "complement" in x for x in cv2["warnings"])
       and not any(x.startswith("i1") for x in cv2["warnings"]))

    # combined: frozen parts, conflict rule, staleness of parts
    frozen = [dict(scenario_id="m2", name="m2", version=1, severity_id="severe"), dict(scenario_id="i1", name="i1", version=1, severity_id="severe")]
    comb = scen("c1", "combined", macro["severities"][0]["overrides"] + idio["severities"][0]["overrides"], parts=frozen)
    cfg3 = dict(c, stress_scenarios=[macro, idio, comb])
    cv3 = stress.coverage(cfg3)
    ck("macroeconomic, idiosyncratic and combined coverage is complete", cv3["complete"] and cv3["counts"]["combined"] == 1, cv3)
    ck("a combined scenario built from frozen parts passes its checks", stress.check_scenario(cfg3, comb)["ok"])
    macro_v2 = dict(copy.deepcopy(macro), version=2)
    w4 = stress.check_scenario(dict(c, stress_scenarios=[macro_v2, idio, comb]), comb)
    ck("editing a part after freezing is reported; the frozen copy still runs unchanged",
       w4["ok"] and any("changed since it was frozen" in x for x in w4["warnings"]))
    clash = scen("c2", "combined", macro["severities"][0]["overrides"] + idio_dup["severities"][0]["overrides"], parts=frozen)
    ck("two parts changing the same input over overlapping periods is a conflict", not stress.check_scenario(cfg3, clash)["ok"])
    ck("the composition rule is stated", "conflict" in cv3["rule"])
    c["stress_scenarios"] = [macro, idio, comb]
    crec = stress.run_scenario(c, comb)[0]
    ck("the combined scenario runs: rate shift, credit and delay together, with attribution reconciled",
       crec["status"] == "completed" and len(crec["attribution"]["rows"]) == 3
       and abs(sum(r["effect"] for r in crec["attribution"]["rows"]) + crec["attribution"]["interaction"] - crec["attribution"]["total"]) < 1e-6
       and crec.get("rate_direction"), crec.get("errors"))

    # ------------------------------------------------------------ export
    from .stress_export import stress_workbook
    wb = stress_workbook([rec, dres, crec])
    ovs = wb["Stress Overrides"]
    hdr = [x.value for x in ovs[1]]
    rows = [[x.value for x in r] for r in ovs.iter_rows(min_row=2)]
    ck("export carries calibration records and the delay disclosure",
       {"Rationale", "Data source", "Approval", "Delay disclosure"} <= set(hdr)
       and any(r[hdr.index("Data source")] == "FDIC QBP 2009-2010" for r in rows)
       and any((r[hdr.index("Delay disclosure")] or "").startswith("6 periods") for r in rows))
    ck("export carries the rate-direction evidence", "Stress Rate Direction" in wb.sheetnames and wb["Stress Rate Direction"].max_row >= 3)

    # ------------------------------------------------------------ endpoint
    import app as A
    from fastapi.testclient import TestClient
    A.app.dependency_overrides[A.gate] = lambda: "u1"
    j = TestClient(A.app).post("/api/v31/stress/coverage", json={"cfg": cfg3}).json()
    A.app.dependency_overrides.clear()
    ck("coverage endpoint returns counts, warnings and the rule", j.get("complete") and "rule" in j)

    print(f"\n{sum(results)} passed, {len(results) - sum(results)} failed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
