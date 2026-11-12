"""r498 acceptance checks for stage-1 stress testing (override runner, validation, run records).

Each check names the review requirement it covers.
"""
import copy
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

from . import stress
from .tests_r485_linked_deposit_originations import linked

ROOT = Path(__file__).resolve().parents[2]
BANK = json.loads((ROOT / "foundry/fixtures/universal_template_bank.json").read_text())
results = []


def ck(name, ok, detail=""):
    results.append(bool(ok))
    print(("  PASS  " if ok else "  FAIL  ") + name + ("" if ok else f" :: {str(detail)[:400]}"))


def key_for(cfg, pred):
    rows = [r for r in stress.targets(cfg) if pred(r)]
    assert rows, "no target"
    stress.assign_stable_ids(cfg, rows[0]["locator"])
    return next(r for r in stress.targets(cfg) if r["locator"] == rows[0]["locator"])["key"]


def sc(overrides, sid="s1", name="Test", funding="inherit", sev="moderate"):
    return dict(id=sid, name=name, kind="economic", version=1, funding=funding,
                severities=[dict(id=sev, label=sev.title(), overrides=overrides)])


def main():
    # ---------------------------------------------------------- identity, catalog, dormancy
    c = copy.deepcopy(BANK)
    k_co = key_for(c, lambda r: r["product_name"] == "Commercial Real Estate" and r["field"] == "charge_off_ann")
    ck("a product input has a stable key once the product carries an ID", k_co.startswith("lending_products:sid-"), k_co)
    c2 = copy.deepcopy(c)
    lp = c2["assumptions"]["lending_products"]
    lp[0]["name"] = "CRE (renamed)"
    lp.append(lp.pop(0))
    _p, _f, v, prod, *_ = stress.resolve_target(c2, k_co)
    ck("the key still resolves after rename and reordering", prod["name"] == "CRE (renamed)" and v == BANK["assumptions"]["lending_products"][0]["charge_off_ann"])
    c3 = copy.deepcopy(c)
    c3["assumptions"]["lending_products"][0]["_scenario_off"] = True
    try:
        stress.resolve_target(c3, k_co); ok = False
    except stress.StressError as e:
        ok = "not active" in str(e)
    ck("an input of a switched-off product is rejected as inactive (dormant inputs are not overrides)", ok)
    ck("schedule points, dated anchors and timing settings are not offered as targets",
       not any(r["field"].split(".")[-1].isdigit() or "start_period" in r["field"] for r in stress.targets(c)))

    # ---------------------------------------------------------- structural validation
    bad = sc([dict(target="lending_products:nope:charge_off_ann", op="multiply", value=2, start=1),
              dict(target=k_co, op="divide", value=2, start=1),
              dict(target=k_co, op="multiply", value=2, start=5)])
    chk = stress.check_scenario(c, bad)
    txt = " | ".join(chk["errors"])
    ck("missing targets, unknown operations and part-horizon shocks of one-value settings are rejected with the named input",
       not chk["ok"] and "no lending product has ID 'nope'" in txt and "operation must be" in txt
       and "Commercial Real Estate · Charge off annual: this setting has one value" in txt, txt)
    dup = copy.deepcopy(c)
    dup["assumptions"]["lending_products"][1]["stable_id"] = dup["assumptions"]["lending_products"][0]["stable_id"]
    ck("an ambiguous ID is rejected", any("share ID" in e for e in stress.check_scenario(dup, sc([dict(target=k_co, op="multiply", value=2, start=1)]))["errors"]))
    k_ox = key_for(c, lambda r: r["field"].startswith("nie_detail.categories.[#0].flow_spec"))
    ov = stress.check_scenario(c, sc([dict(target=k_ox, op="multiply", value=1.2, start=1, end=12),
                                      dict(target=k_ox, op="add", value=1000, start=10, end=20)]))
    ck("two overrides on the same input in overlapping periods are rejected", any("overlaps override 1" in e for e in ov["errors"]), ov)

    # ---------------------------------------------------------- zero shock and base immutability
    base_cfg = copy.deepcopy(c)
    base_res = stress._engine_run(base_cfg)
    s1 = sc([dict(target=k_co, op="multiply", value=2, start=1), dict(target=k_ox, op="multiply", value=1.3, start=13, end=24)])
    c["stress_scenarios"] = [s1]
    before = json.dumps({k: v for k, v in c.items() if k != "stress_scenarios"}, sort_keys=True)
    zc, _ = stress.build_config(c, s1, "moderate", identity=True, modes={k_ox: stress.probe_target(c, k_ox)["mode"]})
    ck("zero shock reproduces the base financial series exactly", stress._comparable(stress._engine_run(zc)) == stress._comparable(base_res))
    recs = stress.run_scenario(c, s1, base_res=base_res)
    r = recs[0]
    ck("the run completes with structural and zero-shock checks passed",
       r["status"] == "completed" and r["checks"] == {"structural": "passed", "zero_shock": "passed"}, r.get("errors"))
    ck("the base configuration is unchanged after a successful run", json.dumps({k: v for k, v in c.items() if k != "stress_scenarios"}, sort_keys=True) == before)
    ck("charge-offs ×2 lower cumulative net income", r["stress"]["metrics"]["cum_ni"] < r["base"]["metrics"]["cum_ni"])
    ox = r["resolved_overrides"][1]
    ck("a windowed shock changes only its window (M13 to M24) and reports base and stressed values",
       ox["start"] == 13 and abs(ox["stressed_at_start"] - 1.3 * ox["base_at_start"]) < 1e-6, ox)
    sc2c, _ = stress.build_config(c, s1, "moderate", modes={k_ox: ox["mode"]})
    _p, _f, spec, *_ = stress.resolve_target(sc2c, k_ox)
    path = spec["values"]
    _p0, _f0, spec0, *_ = stress.resolve_target(c, k_ox)
    base_path = stress._resolve_path(spec0, ox["mode"], 36, 12)
    ck("periods outside the window keep base values exactly", path[:12] == base_path[:12] and path[24:] == base_path[24:]
       and all(abs(a - 1.3 * b) < 1e-9 for a, b in zip(path[12:24], base_path[12:24])))
    att = r["attribution"]
    ck("attribution is isolated one-at-a-time with an interaction residual and reconciles to the total",
       att["method"].startswith("isolated") and abs(sum(x["effect"] for x in att["rows"]) + att["interaction"] - att["total"]) < 1e-6
       and abs(att["total"] - (r["stress"]["metrics"]["cum_ni"] - r["base"]["metrics"]["cum_ni"])) < 1e-6, att)

    failed = stress.run_scenario(c, sc([dict(target="lending_products:nope:x", op="multiply", value=2, start=1)], sid="s1"), base_res=base_res)[0]
    ck("a failed run is recorded as failed with the error, never as a result column",
       failed["status"] == "failed" and "no lending product has ID 'nope'" in failed["errors"][0] and "stress" not in failed)
    ck("the base configuration is unchanged after a failed run", json.dumps({k: v for k, v in c.items() if k != "stress_scenarios"}, sort_keys=True) == before)
    cf = copy.deepcopy(c)
    k_fee = key_for(cf, lambda r: "fee_streams" in r["field"] and r["kind"] == "series" and "stock_multiplier" in r["field"])
    pf = stress.run_scenario(cf, sc([dict(target=k_fee, op="multiply", value=0.5, start=1)], sid="s1"))[0]
    ck("an input the model reads in a form a scenario cannot rewrite fails the zero-shock check, by name",
       pf["status"] == "failed" and pf["checks"]["zero_shock"] == "failed" and "cannot rewrite yet" in pf["errors"][0], pf["errors"])

    # ---------------------------------------------------------- stale and current
    ck("a fresh record is current", stress.run_state(r, c) == "current")
    c_edit = copy.deepcopy(c); c_edit["stress_scenarios"][0]["severities"][0]["overrides"][0]["value"] = 3
    ck("editing the scenario marks its record stale", stress.run_state(r, c_edit) == "stale")
    c_base = copy.deepcopy(c); c_base["assumptions"]["tax_rate"] = (c_base["assumptions"].get("tax_rate") or 0) + 0.01
    ck("changing the base marks the record stale", stress.run_state(r, c_base) == "stale")
    c_id = copy.deepcopy(c); c_id["stress_scenarios"][0]["name"] = "Renamed only"
    ck("renaming a scenario does not mark results stale", stress.run_state(r, c_id) == "current")

    # ---------------------------------------------------------- propagation through links (r485 deposit link)
    L = linked(24, 12)
    k_dep = key_for(L, lambda r: r["product_name"] == "Portfolio Partnerships" and r["field"] == "opening_balance")
    k_pct = key_for(L, lambda r: r["field"] == "loan_rollforward.percentage_spec")
    up = sc([dict(target=k_dep, op="multiply", value=0.8, start=1)], sid="u")
    L["stress_scenarios"] = [up]
    ru = stress.run_scenario(L, up)[0]
    ck("an upstream deposit shock completes", ru["status"] == "completed", ru.get("errors"))
    sL, _ = stress.build_config(L, up, "moderate")
    loan = stress._engine_run(sL)["products"][0]
    dep = [p for p in stress._engine_run(sL)["products"] if p["name"] == "Portfolio Partnerships"][0]
    base_loan = stress._engine_run({k: v for k, v in L.items() if k != "stress_scenarios"})["products"][0]
    ck("the deposit shock reaches linked originations exactly once (originations = shocked balance × 1.176471%, below base)",
       all(abs(a - b * 0.01176471) < 1e-6 for a, b in zip(loan["linkedOriginations"], loan["linkedSourceBalance"]))
       and loan["linkedSourceBalance"][0] < base_loan["linkedSourceBalance"][0])
    both = sc([dict(target=k_dep, op="multiply", value=0.8, start=1), dict(target=k_pct, op="multiply", value=0.5, start=1)], sid="u")
    L["stress_scenarios"] = [both]
    rb = stress.run_scenario(L, both)[0]
    ck("an independent downstream driver (conversion %) can be shocked with the upstream deposit; both are named inputs",
       rb["status"] == "completed" and len(rb["attribution"]["rows"]) == 2, rb.get("errors"))
    ck("linked results are not offered as inputs", not any("linkedOriginations" in r["field"] or r["field"].endswith("origq") for r in stress.targets(L)))

    # ---------------------------------------------------------- funding policy
    F = copy.deepcopy(BANK)
    wipe = []
    for p in F["assumptions"]["deposit_products"]:
        for fld in ("opening_balance", "new_deposits_per_period"):
            if isinstance(p.get(fld), (int, float)):
                wipe.append(dict(target=key_for(F, lambda r, n=p["name"], f=fld: r["product_name"] == n and r["field"] == f),
                                 op="multiply", value=0.0, start=1))
    drain = sc(wipe, sid="f")
    F["stress_scenarios"] = [drain]
    rf = stress.run_scenario(F, drain, attribution=False)[0]
    m = rf["stress"]["metrics"]
    drain_b = dict(drain, funding="automatic_borrowing")
    F["stress_scenarios"] = [drain_b]
    rfb = stress.run_scenario(F, drain_b, attribution=False)[0]
    mb = rfb["stress"]["metrics"]
    ck("automatic borrowing is applied only when the scenario says so",
       mb["funding_policy"] == "automatic_borrowing" and mb["peak_replacement_borrowing"] > 0
       and F["assumptions"].get("funding_shortfall_policy", "show_shortfall") == "show_shortfall", mb)
    ck("unfunded shortfall, replacement borrowing and borrowing expense are reported separately",
       all(k in m for k in ("max_unfunded_shortfall", "peak_replacement_borrowing", "borrowing_expense")))

    # ---------------------------------------------------------- fixed schedule stays fixed
    fixed = [r for r in stress.targets(c) if r["kind"] == "series" and r["trajectory"] == "explicit" and r["family"] == "bank"]
    if fixed:
        fx = fixed[0]
        before_vals = copy.deepcopy(stress.resolve_target(c, key_for(c, lambda r: r["locator"] == fx["locator"]))[2])
        sc3, _ = stress.build_config(c, s1, "moderate", modes={k_ox: ox["mode"]})
        after_vals = stress.resolve_target(sc3, key_for(sc3, lambda r: r["locator"] == fx["locator"]))[2]
        ck("an entered schedule that is not shocked stays exactly as authored", before_vals == after_vals)

    # ---------------------------------------------------------- export and endpoints
    from .stress_export import stress_workbook
    wb = stress_workbook([r, failed], lambda x: stress.run_state(x, c))
    met = {row[0]: row for row in wb["Stress Metrics"].iter_rows(values_only=True)}
    ck("the export carries the stored metrics exactly",
       met["Cumulative net income, full horizon"][2] == r["base"]["metrics"]["cum_ni"]
       and met["Cumulative net income, full horizon"][3] == r["stress"]["metrics"]["cum_ni"])
    runs = list(wb["Stress Runs"].iter_rows(values_only=True))
    ck("failed runs are exported with their status and error", any(x[3] == "failed" and "nope" in (x[14] or "") for x in runs[1:]))

    d = tempfile.mkdtemp(); old = os.environ.get("FOUNDRY_DATA_DIR"); os.environ["FOUNDRY_DATA_DIR"] = d
    try:
        for k, v in (("FOUNDRY_USER", "klaros"), ("FOUNDRY_PASS", "test123"), ("FOUNDRY_COOKIE_SECURE", "0")):
            os.environ.setdefault(k, v)
        sys.path.insert(0, str(ROOT))
        import app as A
        A.app.dependency_overrides[A.gate] = lambda: "u1"
        from fastapi.testclient import TestClient
        cl = TestClient(A.app)
        t = cl.post("/api/v31/stress/targets", json={"cfg": c}).json()
        ck("targets endpoint lists inputs with keys", any(x["key"] == k_co for x in t["targets"]))
        out = cl.post("/api/v31/stress/run", json={"cfg": c, "slug": "stress-test", "runs": [{"scenario_id": "s1"}]}).json()
        ck("run endpoint stores records automatically", out["stored"] and out["records"][0]["status"] == "completed" and out["records"][0]["state"] == "current")
        listed = cl.post("/api/v31/stress/runs", json={"cfg": c, "slug": "stress-test"}).json()["records"]
        ck("stored records list back with their state", len(listed) == 1 and listed[0]["state"] == "current")
        listed2 = cl.post("/api/v31/stress/runs", json={"cfg": c_base, "slug": "stress-test"}).json()["records"]
        ck("stored records are marked stale against a changed base, not overwritten", listed2[0]["state"] == "stale" and listed2[0]["run_id"] == listed[0]["run_id"])
        x = cl.post("/api/v31/stress/export", json={"cfg": c, "slug": "stress-test", "run_ids": [listed[0]["run_id"]]})
        ck("export endpoint returns a workbook of the stored record", x.status_code == 200 and x.content[:2] == b"PK")
    finally:
        try:
            A.app.dependency_overrides.clear()
        except Exception:
            pass
        shutil.rmtree(d, ignore_errors=True)
        if old is None:
            os.environ.pop("FOUNDRY_DATA_DIR", None)
        else:
            os.environ["FOUNDRY_DATA_DIR"] = old

    print(f"{sum(results)} passed, {len(results) - sum(results)} failed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
