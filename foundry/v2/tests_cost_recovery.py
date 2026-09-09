"""Regression tests for linked cost pools + cost-recovery fee pricing (r46).

Run: python3 -m foundry.v2.tests_cost_recovery
"""
from __future__ import annotations

import copy
import json
import subprocess
from pathlib import Path

from .cost_pools import cost_pool_series, cost_pool_series_map, resolve_cost_pool_ref
from .income_modules import fee_stream_q, _validate_fee_stream_shape
from .run_q import run_v2
from .validate_q import validate_config_v2, ConfigErrorV2


def _eq(a, b, tol=1e-7):
    return abs(float(a) - float(b)) <= tol


def _stream(ref="pool-platform", recovery=.90, markup=.10, markup_obj=None):
    params = {"recovery_pct": recovery}
    if markup_obj is None:
        params["markup"] = {"value": markup, "trajectory": "flat"}
    else:
        params["markup"] = markup_obj
    return {
        "name": "Platform services fee",
        "basis": "transaction",
        "driver": {"source": "cost_pool", "ref": ref, "trajectory": "flat", "params": {}},
        "rate": {"behavior": "cost_recovery", "params": params},
        "timing": {"start_period": 1},
        "cost": {"kind": "none", "params": {}},
    }


def _assumptions(ppy=12, n=12):
    return {
        "periods_per_year": ppy,
        "n_periods": n,
        "nie_detail": {
            "categories": [{
                "series_id": "opex-tech", "owner_module": "operating_expense",
                "name": "Technology", "per_quarter": 30_000.0, "trajectory": "flat",
            }],
            "workforce": {
                "mode": "roles", "default_payroll_load_rate": .25,
                "roles": [{
                    "series_id": "wf-count-platform", "compensation_series_id": "wf-comp-platform",
                    "expense_series_id": "wf-exp-platform", "owner_module": "operating_expense.workforce",
                    "role": "Platform operations", "count": 2, "annual_comp": 120_000.0,
                    "hire_period": 1,
                }],
            },
        },
        "cost_pools": [{
            "series_id": "pool-platform", "owner_module": "cost_pool",
            "name": "Platform Services Eligible Costs",
            "components": [
                {"kind": "operating_expense_category", "series_id": "opex-tech", "allocation_pct": .80},
                {"kind": "workforce_role_expense", "series_id": "wf-exp-platform", "allocation_pct": .40},
            ],
        }],
    }


def main():
    P = F = 0

    def ck(name, cond, detail=""):
        nonlocal P, F
        if cond:
            P += 1; print(f"PASS {name}")
        else:
            F += 1; print(f"FAIL {name}" + (f" — {detail}" if detail else ""))

    # --- source composition: component allocation is upstream and dimensionless ---
    a = _assumptions(12, 12)
    pool = a["cost_pools"][0]
    arr = cost_pool_series(pool, a, 12, 12)
    # Opex: 30k/q => 10k/mo * 80% = 8k/mo.
    # Workforce: 2 * 120k * 1.25 / 12 = 25k/mo * 40% = 10k/mo.
    ck("cost pool composes native-period Opex + Workforce flows with component allocations",
       len(arr) == 12 and all(_eq(x, 18_000.0) for x in arr))
    ck("cost pool stable ID resolves independently of display name",
       resolve_cost_pool_ref("pool-platform", a)["name"] == "Platform Services Eligible Costs")
    renamed = copy.deepcopy(a); renamed["cost_pools"][0]["name"] = "Renamed display label"
    ck("cost pool stable reference survives pool rename",
       all(_eq(x, 18_000.0) for x in cost_pool_series_map(renamed, 12, 12)["pool-platform"]))

    # --- pricing: recovery and markup stay separate; pool is not /ppy periodized again ---
    s = _stream()
    inc, opex = fee_stream_q(s, 1, {"cost_pool": {"pool-platform": 18_000.0}}, ppy=12)
    ck("cost recovery applies pool × recovery × (1 + markup)", _eq(inc, 17_820.0))
    ck("cost recovery observational link posts no fee-product expense", _eq(opex, 0.0))

    # Identical annual source economics in monthly vs quarterly cadence.
    aq = _assumptions(4, 4); am = _assumptions(12, 12)
    pq = cost_pool_series(aq["cost_pools"][0], aq, 4, 4)
    pm = cost_pool_series(am["cost_pools"][0], am, 12, 12)
    fq = sum(fee_stream_q(s, q, {"cost_pool": {"pool-platform": pq[q-1]}}, ppy=4)[0] for q in range(1, 5))
    fm = sum(fee_stream_q(s, q, {"cost_pool": {"pool-platform": pm[q-1]}}, ppy=12)[0] for q in range(1, 13))
    # annual eligible pool = 30k*4*.8 + 300k*.4 = 216k; fee = 216k*.9*1.1 = 213,840
    ck("cost recovery annual economics are quarterly/monthly cadence-stable",
       _eq(fq, 213_840.0) and _eq(fm, 213_840.0) and _eq(fq, fm))

    # Markup is a dimensionless Series level, including growth / explicit paths.
    growth_markup = {
        "value": .10, "trajectory": "growth",
        "growth_spec": {"rate": .50, "period": "year", "method": "step", "anchor": "model_year"},
    }
    sg = _stream(markup_obj=growth_markup)
    g1 = fee_stream_q(sg, 1, {"cost_pool": {"pool-platform": 100.0}}, ppy=4)[0]
    g5 = fee_stream_q(sg, 5, {"cost_pool": {"pool-platform": 100.0}}, ppy=4)[0]
    ck("markup Growth uses the standard Series level path without annualizing the cost pool",
       _eq(g1, 99.0) and _eq(g5, 103.5))
    explicit_markup = {
        "value": .10, "trajectory": "explicit_schedule", "period": "year", "resolution": "step",
        "schedule": {"1": .10, "2": .20},
    }
    se = _stream(markup_obj=explicit_markup)
    ck("explicit markup schedule changes pricing while preserving source dollars",
       _eq(fee_stream_q(se, 1, {"cost_pool": {"pool-platform": 100.0}}, ppy=12)[0], 99.0)
       and _eq(fee_stream_q(se, 24, {"cost_pool": {"pool-platform": 100.0}}, ppy=12)[0], 108.0))

    # --- fail-closed contract ---
    bad = copy.deepcopy(s); bad["basis"] = "balance"
    try: _validate_fee_stream_shape(bad); raised_basis = False
    except ValueError: raised_basis = True
    ck("cost_pool cannot masquerade as balance basis", raised_basis)

    bad = copy.deepcopy(s); bad["driver"]["trajectory"] = "derived"
    try: _validate_fee_stream_shape(bad); raised_traj = False
    except ValueError: raised_traj = True
    ck("cost_pool rejects derived coefficient semantics that would periodize recovery", raised_traj)

    bad = copy.deepcopy(s); bad["cost"] = {"kind": "per_unit", "params": {"per_unit": 1}}
    try: _validate_fee_stream_shape(bad); raised_cost = False
    except ValueError as e: raised_cost = "already posted" in str(e)
    ck("cost recovery rejects a second fee-product expense posting", raised_cost)

    bad = copy.deepcopy(s); bad["rate"]["params"]["recovery_pct"] = 1.25
    try: _validate_fee_stream_shape(bad); raised_recovery = False
    except ValueError: raised_recovery = True
    ck("recovery percentage fails closed outside 0..100%", raised_recovery)

    missing_ctx = False
    try: fee_stream_q(s, 1, {"cost_pool": {}}, ppy=12)
    except ValueError as e: missing_ctx = "unavailable" in str(e)
    ck("missing cost-pool evaluator context fails closed", missing_ctx)

    circular = copy.deepcopy(a)
    circular["nie_detail"]["workforce"]["roles"][0]["activation"] = {
        "metric": "managed_notional_end", "source": "Platform services", "operator": ">=", "value": 1,
    }
    try: cost_pool_series(circular["cost_pools"][0], circular, 12, 12); raised_circular = False
    except ValueError as e: raised_circular = "metric-triggered" in str(e) or "circular" in str(e)
    ck("metric-triggered Workforce expense is excluded from cost pools to avoid circularity", raised_circular)

    dup = copy.deepcopy(a)
    dup["cost_pools"][0]["components"].append(copy.deepcopy(dup["cost_pools"][0]["components"][0]))
    try: cost_pool_series(dup["cost_pools"][0], dup, 12, 12); duplicate_failed = False
    except ValueError as e: duplicate_failed = "duplicates" in str(e)
    ck("cost pool rejects duplicate inclusion of the same upstream Series", duplicate_failed)

    # --- full engine: linked pool creates fee income only; original NIE remains owned upstream ---
    def engine_pair(ppy):
        cfg = json.loads(Path("foundry/fixtures/parity/configs/pf_a_base.json").read_text())
        aa = cfg["assumptions"]
        aa.update(_assumptions(ppy, ppy))
        # Isolate the observational cost-pool contract from balance-sheet-sensitive
        # regulatory assessments: fee income legitimately changes assets, which can
        # change FDIC/OCC assessments without re-posting the linked upstream expense.
        aa["nie_detail"]["fdic_bp_ann"] = 0.0
        aa["nie_detail"]["occ_bp_ann"] = 0.0
        aa["obs_exposures"] = []
        base = copy.deepcopy(cfg)
        aa["obs_exposures"] = [{
            "name": "Affiliate Platform Services", "call_report_line": "obs", "_fee_product": True,
            "managed_notional": {"day1": 0, "trajectory": "flat"},
            "fee_streams": [_stream()],
        }]
        return run_v2(base)["financials"], run_v2(cfg)["financials"]

    bq, wq = engine_pair(4)
    bm, wm = engine_pair(12)
    # financial statement arrays are $000s, so annual fee delta should be 213.84.
    dq = sum(wq["is"]["fees"]) - sum(bq["is"]["fees"])
    dm = sum(wm["is"]["fees"]) - sum(bm["is"]["fees"])
    ck("full engine posts cost-recovery fee income in quarterly cadence", _eq(dq, 213.84, 1e-5))
    ck("full engine posts cost-recovery fee income in monthly cadence", _eq(dm, 213.84, 1e-5))
    ck("full engine cost-recovery fee is cadence-equivalent", _eq(dq, dm, 1e-5))
    ck("linked cost pool does not re-post upstream expense into Fee Product Costs",
       _eq(sum(wq["is"]["feeOpex"]) - sum(bq["is"]["feeOpex"]), 0.0)
       and _eq(sum(wm["is"]["feeOpex"]) - sum(bm["is"]["feeOpex"]), 0.0))
    # Because base and with-fee runs share identical Opex/Workforce assumptions, overhead
    # should remain identical; the only cost-recovery change is fee income.
    ck("linked cost pool leaves original Opex/Workforce expense posting unchanged",
       all(_eq(x, y, 1e-7) for x, y in zip(wq["is"]["overhead"], bq["is"]["overhead"]))
       and all(_eq(x, y, 1e-7) for x, y in zip(wm["is"]["overhead"], bm["is"]["overhead"])))

    # Config-level stable-ID/ref validation.
    valid_cfg = json.loads(Path("foundry/fixtures/parity/configs/pf_a_base.json").read_text())
    valid_cfg["assumptions"].update(_assumptions(4, 4))
    valid_cfg["assumptions"]["obs_exposures"] = [{
        "name": "Affiliate Platform Services", "call_report_line": "obs", "_fee_product": True,
        "managed_notional": {"day1": 0, "trajectory": "flat"}, "fee_streams": [_stream()],
    }]
    try: validate_config_v2(valid_cfg); valid_ok = True
    except ConfigErrorV2 as e:
        print("validation error", e); valid_ok = False
    ck("full config accepts stable cost-pool link", valid_ok)
    broken = copy.deepcopy(valid_cfg)
    broken["assumptions"]["obs_exposures"][0]["fee_streams"][0]["driver"]["ref"] = "missing-pool"
    try: validate_config_v2(broken); broken_failed = False
    except ConfigErrorV2 as e: broken_failed = "missing-pool" in str(e)
    ck("full config fails closed on broken cost-pool ref", broken_failed)
    empty = copy.deepcopy(valid_cfg)
    empty["assumptions"]["cost_pools"][0]["components"] = []
    try: validate_config_v2(empty); empty_failed = False
    except ConfigErrorV2 as e: empty_failed = "at least one eligible expense component" in str(e)
    ck("referenced empty cost pool fails closed instead of silently producing zero revenue", empty_failed)

    # Guide Me maps the generic mechanic without inventing Reg W or a sixth basis.
    from .fee_guide import validate_guide_plan, render_guide_plan, fee_guide_manifest
    guide_stream = {
        "name": "Platform services fee", "basis": "transaction",
        "driver_source": "cost_pool", "driver_trajectory": "flat",
        "driver_period": "not_applicable", "driver_resolution": "not_applicable",
        "stock_multiplier_trajectory": "not_applicable", "stock_multiplier_period": "not_applicable",
        "stock_multiplier_resolution": "not_applicable",
        "pricing_trajectory": "flat", "pricing_period": "not_applicable",
        "pricing_resolution": "not_applicable",
        "coefficient_kind": "not_applicable", "coefficient_period": "not_applicable",
        "coefficient_trajectory": "not_applicable", "flat_amount_trajectory": "not_applicable",
        "rate_behavior": "cost_recovery", "cost_kind": "none",
    }
    gplan = {"status": "plan", "product_label": "Affiliate platform services",
             "managed_notional_source": "not_needed", "streams": [guide_stream],
             "questions": [], "unsupported_mechanics": []}
    try:
        gv = validate_guide_plan(gplan); guide_ok = True
    except Exception as e:
        print("guide validation error", e); guide_ok = False; gv = None
    ck("Guide Me accepts cost_pool + transaction + cost_recovery without a new basis",
       guide_ok and gv["streams"][0]["basis"] == "transaction")
    rendered = render_guide_plan(gplan) if guide_ok else {"stream_guides": []}
    gst = " ".join(rendered.get("stream_guides", [{}])[0].get("steps", [])) if guide_ok else ""
    ck("Guide Me instructions preserve separate pool allocation, recovery, and markup controls",
       "Eligible / allocated" in gst and "Recovery" in gst and "Markup" in gst)
    mf = fee_guide_manifest()
    ck("Guide Me manifest exposes generic cost mechanics rather than Reg W ontology",
       any(x["id"] == "cost_pool" for x in mf["driver_sources"])
       and any(x["id"] == "cost_recovery" for x in mf["rate_behaviors"])
       and all(x["id"] != "reg_w" for x in mf["bases"]))

    # Browser contract: compact authoring keeps pool allocation, recovery, markup, and no-cost guard visible.
    html = Path("web/console_v2.html").read_text()
    ck("Fee Product UI exposes linked cost-pool source", "Cost pool — linked eligible expenses" in html)
    ck("Fee Product UI keeps pricing basis distinct from driver source", "Basis (calculation)" in html and "Basis (what it\'s charged on)" not in html)
    ck("Fee Product UI separates pool allocation from downstream recovery", "Eligible / allocated" in html and "Recovery (% of eligible cost pool)" in html)
    ck("Fee Product UI exposes Series-style Markup path", "Markup path" in html and "Markup schedule (%)" in html)
    ck("Fee Product UI makes observational no-repost guard explicit", "upstream costs already posted" in html)
    ck("Fee Product UI safely unwinds cost-pool-only state when basis changes", "feeStreamBasisChange" in html and 'st.driver.source==="cost_pool"&&v!=="transaction"' in html)
    ck("Fee Product UI provides a safe single-reference shared-pool delete path", "feeCostPoolDeleteFromStream" in html and "Delete pool" in html)

    # Execute the shipped renderer for an authored cost-recovery stream (not just string inventory).
    ha = html.index("function _feeCoeffScheduleText("); hb = html.index("function fieldsFor(", ha)
    fa = html.index("function fieldsFor("); fb = html.index("function lineOptionsFor", fa)
    hjs, fjs = html[ha:hb], html[fa:fb]
    node = (
        "const cfg={assumptions:{cac_feeds:{},nie_detail:{categories:[{series_id:'opex-tech',name:'Technology'}],workforce:{roles:[{series_id:'wf-count',compensation_series_id:'wf-comp',expense_series_id:'wf-exp',role:'Platform Ops',hire_period:1}]}},cost_pools:[{series_id:'pool-platform',owner_module:'cost_pool',name:'Platform Services Eligible Costs',components:[{kind:'operating_expense_category',series_id:'opex-tech',allocation_pct:.8},{kind:'workforce_role_expense',series_id:'wf-exp',allocation_pct:.4}]}],obs_exposures:[]}};\n"
        "function esc(x){return String(x==null?'':x);} function PLAB(k){return k==='full'?'month':'Mth';} function PPY(){return 12;}\n"
        "function numInput(){return '<input>'; } function growthSpecInline(){return '<growth>'; } function _qGrowthToPeriod(x){return x||0;} function _pf(x){return +(String(x).replace(/,/g,''))||0;} function _seriesId(p){return p+'-stub';} function _ensureLinkableSeriesIds(){} function _feeBasisTileHtml(){return '<tile>'; } function renderContent(){} function refresh(){} function appStatus(){} function alert(){}\n"
        + hjs + fjs +
        "\nconst p={name:'Affiliate Platform Services',_fee_product:true,managed_notional:{day1:0,trajectory:'flat'},fee_streams:[{name:'Platform services fee',basis:'transaction',driver:{source:'cost_pool',ref:'pool-platform',trajectory:'flat',params:{}},rate:{behavior:'cost_recovery',params:{recovery_pct:.9,markup:{value:.1,trajectory:'flat',period:'year',resolution:'step'}}},cost:{kind:'none',params:{}},timing:{start_period:1}}]};"
        "\ncfg.assumptions.obs_exposures=[p]; const out=fieldsFor('obs',p,'assumptions.obs_exposures.0'); console.log(JSON.stringify({ok:out.includes('Platform Services Eligible Costs')&&out.includes('Operating Expense: Technology')&&out.includes('Workforce expense: Platform Ops')&&out.includes('Recovery (% of eligible cost pool)')&&out.includes('Markup path')&&out.includes('upstream costs already posted')}));"
    )
    nr = subprocess.run(["node", "-e", node], text=True, capture_output=True)
    no = {}
    if nr.returncode == 0 and nr.stdout.strip():
        try: no = json.loads(nr.stdout.strip().splitlines()[-1])
        except Exception: pass
    ck("cost-recovery Fee Product renders end-to-end without browser-runtime error",
       nr.returncode == 0 and no.get("ok") is True, nr.stderr.strip())

    print(f"\n{P} passed, {F} failed")
    return 0 if F == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
