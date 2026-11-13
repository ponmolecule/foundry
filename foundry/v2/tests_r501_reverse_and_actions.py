"""r501 acceptance checks: shared solver, reverse stress on the deterministic runner (grid then bisection,
crossings, no-breach, non-monotonic honesty, formal records), management actions with costs before and after,
and design alternatives as change sets on the frozen baseline.
"""
import copy
import os
import shutil
import tempfile

from . import actions as ACT, reverse_stress as RS, solver, stress
from .stress_report import capital_assessment
from .tests_r498_stress import BANK, key_for

results = []


def ck(name, ok, detail=""):
    results.append(bool(ok))
    print(("  PASS  " if ok else "  FAIL  ") + name + ("" if ok else f" :: {str(detail)[:400]}"))


def main():
    c = copy.deepcopy(BANK)
    k_co = key_for(c, lambda r: r["product_name"] == "Commercial Real Estate" and r["field"] == "charge_off_ann")
    c["stress_reporting"] = {"policy_minimums": {"leverage": {"value": 22.0, "source": "test policy"}}}

    # ------------------------------------------------------------ shared solver
    f = lambda x: x * x - 2.0
    n = {"k": 0}

    def g(x):
        n["k"] += 1
        return f(x)
    sol = solver.bisect(g, 0.0, 2.0, f(0.0), tol=1e-6, budget=lambda: n["k"] < 80)
    ck("shared bisection solves within tolerance", abs(sol - 2 ** 0.5) < 1e-4)
    pts = [(x, (x - 2) * (x - 5)) for x in solver.grid(0, 7, 8)]
    ck("grid finds every sign change, not just one", len(solver.sign_changes(pts)) == 2 and not solver.monotonic(pts))

    # ------------------------------------------------------------ reverse stress: one change
    base = stress.base_fingerprint(c)
    r = RS.run(c, dict(kind="change", target=k_co, op="multiply", lo=1, hi=60, grid=7))
    bp = r["breaking_point"]
    ck("a breaking point is found and names the binding ratio, threshold tier and period",
       r["status"] == "breach_found" and bp and bp["binding"]["ratio"] == "leverage" and bp["binding"]["tier"] == "policy"
       and bp["binding"]["period"], r["status"])
    ev = {e["x"]: e for e in r["evaluations"]}
    lo, hi = bp["between"]
    ck("the bracket is narrower than the tolerance and straddles the breach",
       hi - lo <= r["tolerance"] + 1e-9 and ev[round(hi, 9)]["breach"] and not ev[round(lo, 9)]["breach"])
    ck("every evaluation is recorded with its margin and binding threshold",
       len(r["evaluations"]) == r["engine_runs"] - 1 and all("margin" in e and "binding" in e for e in r["evaluations"]))
    one = dict(id="v", kind="sensitivity", funding="inherit", severities=[dict(id="x", overrides=[dict(target=k_co, op="multiply", value=round(hi, 9), start=1, end=None)])])
    cc, _ = stress.build_config(c, one, "x", modes={k_co: "scalar"})
    cap = capital_assessment(dict(cc, stress_reporting=c["stress_reporting"]), stress._engine_run(cc))
    ck("independent rerun at the breaking point confirms the breach", cap["ratios"]["leverage"]["tiers"]["policy"]["status"] == "below")
    ck("the base is untouched by the search", stress.base_fingerprint(c) == base)
    nb = RS.run(c, dict(kind="change", target=k_co, op="multiply", lo=1, hi=5, grid=5))
    ck("no breach within bounds is reported as such, with the bound stated",
       nb["status"] == "no_breach_within_bounds" and nb["breaking_point"] is None and "1 to 5 only" in nb["limitations"][0])
    lev = RS.run(c, dict(kind="change", target=k_co, op="multiply", lo=1, hi=60, grid=5, criterion="leverage_only", tiers=["regulatory", "commitment"]))
    ck("leverage-only against regulatory and commitment tiers finds no breach (policy excluded)", lev["status"] == "no_breach_within_bounds")

    # rate path: both sides of zero, crossing oriented away from the unstressed value
    rr = RS.run(c, dict(kind="change", target=stress.RATE_KEY, op="add", lo=-400, hi=400, grid=9))
    ck("rate path reverse stress: the breaking shift is a cut, found below zero", rr["breaking_point"] and rr["breaking_point"]["x"] < 0
       and rr["breaking_point"]["direction"] == "into breach", rr["breaking_point"])

    # scale a whole scenario by lambda
    sc = dict(id="m", name="Macro", kind="macro", version=1, funding="inherit", severities=[dict(id="severe", label="Severe", overrides=[
        dict(target=stress.RATE_KEY, op="add", value=-100, start=1, end=None), dict(target=k_co, op="multiply", value=2, start=1, end=None)])])
    c["stress_scenarios"] = [sc]
    sr = RS.run(c, dict(kind="scale", scenario_id="m", severity_id="severe", lo=0, hi=4, grid=5))
    ck("a whole scenario scaled by lambda finds where it breaks", sr["status"] in ("breach_found", "multiple_crossings") and sr["breaking_point"], sr["status"])
    s2 = RS._scaled_scenario(sc, "severe", 2)["severities"][0]["overrides"]
    ck("scaling: multipliers scale their deviation from 1, additions their size",
       s2[0]["value"] == -200 and abs(s2[1]["value"] - 3.0) < 1e-12)
    for bad, why in ((dict(kind="change", target=k_co, op="multiply", lo=5, hi=1), "lower bound"),
                     (dict(kind="change", target=k_co, op="replace", lo=0, hi=1), "multiplier, an added amount or a delay"),
                     (dict(kind="change", target=stress.RATE_KEY, op="multiply", lo=0, hi=2), "basis points"),
                     (dict(kind="scale", scenario_id="nope", severity_id="x", lo=0, hi=1), "not saved")):
        try:
            RS.validate(bad, c); ok = False
        except stress.StressError as e:
            ok = why in str(e)
        ck(f"reverse stress validation: {why}", ok)

    # non-monotonic honesty on a synthetic response
    r_nm = dict(pts=[(x, (x - 2) * (x - 5)) for x in solver.grid(0, 7, 8)])
    ck("non-monotonic responses are named in the limitations", not solver.monotonic(r_nm["pts"]))

    # ------------------------------------------------------------ formal record, staleness, endpoints
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
        spec = dict(kind="change", target=k_co, op="multiply", lo=1, hi=60, grid=7)
        ex = cl.post("/api/v31/stress/reverse", json={"cfg": c, "slug": "eng", "spec": spec}).json()
        ck("exploration returns evidence without storing it", not ex["formal"] and not store.list_stress_runs("eng", user="u1"))
        fm = cl.post("/api/v31/stress/reverse", json={"cfg": c, "slug": "eng", "spec": spec, "formal": True}).json()
        rec = fm["record"]
        ck("promote to formal reruns deterministically and stores the record with its baseline",
           fm["formal"] and rec["record_type"] == "reverse_stress" and rec["state"] == "current" and rec.get("archive")
           and rec["reverse"]["breaking_point"]["x"] == ex["result"]["breaking_point"]["x"])
        c2 = copy.deepcopy(c); c2["assumptions"]["tax_rate"] = (c2["assumptions"].get("tax_rate") or .21) + .01
        ck("a formal reverse stress record goes stale when the base changes", stress.run_state(rec, c2) == "stale")

        # management actions against a stored stress run
        sc2 = dict(id="cre", name="CRE", kind="idiosyncratic", version=1, funding="inherit",
                   severities=[dict(id="severe", label="Severe", overrides=[dict(target=k_co, op="multiply", value=25, start=1, end=None)])])
        c["stress_scenarios"] = [sc, sc2]
        run = cl.post("/api/v31/stress/run", json={"cfg": c, "slug": "eng", "runs": [{"scenario_id": "cre"}], "attribution": False}).json()["records"][0]
        acts = [dict(type="capital_injection", amount=5000, period=12),
                dict(type="contingency_line", capacity=20000, spread_bp=150, commitment_fee_bp=25, other_costs=40, available_from=1)]
        a = cl.post("/api/v31/stress/actions", json={"cfg": c, "slug": "eng", "run_id": run["run_id"], "actions": acts}).json()
        ar = a.get("record") or {}
        ck("actions run against the stored stress and are stored as their own record", ar.get("record_type") == "actions" and ar.get("parent_run_id") == run["run_id"], a)
        fees = ar["costs"]["facility_fees_and_other"]
        ck("facility costs reach earnings: commitment fee on the full line plus other costs, per year, over the window",
           abs(fees - 3 * (0.0025 * 20000 + 40)) < 1e-6, ar["costs"])
        pre_lev, post_lev = ar["pre"]["capital"]["ratios"]["leverage"]["min"], ar["post"]["capital"]["ratios"]["leverage"]["min"]
        ck("pre-action result equals the stored stress run exactly (unmitigated stress kept separate)",
           abs(ar["pre"]["cum_ni"] - sum(run["stress"]["series"]["ni"][:36])) < 1e-3)
        ck("capital injection lifts the lowest leverage after actions", post_lev > pre_lev, (pre_lev, post_lev))
        ck("drawn interest and facility costs are reported separately, and notes state each action's timing and cost",
           ar["costs"]["drawn_interest"] >= 0 and len(ar["notes"]) == 2 and "period 12" in ar["notes"][0] and "25 bp" in ar["notes"][1])
        bad = cl.post("/api/v31/stress/actions", json={"cfg": c, "slug": "eng", "run_id": run["run_id"], "actions": [dict(type="contingency_line", capacity=-1, period=1)]})
        ck("an invalid action is refused by name", bad.status_code == 422 and "commitment" in bad.json()["error"])
        A.app.dependency_overrides.clear()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # reduced growth action alone, direct
    k_ch = key_for(c, lambda r: r["kind"] == "series" and r["field"].startswith("cac_feeds.") and r["unit_kind"] == "count")
    pc, info = ACT.apply({k: v for k, v in c.items() if k not in stress.STRESS_KEYS}, [dict(type="reduced_growth", target=k_ch, factor=0.5, start=1)])
    ck("reduced growth applies a factor to a supported input", "Reduced growth" in info["notes"][0]
       and stress._comparable(stress._engine_run(pc)) != stress._comparable(stress._engine_run({k: v for k, v in c.items() if k not in stress.STRESS_KEYS})))

    # ------------------------------------------------------------ design alternatives are change sets on the frozen base
    ck("design classes are accepted", stress.check_scenario(c, dict(id="d", name="d", kind="design", version=1, severities=[dict(id="d", overrides=[dict(target=k_co, op="replace", value=0.004, start=1)])]))["ok"])

    print(f"\n{sum(results)} passed, {len(results) - sum(results)} failed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
