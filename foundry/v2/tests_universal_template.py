"""Release-gate coverage contract for Foundry's Universal Input Workbook fixture.

The Universal fixture is intentionally pathological rather than representative: each current
canonical authoring primitive must have at least one concrete specimen, must execute, and must
survive a zero-edit FIW round trip without changing configuration or economics.
"""
from __future__ import annotations

import io
import json
from copy import deepcopy

from openpyxl import load_workbook

from . import run_q
from .fiw import build_fiw, cfg_hash, diff_import
from .income_modules import (
    _FEE_BASES, _FEE_SOURCES, _FEE_TRAJECTORIES, _FEE_RATE_BEHAVIORS, _FEE_COST_KINDS,
)
from .opex_extensions import (
    SAFE_REVENUE_DRIVERS, FEE_STREAM_QUANTITY_DRIVER, CAC_AUC_DRIVER,
    WORKFORCE_COUNT_DRIVER, SERVICE_CAPACITY_DRIVER, FORMULA_DRIVER,
    COST_POOL_CHARGE_DRIVER, PIECEWISE_LINKED_DRIVER,
)
from .validate_q import validate_errors_v2

FIXTURE = "foundry/fixtures/universal_template_bank.json"


def _all_fee_streams(a):
    owners = list(a.get("lending_products") or []) + list(a.get("deposit_products") or []) + list(a.get("obs_exposures") or [])
    return [(p, s) for p in owners for s in (p.get("fee_streams") or [])]


def _trajectories_in(obj):
    out = set()
    def walk(x):
        if isinstance(x, dict):
            if x.get("trajectory") is not None:
                out.add(str(x.get("trajectory")))
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(obj)
    return out


def main():
    cfg = json.load(open(FIXTURE, encoding="utf-8"))
    a = cfg["assumptions"]
    P = F = 0

    def ck(name, cond, detail=""):
        nonlocal P, F
        if cond:
            P += 1; print("PASS", name)
        else:
            F += 1; print("FAIL", name, detail)

    # Engine/config baseline.
    errs = validate_errors_v2(deepcopy(cfg))
    ck("universal fixture validates cleanly", not errs, errs[:3])                                    # 1
    ck("universal fixture is a 36-month computational model",
       int(a.get("periods_per_year") or 0) == 12 and int(a.get("n_periods") or 0) == 36)           # 2
    out = run_q.run_v2(deepcopy(cfg))
    ck("universal fixture actually runs modern modules",
       bool(out.get("financials")) and bool(out.get("customer_acquisition")))                         # 3

    # Traditional/core-bank breadth remains present.
    loans = a.get("lending_products") or []; deps = a.get("deposit_products") or []
    ck("core lending covers fixed and floating rates", {p.get("rate_type") for p in loans} >= {"fixed","float"}) # 4
    ck("core deposits cover fixed and floating rates", {p.get("rate_type") for p in deps} >= {"fixed","float"}) # 5
    ck("lending covers amortized cost and fair value", {p.get("measurement","amortized") for p in loans} >= {"amortized","fair_value"}) # 6
    ck("mortgage-banking branch is represented", any(p.get("mortgage_banking") for p in loans))      # 7
    ck("AFS and HTM securities are represented", bool(a.get("securities_afs")) and bool(a.get("securities_htm"))) # 8
    ck("scheduled borrowings and staged raises are represented", bool(a.get("scheduled_borrowings")) and bool(a.get("capital_raises"))) # 9
    ck("pre-opening expense branch is represented", bool((cfg.get("pre_opening") or {}).get("expenses"))) # 10
    rc = a.get("rate_curves") or {}
    ck("structured SOFR EFFR Prime and FOMC rate framework is represented",
       all(rc.get(k) for k in ("sofr","effr","prime","fomc","current_policy")))                    # 11

    # Customer Acquisition vocabulary.
    feeds = a.get("cac_feeds") or {}; channels=[ch for feed in feeds.values() for ch in (feed.get("channels") or [])]
    ck("CAC covers all four acquisition methods", {ch.get("method") for ch in channels} >= {"pool_conversion","spend_cac","fte_productivity","explicit"}) # 12
    specs=[sp for feed in feeds.values() for ch in (feed.get("channels") or []) for sp in (ch.get("driver_specs") or {}).values()]
    specs += [sp for feed in feeds.values() for sp in (feed.get("driver_specs") or {}).values()]
    trs={str((sp or {}).get("trajectory",(sp or {}).get("mode","flat"))) for sp in specs}
    ck("CAC covers Flat Growth Explicit trajectories", {"flat","growth","explicit"} <= trs)          # 13
    ck("CAC covers entered and linked operands", {str((sp or {}).get("source","entered")) for sp in specs} >= {"entered","link"}) # 14
    periods={str((sp or {}).get("period",(sp or {}).get("cadence",""))) for sp in specs}
    ck("CAC source operands cover Month Quarter Year", {"month","quarter","year"} <= periods)        # 15
    ck("CAC publishes stable AUC and customer-count Series", all(feed.get("series_id") and feed.get("customer_count_series_id") for feed in feeds.values())) # 16

    # Fee stream grammar — exact enum coverage, not hand-selected subsets.
    streams = _all_fee_streams(a); ss=[s for _,s in streams]
    ck("Universal covers every canonical Fee Product basis", {s.get("basis") for s in ss} == set(_FEE_BASES)) # 17
    ck("Universal covers every canonical Fee Product driver source", {(s.get("driver") or {}).get("source") for s in ss} == set(_FEE_SOURCES)) # 18
    ck("Universal covers every canonical Fee Product driver trajectory", {(s.get("driver") or {}).get("trajectory") for s in ss} == set(_FEE_TRAJECTORIES)) # 19
    ck("Universal covers every canonical Fee Product rate behavior", {(s.get("rate") or {}).get("behavior") for s in ss} == set(_FEE_RATE_BEHAVIORS)) # 20
    ck("Universal covers every canonical Fee Product direct-cost kind", {(s.get("cost") or {}).get("kind") for s in ss} == set(_FEE_COST_KINDS)) # 21
    measures={(s.get("driver") or {}).get("measure") or (((s.get("driver") or {}).get("params") or {}).get("customer_count_measure"))
              for s in ss if (s.get("driver") or {}).get("source")=="customer_acquisition_count"}
    ck("Fee Products cover all three CAC customer-count measures", measures == {"period_end","period_average","annual_count"}) # 22
    acct_specs=[(((s.get("rate") or {}).get("params") or {}).get("unit_fee") or {}) for s in ss if s.get("basis")=="account"]
    ck("Account pricing covers Flat Growth Explicit", {x.get("trajectory","flat") for x in acct_specs} >= {"flat","growth","explicit_schedule"}) # 23
    ck("Account pricing covers Month Quarter Year amount periods", {x.get("period") for x in acct_specs} >= {"month","quarter","year"}) # 24
    coeffs={((((s.get("driver") or {}).get("params") or {}).get("coefficient") or {}).get("kind")) for s in ss}
    coeffs.discard(None)
    ck("Derived fee coefficients cover multiple share and amount-per-source-unit", {"multiple","pct","amount_per_source_unit"} <= coeffs) # 25
    rate_tr=set(); cost_tr=set()
    for s in ss:
        rate_tr |= _trajectories_in(s.get("rate") or {})
        cost_tr |= _trajectories_in(s.get("cost") or {})
    ck("Modern fee revenue trajectories cover Growth and Explicit", {"growth","explicit_schedule"} <= rate_tr) # 26
    ck("Modern direct-cost trajectories cover Flat Growth Explicit", {"flat","growth","explicit_schedule"} <= cost_tr) # 27

    # Workforce grammar.
    wf=(a.get("nie_detail") or {}).get("workforce") or {}; roles=wf.get("roles") or []
    count_tr={((r.get("count_spec") or {}).get("trajectory") or "flat") for r in roles}
    comp_tr={((r.get("compensation_spec") or {}).get("trajectory") or "flat") for r in roles}
    ck("Workforce count covers Flat Growth Explicit", {"flat","growth","explicit"} <= count_tr)       # 28
    ck("Workforce compensation covers Flat Growth Explicit", {"flat","growth","explicit"} <= comp_tr) # 29
    ck("Workforce covers Per FTE and Total compensation bases",
       {((r.get("compensation_spec") or {}).get("amount_basis") or r.get("compensation_basis") or "per_unit") for r in roles} >= {"per_unit","total"}) # 30
    ck("Workforce compensation covers Month Quarter Year amount periods",
       {((r.get("compensation_spec") or {}).get("period") or r.get("compensation_period") or "year") for r in roles} >= {"month","quarter","year"}) # 31
    ck("Workforce covers metric activation and additive compensation",
       any(r.get("activation") for r in roles) and bool(wf.get("additive_components")))                 # 32

    # Opex grammar.
    cats=(a.get("nie_detail") or {}).get("categories") or []
    fs=[c.get("flow_spec") or {} for c in cats if c.get("flow_spec")]
    ck("Opex entered amounts cover Flat Growth Explicit", {x.get("trajectory") for x in fs} >= {"flat","growth","explicit"}) # 33
    ck("Opex entered amounts cover Month Quarter Year", {x.get("period") for x in fs} >= {"month","quarter","year"}) # 34
    linked={lc.get("driver") for c in cats for lc in (c.get("linked_components") or [])}
    required_linked=set(SAFE_REVENUE_DRIVERS)|{FEE_STREAM_QUANTITY_DRIVER,CAC_AUC_DRIVER,WORKFORCE_COUNT_DRIVER,SERVICE_CAPACITY_DRIVER,FORMULA_DRIVER,COST_POOL_CHARGE_DRIVER,PIECEWISE_LINKED_DRIVER}
    ck("Opex covers every current linked-component driver", required_linked <= linked, sorted(required_linked-linked)) # 35
    service=[lc for c in cats for lc in (c.get("linked_components") or []) if lc.get("driver")==SERVICE_CAPACITY_DRIVER]
    ck("Opex service-capacity specimen keeps service FTE outside Workforce and owns an explicit hours period",
       bool(service) and (service[0].get("capacity_spec") or {}).get("period") in {"month","quarter","year"}
       and (service[0].get("quantity_spec") or {}).get("source")=="entered")
    formula=[lc for c in cats for lc in (c.get("linked_components") or []) if lc.get("driver")==FORMULA_DRIVER]
    ck("Opex Formula / driver specimen combines a stable linked Series with typed periodic and unit-cost factors",
       bool(formula) and any(f.get("kind")=="linked" and f.get("source")==FEE_STREAM_QUANTITY_DRIVER for f in formula[0].get("factors") or [])
       and any(f.get("kind")=="entered" and f.get("periodized") for f in formula[0].get("factors") or [])
       and any(f.get("kind")=="entered" and not f.get("periodized") for f in formula[0].get("factors") or []))
    rec={((c.get("recognition") or {}).get("mode") or "trajectory") for c in cats}
    setl={((c.get("settlement") or {}).get("mode") or "recognition") for c in cats}
    ck("Opex recognition covers trajectory monthly quarterly semiannual annual", {"trajectory","monthly","quarterly","semiannual","annual"} <= rec) # 36
    ck("Opex settlement covers recognition monthly quarterly semiannual annual", {"recognition","monthly","quarterly","semiannual","annual"} <= setl) # 37
    piecewise=[lc for c in cats for lc in (c.get("linked_components") or []) if lc.get("driver")==PIECEWISE_LINKED_DRIVER]
    ck("Tiered Opex covers spread recognition with separate cash-event timing",
       any((lc.get("recognition") or {}).get("mode")=="spread" and (lc.get("recognition") or {}).get("first_period")
           and (lc.get("timing") or {}).get("first_period") for lc in piecewise))

    # Cost pools + fixed assets.
    pools=a.get("cost_pools") or []
    pk={x.get("kind") or x.get("type") for p in pools for x in (p.get("components") or [])}
    ck("Cost pools cover all four eligible-cost component kinds",
       {"operating_expense_category","workforce_role_expense","assumption_cost_base","balance_derived_cost"} <= pk) # 38
    pool_refs={p.get("series_id") for p in pools}
    fee_pool=any((s.get("driver") or {}).get("source")=="cost_pool" and (s.get("driver") or {}).get("ref") in pool_refs for s in ss)
    opex_pool=any(lc.get("driver")==COST_POOL_CHARGE_DRIVER and lc.get("ref") in pool_refs for c in cats for lc in (c.get("linked_components") or []))
    ck("Cost pools are consumed downstream by Fee Product and Opex", fee_pool and opex_pool)             # 39
    fa=a.get("fixed_assets") or {}; assets=fa.get("assets") or []
    ck("Fixed assets cover opening accumulated depreciation and future CAPEX",
       fa.get("mode")=="schedule" and any(x.get("opening_accumulated_depreciation") for x in assets) and any((x.get("in_service_period") or 0)>0 for x in assets)) # 40

    # Fixed-asset methodologies are mutually exclusive in one live model. Exercise Formula / level
    # as a second executable Universal variant rather than pretending both can be active at once.
    flcfg=deepcopy(cfg); fla=flcfg["assumptions"]; flroles=(((fla.get("nie_detail") or {}).get("workforce") or {}).get("roles") or [])
    level_role=next((r for r in flroles if not r.get("activation") and r.get("series_id")), None); level_sid=(level_role or {}).get("series_id")
    fla["fixed_assets"]={"mode":"formula_level","formula_level":{
        "level_basis":"gross","opening_level":0.0,"opening_accumulated_depreciation":0.0,
        "base_spec":{"source":"entered","trajectory":"flat","value":250000.0},
        "components":[{"component_id":"universal-fixed-assets-workforce","name":"Capacity-linked equipment",
                       "driver_spec":{"source":"link","link":{"kind":"workforce_role_count","series_id":level_sid,"aggregation":"end"}},
                       "multiplier_spec":{"source":"entered","trajectory":"growth","base":4000.0,
                                          "growth_spec":{"rate":0.02,"period":"year","method":"step","anchor":"model_year"}}}],
        "depreciation":{"kind":"rate_of_level","rate_spec":{"source":"entered","trajectory":"flat","value":0.12,"period":"year"}}}}
    flerrs=validate_errors_v2(deepcopy(flcfg)); flout=run_q.run_v2(deepcopy(flcfg)) if not flerrs else {}
    ck("Universal alternate variant executes Formula / level fixed assets",
       not flerrs and (flout.get("fixed_assets") or {}).get("mode")=="formula_level"
       and (((flout.get("fixed_assets") or {}).get("formula_level") or {}).get("level_basis"))=="gross"
       and bool(((flout.get("fixed_assets") or {}).get("formula_level") or {}).get("components")), flerrs[:3]) # 41
    fldata,_=build_fiw(deepcopy(flcfg), include_capability_map=True); flwb=load_workbook(io.BytesIO(fldata), data_only=True)
    flcmap="\n".join(str(c.value or "") for row in flwb["CAPABILITY_MAP"].iter_rows() for c in row)
    ck("Universal alternate Formula / level FIW exposes its editable causal surface",
       "ASSM_FIXED_ASSETS_LEVEL" in flwb.sheetnames and "Formula / level methodology" in flcmap
       and "Linked Series × multiplier asset level" in flcmap) # 42

    # Managed securities grammar (r114): generic target-driven stock/flow books, no client-specific nouns.
    mps=a.get("managed_securities_portfolios") or []; ms=[sl for p in mps for sl in (p.get("sleeves") or [])]
    ck("Managed securities portfolio is represented", bool(mps) and bool(ms))                         # 41
    ck("Managed securities covers AFS and HTM sleeves", {str(x.get("classification") or "").upper() for x in ms} == {"AFS","HTM"}) # 42
    ck("Managed securities covers entered and Curve Library yield sources", {x.get("yield_source","entered") for x in ms} >= {"entered","curve_library"}) # 43
    ck("Managed securities runoff owns explicit Month Quarter Year natural periods",
       {str((x.get("maturity_rate_spec") or {}).get("period")) for x in ms} >= {"month","quarter","year"}) # 44
    ck("Managed securities target timing and first-period initialization are explicit",
       all((p.get("target_source") or {}).get("timing") in {"current_period","prior_period"}
           and (p.get("target_source") or {}).get("prior_initialization") in {"zero","opening_source"}
           for p in mps)) # 45
    mout=out.get("managed_securities") or []
    ck("Managed securities publishes target runoff balancing flow ending yield and interest",
       bool(mout) and all(all(k in sl for k in ("starting","maturing","net_purchases","ending","yield","interest_income"))
                          for pp in mout for sl in (pp.get("sleeves") or [])))                         # 46

    # FIW visible/hidden contract + no-op round trip.
    data, gh = build_fiw(deepcopy(cfg), include_capability_map=True)
    wb=load_workbook(io.BytesIO(data), data_only=True)
    ck("Universal FIW visibly exposes CAPABILITY_MAP and very-hides STATE",
       "CAPABILITY_MAP" in wb.sheetnames and "STATE" in wb.sheetnames and wb["STATE"].sheet_state=="veryHidden") # 41
    readme="\n".join(str(c.value or "") for row in wb["README"].iter_rows() for c in row)
    ck("README explains the embedded STATE round-trip contract",
       "very-hidden STATE" in readme and "editable overlays" in readme and "CAPABILITY_MAP" in readme) # 42
    settings="\n".join(str(c.value or "") for row in wb["SETTINGS"].iter_rows() for c in row)
    ck("SETTINGS reviews modern CAC pools fee streams Opex and rate curves",
       all(x in settings for x in ("Projection engine / calendar","Customer acquisition / published Series","Cost pools (non-posting eligible-cost bases)","Fee stream detail","Operating-expense linked mechanics","Structured rate curves"))) # 43
    cmap=list(wb["CAPABILITY_MAP"].iter_rows(min_row=2, values_only=True))
    ck("Every CAPABILITY_MAP claim points to a concrete specimen", len(cmap)>=80 and all(r[1] and r[2] and r[3] for r in cmap)) # 44
    merged, rep = diff_import(data, deepcopy(cfg))
    edits=(rep or {}).get("edits") if isinstance(rep,dict) else None
    ck("Zero-edit Universal FIW round trip reports no human edits", edits == [] or edits is None, rep) # 45
    ck("Zero-edit Universal FIW round trip is semantically config-identical",
       json.dumps(merged,sort_keys=True,default=str)==json.dumps(cfg,sort_keys=True,default=str))          # 46
    out2=run_q.run_v2(deepcopy(merged))
    ck("Zero-edit Universal FIW round trip preserves financial outputs and generation hash",
       json.dumps(out2.get("financials"),sort_keys=True,default=str)==json.dumps(out.get("financials"),sort_keys=True,default=str)
       and gh==cfg_hash(cfg))                                                                              # 47

    print(f"\n{P} passed, {F} failed")
    if F:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
