"""r504: the three corrections from the r503 review, each on the reviewer's own case.

1. A loan roll-forward origination count (loan_rollforward.count_spec) is a flow: delayed two periods,
   1, 2, 3, 4, 5 becomes 0, 0, 1, 2, 3. Classification reads the whole path, so a role's headcount (also
   "count_spec") stays a level, and a bare count with no recognised context must be chosen.
2. The LCR never reads a missing run-off component as zero.
3. The exported workbook carries the Reporting settings sheet.
"""
import copy
import io
import os
import shutil
import tempfile

from . import liquidity as LQ, stress
from .tests_r369_lending_contracts import config as rollforward_config
from .tests_r498_stress import BANK, key_for
from .tests_r502_liquidity import trust_bank, base_of

results = []


def ck(name, ok, detail=""):
    results.append(bool(ok))
    print(("  PASS  " if ok else "  FAIL  ") + name + ("" if ok else f" :: {str(detail)[:400]}"))


def scen(overrides, sid="s"):
    return dict(id=sid, name=sid, kind="idiosyncratic", version=1, funding="inherit", severities=[dict(id="x", label="X", overrides=overrides)])


def main():
    # ============================================================ 1. the reviewer's origination field
    c = rollforward_config(24)
    k = key_for(c, lambda r: r["kind"] == "series" and r["field"] == "loan_rollforward.count_spec")
    par, fld, spec, *_ = stress.resolve_target(c, k)
    par[fld] = stress._rewrite(spec, "level", [float(i) for i in range(1, 25)], 12)   # entered monthly new loans 1, 2, 3, ...
    row = next(r for r in stress.targets(c) if r["key"] == k)
    ck("loan_rollforward.count_spec is a flow, read from its full path", row["econ_class"] == "flow" and "loan roll-forward" in row["econ_basis"], row)
    pr = stress.probe_target(c, k)
    ck("the input can be stressed (zero-shock rewrite reproduces the base)", pr["ok"], pr)
    cc, res = stress.build_config(c, scen([dict(target=k, op="delay", value=2, start=1)]), "x", modes={k: pr["mode"]})
    new = stress._resolve_path(stress.resolve_target(cc, k)[2], pr["mode"], 24, 12)
    ck("reviewer's case: originations 1, 2, 3, 4, 5 delayed two periods are 0, 0, 1, 2, 3", new[:5] == [0.0, 0.0, 1.0, 2.0, 3.0], new[:5])
    ck("the disclosure names the class, the default fill and the volume pushed past the horizon",
       res[0]["delay"]["econ_class"] == "flow" and res[0]["delay"]["fill_policy"] == "zero" and res[0]["delay"]["shifted_past_horizon"] == 23 + 24)
    c["stress_scenarios"] = [scen([dict(target=k, op="delay", value=2, start=1)], sid="late")]
    rec = stress.run_scenario(c, c["stress_scenarios"][0], keep_results=True)[0]
    rec.pop("_results", None)
    ck("the delayed origination scenario runs with its checks passed", rec["status"] == "completed" and rec["checks"]["zero_shock"] == "passed", rec.get("errors"))
    ck("loan size in the roll-forward is a price (held), not a flow",
       next(r for r in stress.targets(c) if r["field"] == "loan_rollforward.loan_size_spec")["econ_class"] == "price")
    b = copy.deepcopy(BANK)
    roles = [r for r in stress.targets(b) if r["field"].startswith("nie_detail.workforce.roles") and r["field"].endswith("count_spec")]
    ck("a role's headcount (also 'count_spec') is a level, so both counts are told apart by context",
       roles and all(r["econ_class"] == "quantity" for r in roles))
    ck("monetary originations are a flow: the scalar per-period amount and a per-period series",
       next(r for r in stress.targets(b) if r["field"] == "originations_per_period")["econ_class"] == "flow"
       and stress.econ_class(("lending_products", "[#0]", "originations_spec"), "money") == "flow"
       and stress.econ_class(("loan_production", "origination_amount_spec"), "money") == "flow")
    ck("a bare count or amount with no recognised context is 'other': the user must choose the fill",
       stress.econ_class(("widgets", "count_spec"), "count") == "other" and stress.econ_class(("widgets", "amount_spec"), "money") == "other"
       and stress.DELAY_FILL["other"] is None)

    # ============================================================ 2. the LCR never reads a missing component as zero
    c = trust_bank()
    c["liquidity_stress"]["books"][1].update(balance={"entered": 100.0}, severities={"severe": {"day1": None, "days2_30": 0.40}})
    c["liquidity_stress"]["books"][1]["lcr"] = {"rate": None}
    res = stress._engine_run(base_of(c))
    o = LQ.run(c, res)
    ap = {x["test"]: x for x in o["applicability"]}
    ck("reviewer's case: settlement book of 100, day-1 missing, 40% days 2 to 30, no override: the LCR is not calculated",
       o["lcr"]["status"] == "inputs_missing" and ap["lcr"]["inputs"] == "missing" and "outflow_rows" not in o["lcr"], o["lcr"])
    ck("the LCR names the missing component and how to supply it",
       any("day-1 run-off" in m and "LCR override" in m for m in o["lcr"]["missing"]), o["lcr"].get("missing"))
    ck("the daily test also stops, so neither view treats the gap as zero", o["run_30"]["status"] == "inputs_missing")
    c2 = copy.deepcopy(c); c2["liquidity_stress"]["books"][1]["lcr"] = {"rate": 0.45}
    o2 = LQ.run(c2, res)
    rw = next(r for r in o2["lcr"]["outflow_rows"] if r["category"] == "Fund share settlement")
    ck("an entered LCR override replaces the derived rate: the LCR runs at 45% and is tagged an engagement assumption",
       o2["lcr"]["status"] == "calculated" and abs(rw["rate"] - 0.45) < 1e-12 and abs(rw["outflow"] - 45.0) < 1e-9 and rw["source"] == "engagement")
    c3 = copy.deepcopy(trust_bank()); c3["liquidity_stress"]["books"][0]["operational_share"] = None
    o3 = LQ.run(c3, res)
    ck("a custody book without its operational share does not default to 0% operational", o3["lcr"]["status"] == "inputs_missing"
       and any("operational share" in m for m in o3["lcr"]["missing"]))
    try:
        LQ._lcr_block(c["liquidity_stress"], None, 1, [], [], None); guarded = False
    except RuntimeError as e:
        guarded = "read as zero" in str(e)
    ck("the LCR calculation itself refuses incomplete inputs, even if called directly", guarded)
    full = LQ.run(trust_bank(), res)
    ck("a complete setup still calculates the LCR", full["lcr"]["status"] == "calculated")

    # ============================================================ 3. the exported workbook carries the settings sheet
    tmp = tempfile.mkdtemp()
    os.environ["FOUNDRY_DATA_DIR"] = tmp
    try:
        import importlib
        from fastapi.testclient import TestClient
        from openpyxl import load_workbook
        from foundry import store
        importlib.reload(store)
        import app as A
        A.app.dependency_overrides[A.gate] = lambda: "u1"
        cl = TestClient(A.app)
        c = copy.deepcopy(BANK)
        k_co = key_for(c, lambda r: r["product_name"] == "Commercial Real Estate" and r["field"] == "charge_off_ann")
        c["stress_reporting"] = {"policy_minimums": {"leverage": {"value": 21.5, "source": "capital policy 2026"}}, "window_periods": 24}
        c["stress_scenarios"] = [scen([dict(target=k_co, op="multiply", value=10, start=1)], sid="cre")]
        rec = cl.post("/api/v31/stress/run", json={"cfg": c, "slug": "eng", "runs": [{"scenario_id": "cre"}], "attribution": False}).json()["records"][0]
        r = cl.post("/api/v31/stress/export", json={"cfg": c, "slug": "eng", "run_ids": [rec["run_id"]], "report_run_id": rec["run_id"]})
        wb = load_workbook(io.BytesIO(r.content))
        ck("reviewer's case: the exported workbook includes the Reporting settings sheet", "Reporting settings" in wb.sheetnames, wb.sheetnames)
        ws = wb["Reporting settings"]
        rows = [[c_.value for c_ in row_] for row_ in ws.iter_rows()]
        iss = store.list_report_issues("eng", user="u1")[0]
        ck("the sheet carries the fingerprint recorded for the issued package",
           ["Fingerprint", iss["settings_fingerprint"]] in [x[:2] for x in rows], rows[:3])
        ck("the sheet carries the policy minimum with its source, and the window",
           ["Policy minimum: leverage", 21.5, "capital policy 2026"] in [x[:3] for x in rows] and ["Window (periods)", 24] in [x[:2] for x in rows], rows)
        ck("Tables X and Y and the capital sheets are still there", "Table X Balance Sheet" in wb.sheetnames and "Table Y Income Statement" in wb.sheetnames)
        A.app.dependency_overrides.clear()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print(f"\n{sum(results)} passed, {len(results) - sum(results)} failed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
