"""r503 corrective checks, one block per finding in the r499-r502 review. Each uses the reviewer's own case
where one was given, and checks the arithmetic independently of the module under test.
"""
import copy
import os
import shutil
import tempfile

from . import actions as ACT, liquidity as LQ, reverse_stress as RS, stress, stress_report as SR
from .tests_r498_stress import BANK, key_for
from .tests_r502_liquidity import trust_bank, base_of

results = []


def ck(name, ok, detail=""):
    results.append(bool(ok))
    print(("  PASS  " if ok else "  FAIL  ") + name + ("" if ok else f" :: {str(detail)[:400]}"))


def scen(overrides, sid="s", kind="idiosyncratic"):
    return dict(id=sid, name=sid, kind=kind, version=1, funding="inherit", severities=[dict(id="x", label="X", overrides=overrides)])


def main():
    # ============================================================ 1. delay follows what the input is
    c = copy.deepcopy(BANK)
    k_new = key_for(c, lambda r: r["kind"] == "series" and r["field"].endswith("new_customers"))
    par, fld, spec, *_ = stress.resolve_target(c, k_new)
    par[fld] = stress._rewrite(spec, "level", [float(i) for i in range(1, 37)], 12)   # an entered monthly count: 1, 2, 3, ...
    row = next(r for r in stress.targets(c) if r["key"] == k_new)
    ck("an origination count is classed as a flow from its contract, not from which rewrite reproduces the base",
       row["econ_class"] == "flow" and next(e for e in stress.registry(c) if e["key"] == k_new)["delay_fill"] == "zero")
    pr = stress.probe_target(c, k_new)
    cc, res = stress.build_config(c, scen([dict(target=k_new, op="delay", value=2, start=1)]), "x", modes={k_new: pr["mode"]})
    new = stress._resolve_path(stress.resolve_target(cc, k_new)[2], pr["mode"], 36, 12)
    ck("reviewer's case: 1, 2, 3, 4, 5 delayed two periods is 0, 0, 1, 2, 3 (no originations during the delay)",
       new[:5] == [0.0, 0.0, 1.0, 2.0, 3.0], (pr["mode"], new[:5]))
    d = res[0]["delay"]
    ck("the delay discloses the class, the fill and where the fill came from",
       d["econ_class"] == "flow" and d["fill_policy"] == "zero" and d["fill_source"] == "class default" and d["shifted_past_horizon"] == 35 + 36)
    cc2, res2 = stress.build_config(c, scen([dict(target=k_new, op="delay", value=2, start=1, fill="hold")]), "x", modes={k_new: pr["mode"]})
    new2 = stress._resolve_path(stress.resolve_target(cc2, k_new)[2], pr["mode"], 36, 12)
    ck("an explicit fill overrides the class default and is disclosed as chosen", new2[:3] == [1.0, 1.0, 1.0] and res2[0]["delay"]["fill_source"] == "chosen")
    k_fte = key_for(c, lambda r: r["kind"] == "series" and r["field"].endswith("driver_specs.ftes"))
    ck("a headcount is a quantity and a delay holds its level", next(r for r in stress.targets(c) if r["key"] == k_fte)["econ_class"] == "quantity")
    k_oth = key_for(c, lambda r: r["kind"] == "series" and r["field"].endswith("driver.params.coefficient"))
    chk = stress.check_scenario(c, scen([dict(target=k_oth, op="delay", value=2, start=1)]))
    ck("an input outside the contract cannot be delayed until the fill is chosen", not chk["ok"] and any("choose what fills the delay" in e for e in chk["errors"]), chk["errors"])
    chk2 = stress.check_scenario(c, scen([dict(target=k_oth, op="delay", value=2, start=1, fill="hold")]))
    ck("with a chosen fill it is accepted", chk2["ok"], chk2["errors"])
    chk3 = stress.check_scenario(c, scen([dict(target=k_new, op="delay", value=2, start=1, fill="carry")]))
    ck("an unknown fill is refused by name", not chk3["ok"] and any("zero or held" in e for e in chk3["errors"]))

    # ============================================================ 2. reverse stress never reports "no breach" from failures
    c = copy.deepcopy(BANK)
    k_co = key_for(c, lambda r: r["product_name"] == "Commercial Real Estate" and r["field"] == "charge_off_ann")
    c["stress_reporting"] = {"policy_minimums": {"leverage": {"value": 22.0, "source": "test"}}}
    real = stress._engine_run
    try:
        def boom(cfg_):
            raise RuntimeError("engine failure (forced)")
        stress._engine_run = boom
        base_res = real(base_of(c))
        r_all = RS.run(c, dict(kind="change", target=k_co, op="multiply", lo=1, hi=5, grid=3), base_res=base_res)
        ck("reviewer's case: every evaluation fails, so the status is 'search failed', not 'no breach'",
           r_all["status"] == "search_failed" and r_all["breaking_point"] is None and r_all["failed_evaluations"] == 3
           and all(e.get("error") for e in r_all["evaluations"]), r_all["status"])
        calls = {"n": 0}

        def half(cfg_):
            calls["n"] += 1
            if calls["n"] % 2 == 0:
                raise RuntimeError("engine failure (forced)")
            return real(cfg_)
        stress._engine_run = half
        r_half = RS.run(c, dict(kind="change", target=k_co, op="multiply", lo=1, hi=5, grid=4), base_res=base_res)
        ck("some evaluations failed and none of the rest breached: 'inconclusive', with the failures in the limitations",
           r_half["status"] == "inconclusive" and "failed" in r_half["limitations"][0], (r_half["status"], r_half["limitations"][:1]))
    finally:
        stress._engine_run = real
    c0 = copy.deepcopy(BANK); c0["stress_reporting"] = {}
    k0 = key_for(c0, lambda r: r["product_name"] == "Commercial Real Estate" and r["field"] == "charge_off_ann")
    r_nt = RS.run(c0, dict(kind="change", target=k0, op="multiply", lo=1, hi=5, grid=3, tiers=["policy"]))
    ck("no applicable threshold (policy tier selected, none set): no evaluation can say 'no breach'",
       r_nt["status"] == "search_failed" and "no capital measure with an applicable threshold" in r_nt["evaluations"][0]["error"])
    ok = RS.run(c, dict(kind="change", target=k_co, op="multiply", lo=1, hi=5, grid=5))
    ck("a clean search with no breach still reports 'no breach within bounds'", ok["status"] == "no_breach_within_bounds" and ok["failed_evaluations"] == 0)

    # ============================================================ 3. the contingency line is a constrained facility
    from .engine_q_a import run_pf_a
    from .engine_q_b import run_pf_b
    from .tests_funding_policy import config as fconfig
    for profile, runner in (("pf_a", run_pf_a), ("pf_b", run_pf_b)):
        f = fconfig(profile)
        f["assumptions"].update(securities_afs=[{"name": "Assets", "opening": 1500000., "yield_ann": 0.}], borrow_rate_ann=0.5,
                                funding_shortfall_policy="contingency_facility",
                                contingency_facility=dict(capacity=300000., available_from=3, rate_ann=0.10))
        r = runner(f)
        fu = r["funding"]
        draws, cash = fu["automatic_borrowing"], fu["cash_position"]
        ck(f"{profile}: nothing is drawn before the line is available (periods 0 to 2)", all(x == 0 for x in draws[:3]), draws[:4])
        ck(f"{profile}: draws never exceed the commitment; the rest of the deficit stays unfunded",
           max(draws) <= 300000. + 1e-6 and abs(draws[3] - 300000.) < 1e-6 and cash[3] < -1 and not fu["feasible"], (draws[3], cash[3]))
        ie = r["is"].get("borrExp") or r["is"].get("intBorrow")
        k = 4 if profile == "pf_b" else 4
        exp_rate = 0.10
        got = ie[k] if len(ie) > k else None
        ppy = 4 if profile == "pf_b" else int(f["assumptions"].get("periods_per_year") or 12)
        ck(f"{profile}: the drawn balance is priced at the line's own rate, not the general borrowing rate",
           got is not None and abs(got - 300000. * exp_rate / ppy) < 1.0, (got, 300000. * exp_rate / ppy))
    a_cfg, info = ACT.apply(base_of(BANK), [dict(type="contingency_line", capacity=20000, spread_bp=150, commitment_fee_bp=25, available_from=12)])
    A = a_cfg["assumptions"]
    ck("the line action sets a facility (capacity, availability, own rate) and leaves the general borrowing rate alone",
       A["funding_shortfall_policy"] == "contingency_facility" and A["contingency_facility"]["capacity"] == 20000 * 1000.0
       and A["contingency_facility"]["available_from"] == 12 and A["borrow_rate_ann"] == base_of(BANK)["assumptions"].get("borrow_rate_ann")
       and abs(A["contingency_facility"]["rate_ann"] - ((base_of(BANK)["assumptions"].get("borrow_rate_ann") or 0) + 0.015)) < 1e-12)
    big = base_of(BANK)
    for p in big["assumptions"]["lending_products"]:
        p["opening_balance"] = (p.get("opening_balance") or 0) * 25
    b_cfg, _ = ACT.apply(big, [dict(type="contingency_line", capacity=20000, spread_bp=150, commitment_fee_bp=25, available_from=12)])
    rb = stress._engine_run(b_cfg)["funding"]
    ck("a shortfall far larger than the line: draws capped at the commitment from period 12; the rest is unfunded",
       max(rb["automatic_borrowing"]) <= 20000 * 1000.0 + 1e-3 and max(rb["automatic_borrowing"][:12]) == 0 and max(rb["unfunded_cash"]) > 0)

    # ============================================================ 4-7. liquidity
    c = trust_bank()
    res = stress._engine_run(base_of(c))
    c4 = copy.deepcopy(c)
    c4["liquidity_stress"]["books"][1]["severities"]["severe"]["day1"] = None
    o4 = LQ.run(c4, res)
    ap = {x["test"]: x for x in o4["applicability"]}
    ck("reviewer's case: a missing day-1 rate stops the daily test too; the book is never skipped behind a 'complete' result",
       o4["run_30"]["status"] == "inputs_missing" and ap["run_30"]["inputs"] == "missing"
       and any("day-1 run-off" in m for m in o4["run_30"]["missing"]), o4["run_30"])
    # 5. no extrapolation past day 30
    try:
        LQ.run_30([(0.0, 100.0, None, None)], 1000.0, 0.0, 90); refused = False
    except LQ.LiquidityError:
        refused = True
    ck("reviewer's case: a 90-day run without an after-day-30 assumption is refused, not extrapolated", refused)
    r90 = LQ.run_30([(0.0, 100.0, 0.0, None)], 1000.0, 0.0, 90)
    ck("with nothing after day 30, a book of 100 loses exactly 100 over 90 days (the 30-day path stops at day 30)",
       abs(sum(r90["outflows"]) - 100.0) < 0.015 and r90["outflows"][30] == 0 and r90["closes"][-1] == r90["closes"][29], sum(r90["outflows"]))   # daily values are rounded to 0.001
    r90b = LQ.run_30([(10.0, 29.0, 30.0, None)], 1000.0, 0.0, 90)
    ck("an after-day-30 assumption is spread over days 31 to 90 only", abs(sum(r90b["outflows"][30:]) - 30.0) < 1e-9 and abs(sum(r90b["outflows"]) - 69.0) < 1e-9)
    c5 = copy.deepcopy(c); c5["liquidity_stress"]["stress_day"]["run_days"] = 90
    o5 = LQ.run(c5, res)
    ck("a 90-day run names the missing after-day-30 inputs per book", o5["run_30"]["status"] == "inputs_missing" and any("after day 30" in m for m in o5["run_30"]["missing"]))
    c5b = copy.deepcopy(c5)
    c5b["liquidity_stress"]["books"][0]["severities"]["severe"]["days31_plus"] = 0.5
    ck("run-off over the whole run cannot exceed the balance", any("whole run cannot exceed" in e for e in LQ.validate(c5b)))
    # 6. one eligibility answer for every view
    c6 = copy.deepcopy(c)
    c6["liquidity_stress"]["line"]["available_from"] = 30
    c6["liquidity_stress"]["stress_day"]["month"] = 1
    o6 = LQ.run(c6, res)
    ld = o6["lcr"]["line_draw"]
    ck("reviewer's case: a line unavailable at the stress date is a labeled hypothetical in the LCR, not a source",
       ld["basis"] == "hypothetical" and not ld["eligible"] and "Hypothetical" in ld["notes"][0] and not o6["line_state"]["eligible"])
    ck("the same line is left out of the intraday test and the daily run",
       not any(s_["name"] == "Contingency line" for s_ in o6["intraday"]["steps"]) and not o6["run_30"].get("with_line"))
    o6b = LQ.run(c, res)
    ck("an available line is a feasible draw", o6b["lcr"]["line_draw"]["basis"] == "feasible" and o6b["line_state"]["eligible"])
    # 7. no double counting
    c7 = copy.deepcopy(c)
    c7["liquidity_stress"]["resources"].append(dict(id="fed2", name="Fed cash again", balance=dict(bs="cash", share=1.0), available="08:00", haircut=0, hqla="1"))
    ck("reviewer's case: two resources each taking 100% of projected cash are refused",
       any("same balance cannot be counted twice" in e for e in LQ.validate(c7)), LQ.validate(c7))
    c7b = copy.deepcopy(c)
    c7b["liquidity_stress"]["resources"][0]["balance"] = dict(bs="cash", share=0.6)
    c7b["liquidity_stress"]["resources"].append(dict(id="tsy", name="Treasury cash", balance=dict(entered=10_000_000, within="cash"), available="08:00", haircut=0, hqla="1"))
    try:
        LQ.run(c7b, res); raised = False
    except LQ.LiquidityError as e:
        raised = "counted twice" in str(e)
    ck("an entered resource declared part of projected cash cannot exceed the cash left unallocated", raised)
    c7c = copy.deepcopy(c)
    c7c["liquidity_stress"]["books"].append(dict(id="dup", type="deposits", name="Sweep again", balance=dict(deposit_keys=["name:Sweep / Program"]),
                                                 severities={"severe": {"day1": 0.1, "days2_30": 0.1}}, hourly=[1] * 9))
    ck("a deposit product cannot sit in two redemption books", any("already in" in e for e in LQ.validate(c7c)))
    ck("the LCR is labeled a simplified management calculation, and a rule rate is not a qualification finding",
       "Simplified management calculation" in o6b["lcr"]["method"] and "not that the balance has been shown to qualify" in o6b["lcr"]["method"])
    ck("post-draw capital is labeled an illustration, with the full economics in management actions",
       any("not a rerun" in n for n in o6b["lcr"]["line_draw"]["notes"]))

    # ============================================================ 8. report rows join by key
    base_rows = [("g:assets", "Assets"), ("cash", "Cash", [1.0]), ("?htm", "HTM", [0.0]), ("afs", "AFS", [2.0])]
    stress_rows = [("g:assets", "Assets"), ("cash", "Cash", [1.0]), ("?htm", "HTM", [5.0]), ("?hfs", "HFS", [7.0]), ("afs", "AFS", [3.0])]
    try:
        rows = SR._rows(base_rows, stress_rows); err = None
    except Exception as e:
        rows, err = [], e
    by = {r.get("key"): r for r in rows if r.get("kind") != "group"}
    ck("reviewer's case: HTM on one side only no longer fails, and rows are matched by key, not position",
       err is None and by["afs"]["base"] == [2.0] and by["afs"]["stress"] == [3.0] and by["htm"]["base"] == [0.0] and by["htm"]["stress"] == [5.0], (err, by.get("afs")))
    ck("a row present on one side only is unavailable on the other, not zero", by["hfs"]["available"] is False)
    ck("the union keeps the stressed-only row in its place", [r.get("key") for r in rows if r.get("kind") != "group"] == ["cash", "htm", "hfs", "afs"])
    q = SR._rows([("cash", "Cash", [1.0]), ("?htm", "HTM", [0.0])], [("cash", "Cash", [1.0]), ("?htm", "HTM", [0.0])])
    ck("a conditional row with no balance in either case is left out", [r["key"] for r in q] == ["cash"])

    # ============================================================ reporting settings identity, issued packages
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
        c = copy.deepcopy(BANK)
        k_co = key_for(c, lambda r: r["product_name"] == "Commercial Real Estate" and r["field"] == "charge_off_ann")
        c["stress_reporting"] = {"policy_minimums": {"leverage": {"value": 20.0, "source": "policy v1"}}}
        c["stress_scenarios"] = [dict(scen([dict(target=k_co, op="multiply", value=10, start=1)], sid="cre"))]
        rec = cl.post("/api/v31/stress/run", json={"cfg": c, "slug": "eng", "runs": [{"scenario_id": "cre"}], "attribution": False}).json()["records"][0]
        ck("each run keeps the reporting settings in force when it ran, with a fingerprint",
           rec["reporting_settings"]["policy_minimums"]["leverage"]["value"] == 20.0 and len(rec["reporting_settings_fingerprint"]) == 16)
        c2 = copy.deepcopy(c); c2["stress_reporting"]["policy_minimums"]["leverage"]["value"] = 24.0
        j = cl.post("/api/v31/stress/report", json={"cfg": c2, "slug": "eng", "run_id": rec["run_id"]}).json()
        ck("after a policy change the report says the settings changed since the run", j["settings_changed_since_run"] and j["settings_basis"] == "current")
        ja = cl.post("/api/v31/stress/report", json={"cfg": c2, "slug": "eng", "run_id": rec["run_id"], "basis": "as_run"}).json()
        ck("the report can be rebuilt on the settings the run used",
           ja["settings_basis"] == "as_run" and ja["report"]["settings_used"]["policy_minimums"]["leverage"]["value"] == 20.0
           and ja["report"]["settings_fingerprint"] == rec["reporting_settings_fingerprint"])
        ex = cl.post("/api/v31/stress/export", json={"cfg": c2, "slug": "eng", "run_ids": [rec["run_id"]], "report_run_id": rec["run_id"]})
        iss = store.list_report_issues("eng", user="u1")
        ck("an exported package is recorded with the run, the settings it used and their fingerprint",
           ex.status_code == 200 and len(iss) == 1 and iss[0]["run_id"] == rec["run_id"] and iss[0]["settings"]["policy_minimums"]["leverage"]["value"] == 24.0
           and iss[0]["settings_fingerprint"] == j["current_settings_fingerprint"])
        # a failed search is not stored as formal evidence
        c3 = copy.deepcopy(BANK); c3["stress_reporting"] = {}
        k3 = key_for(c3, lambda r: r["product_name"] == "Commercial Real Estate" and r["field"] == "charge_off_ann")
        bad = cl.post("/api/v31/stress/reverse", json={"cfg": c3, "slug": "eng", "formal": True,
                                                       "spec": dict(kind="change", target=k3, op="multiply", lo=1, hi=5, grid=3, tiers=["policy"])})
        ck("a failed search cannot be promoted to a formal record", bad.status_code == 422 and "nothing to record" in bad.json()["error"])
        A.app.dependency_overrides.clear()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print(f"\n{sum(results)} passed, {len(results) - sum(results)} failed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
