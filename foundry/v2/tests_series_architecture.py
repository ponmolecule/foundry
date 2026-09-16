"""Golden contract for Foundry Series + causal links across CAC/workforce/opex."""
from __future__ import annotations

import copy

from .series import normalize_series_spec, resolve_entered_series, resolve_series_spec, annual_value, normalize_amount_basis
from .workforce import workforce_role_count_series, workforce_role_compensation_series, workforce_comp_series
from .cac_feeder import cac_auc_rollforward, channel_new_customers


def _eq(a,b,tol=1e-6): return abs(float(a)-float(b)) <= tol


def main():
    P=F=0
    def ck(name, cond, detail=""):
        nonlocal P,F
        if cond: P+=1; print("  PASS ",name)
        else: F+=1; print("  FAIL ",name,detail)

    # Generic entered series semantics.
    flat={"source":"entered","trajectory":"flat","value":3}
    ck("Foundry Series flat repeats at native cadence", resolve_entered_series(flat,6,12)==[3]*6)
    exp={"source":"entered","trajectory":"explicit","cadence":"year","values":[2,4],"resolution":"step"}
    arr=resolve_entered_series(exp,24,12)
    ck("explicit annual series steps without spreadsheet-specific engine logic",
       arr[:12]==[2]*12 and arr[12:]==[4]*12)
    growth={"source":"entered","trajectory":"growth","base":2,
            "growth_spec":{"rate":.5,"period":"year","method":"step","anchor":"model_year"}}
    g=resolve_entered_series(growth,24,12)
    ck("generic growth series changes at model-year boundary", _eq(g[0],2) and _eq(g[12],3))

    # Derived is a first-class source but never an arbitrary formula surface.
    drv={"source":"derived","series_id":"cac-derived-1","owner_module":"customer_acquisition",
         "semantic_type":"new_customers","derived":{"kind":"cac.spend_cac.new_customers"}}
    nd=normalize_series_spec(drv)
    ck("Derived Series retains stable identity and module ownership",
       nd["source"]=="derived" and nd["series_id"]=="cac-derived-1" and nd["owner_module"]=="customer_acquisition")
    blocked=False
    try: resolve_series_spec(drv,{},12,12)
    except ValueError as e: blocked="owning module" in str(e) and "does not evaluate formulas" in str(e)
    ck("generic Series resolver refuses to evaluate Derived formulas", blocked)

    # Workforce Count is a genuine series again, not a static row multiplier only.
    role={"series_id":"wf-rm","role":"Relationship Managers","count":2,"hire_period":1,
          "count_spec":{"source":"entered","trajectory":"explicit","cadence":"year","values":[2,4,6]},
          "annual_comp":120000,"payroll_load_rate":0}
    counts=workforce_role_count_series(role,36,12)
    ck("workforce count explicit path resolves 2->4->6", counts[:12]==[2]*12 and counts[12:24]==[4]*12 and counts[24:]==[6]*12)
    comp=workforce_comp_series({"mode":"roles","roles":[role]},36,12)
    ck("workforce expense consumes count series", _eq(sum(comp[:12]),240000) and _eq(sum(comp[12:24]),480000))
    comp_role={**role,"compensation_series_id":"wf-comp-rm",
        "compensation_spec":{"source":"entered","series_id":"wf-comp-rm","owner_module":"operating_expense.workforce",
            "semantic_type":"compensation_per_fte","trajectory":"explicit","period":"year","cadence":"year",
            "values":[120000,132000,145200],"resolution":"step","extend":"hold"}}
    cps=workforce_role_compensation_series(comp_role,36,12)
    ck("Workforce Compensation uses the same explicit/cadence Series contract",
       cps[:12]==[120000]*12 and cps[12:24]==[132000]*12 and cps[24:]==[145200]*12)
    cpexp=workforce_comp_series({"mode":"roles","roles":[comp_role]},36,12)
    ck("payroll consumes Compensation Series without double annualization",
       _eq(sum(cpexp[:12]),240000) and _eq(sum(cpexp[12:24]),528000))

    # r107: compensation amount period is explicit for Flat / Growth / Explicit.
    # The schedule cadence answers "when may the level change?"; period answers
    # "what time unit does the entered amount represent?".  They are not aliases.
    monthly_explicit={
        "series_id":"wf-monthly-comp","role":"Monthly consultant","count":1,"hire_period":1,
        "annual_comp":358000,"compensation_period":"month","payroll_load_rate":0,
        "compensation_spec":{"source":"entered","series_id":"wf-monthly-comp-value",
            "owner_module":"operating_expense.workforce","semantic_type":"compensation_per_fte",
            "trajectory":"explicit","period":"month","cadence":"month",
            "values":[358000]*12,"resolution":"step","extend":"hold"}}
    monthly_levels=workforce_role_compensation_series(monthly_explicit,12,12)
    monthly_payroll=workforce_comp_series({"mode":"roles","roles":[monthly_explicit]},12,12)
    ck("Explicit $358k/FTE/month remains $358k monthly payroll instead of being treated as annual",
       _eq(monthly_levels[0],4_296_000) and all(_eq(x,358000) for x in monthly_payroll),
       f"annualized={monthly_levels[0]} payroll={monthly_payroll[:2]}")

    flat_year={"role":"Flat year","count":1,"hire_period":1,"annual_comp":120000,
               "compensation_period":"year","payroll_load_rate":0,
               "compensation_spec":{"source":"entered","trajectory":"flat","period":"year","value":120000}}
    flat_month={"role":"Flat month","count":1,"hire_period":1,"annual_comp":10000,
                "compensation_period":"month","payroll_load_rate":0,
                "compensation_spec":{"source":"entered","trajectory":"flat","period":"month","value":10000}}
    ck("Flat compensation period converts equivalent Year and Month amounts identically",
       workforce_comp_series({"roles":[flat_year]},12,12)==workforce_comp_series({"roles":[flat_month]},12,12))

    growth_year={**flat_year,"role":"Growth year","compensation_spec":{
        "source":"entered","trajectory":"growth","period":"year","base":120000,
        "growth_spec":{"rate":.10,"period":"year","method":"step","anchor":"model_year"}}}
    growth_month={**flat_month,"role":"Growth month","compensation_spec":{
        "source":"entered","trajectory":"growth","period":"month","base":10000,
        "growth_spec":{"rate":.10,"period":"year","method":"step","anchor":"model_year"}}}
    ck("Growth compensation amount period is independent of the growth-rate period",
       workforce_comp_series({"roles":[growth_year]},24,12)==workforce_comp_series({"roles":[growth_month]},24,12))
    bad_period=False
    try:
        workforce_comp_series({"roles":[{**flat_month,"compensation_period":"week",
            "compensation_spec":{"source":"entered","trajectory":"flat","period":"week","value":10000}}]},12,12)
    except ValueError as e:
        bad_period="month/quarter/year" in str(e)
    ck("unsupported Workforce compensation amount period fails closed", bad_period)

    # r108: amount basis is independent of Count, amount period, and trajectory.
    # The motivating case carries headcount for downstream consumers while the authored
    # $354k/month is already the entire Workforce compensation amount.
    total_explicit={
        "series_id":"wf-total-explicit","role":"Operations team","count":28.333,"hire_period":1,
        "annual_comp":354000,"compensation_period":"month","compensation_basis":"total","payroll_load_rate":0,
        "compensation_spec":{"source":"entered","series_id":"wf-total-explicit-value",
            "owner_module":"operating_expense.workforce","semantic_type":"compensation",
            "amount_basis":"total","trajectory":"explicit","period":"month","cadence":"month",
            "values":[354000]*12,"resolution":"step","extend":"hold"}}
    total_explicit_count=workforce_role_count_series(total_explicit,12,12)
    total_explicit_pay=workforce_comp_series({"roles":[total_explicit]},12,12)
    ck("Total Explicit compensation does not multiply the authored amount by Workforce Count",
       all(_eq(x,354000) for x in total_explicit_pay), total_explicit_pay[:2])
    ck("Total compensation leaves Workforce Count independently available for other consumers",
       all(_eq(x,28.333) for x in total_explicit_count), total_explicit_count[:2])

    per_fte_explicit=copy.deepcopy(total_explicit)
    per_fte_explicit["series_id"]="wf-per-fte-explicit"
    per_fte_explicit["compensation_basis"]="per_unit"
    per_fte_explicit["compensation_spec"]["series_id"]="wf-per-fte-explicit-value"
    per_fte_explicit["compensation_spec"]["amount_basis"]="per_unit"
    per_fte_pay=workforce_comp_series({"roles":[per_fte_explicit]},12,12)
    ck("Per FTE Explicit compensation preserves Count × amount economics",
       all(_eq(x,354000*28.333) for x in per_fte_pay), per_fte_pay[:2])

    total_flat={"role":"Total flat","count":7,"hire_period":1,"end_period":2,
                "annual_comp":10000,"compensation_period":"month","compensation_basis":"total",
                "payroll_load_rate":0,"compensation_spec":{"source":"entered","trajectory":"flat",
                    "amount_basis":"total","period":"month","value":10000}}
    ck("Total Flat compensation is count-independent but still respects the active window",
       workforce_comp_series({"roles":[total_flat]},4,12)==[10000,10000,0,0])

    total_growth={"role":"Total growth","count":2,"hire_period":1,"annual_comp":10000,
                  "compensation_period":"month","compensation_basis":"total","payroll_load_rate":0,
                  "count_spec":{"source":"entered","trajectory":"explicit","cadence":"year","values":[2,4]},
                  "compensation_spec":{"source":"entered","trajectory":"growth","amount_basis":"total",
                      "period":"month","base":10000,
                      "growth_spec":{"rate":.10,"period":"year","method":"step","anchor":"model_year"}}}
    total_growth_pay=workforce_comp_series({"roles":[total_growth]},24,12)
    ck("Total Growth compensation changes with its own trajectory rather than Count trajectory",
       all(_eq(x,10000) for x in total_growth_pay[:12])
       and all(_eq(x,11000) for x in total_growth_pay[12:]))

    legacy_basis={"role":"Legacy basis","count":2,"hire_period":1,"annual_comp":120000,
                  "compensation_period":"year","payroll_load_rate":0}
    ck("pre-r108 Workforce rows migrate semantically to Per FTE without changing economics",
       _eq(sum(workforce_comp_series({"roles":[legacy_basis]},12,12)),240000))
    ck("generic amount-basis aliases normalize without embedding Workforce terminology",
       normalize_amount_basis("per_fte")=="per_unit" and normalize_amount_basis("aggregate")=="total")
    bad_basis=False
    try:
        workforce_comp_series({"roles":[{**legacy_basis,"compensation_basis":"mystery"}]},12,12)
    except ValueError as e:
        bad_basis="total/per_unit" in str(e)
    ck("unsupported Workforce compensation amount basis fails closed", bad_basis)

    # Stable-ID operating-expense link: CAC consumes the expense trajectory instead of duplicating it.
    assumptions={"n_periods":24,"nie_detail":{"categories":[{
        "series_id":"opex-bd","name":"Business Development","trajectory":"growth","per_period":10000,
        "growth_spec":{"rate":1.0,"period":"year","method":"step","anchor":"model_year"}
    }],"workforce":{"mode":"roles","roles":[role]}}}
    linked_spend={"source":"link","link":{"kind":"operating_expense_category","series_id":"opex-bd","aggregation":"sum"}}
    ch={"name":"Direct / BD","method":"spend_cac","params":{"cac":1200},"avg_auc_per_customer":100000,
        "driver_specs":{"spend":linked_spend}}
    rf=cac_auc_rollforward({"channels":[ch],"attrition_rate":0},24,12,assumptions=assumptions)
    ck("CAC linked spend consumes Year-1 operating-expense flow", _eq(rf["annual"][0]["total_spend"],120000))
    ck("linked expense trajectory remains owned by Opex", _eq(rf["annual"][1]["total_spend"],240000))
    ck("Spend/CAC equation uses linked spend without duplicating a BD budget", _eq(rf["annual"][0]["new_cust"],100))

    # r103: an Opex category is the complete linkable Series, not merely its entered base.
    # Workforce Count × amount/FTE is deterministic upstream economics and therefore must
    # travel with the category when CAC consumes it as Acquisition Spend.
    ga_assumptions={"n_periods":24,"nie_detail":{
        "categories":[{"series_id":"opex-ga","name":"G&A",
            "flow_spec":{"trajectory":"flat","value":0,"period":"month"},
            "linked_components":[{"driver":"workforce_count","series_id":"wf-total-ga",
                "amount_spec":{"trajectory":"flat","value":10000,"period":"month"}}]}],
        "workforce":{"mode":"roles","total_count_series_id":"wf-total-ga","roles":[
            {"series_id":"wf-ga","role":"G&A population","count":3,"annual_comp":100000,"hire_period":1}
        ]}}}
    ga_spend={"source":"link","link":{"kind":"operating_expense_category",
        "series_id":"opex-ga","aggregation":"sum"}}
    ga_ch={"name":"G&A-funded acquisition","method":"spend_cac","params":{"cac":1000},
           "avg_auc_per_customer":1,"driver_specs":{"spend":ga_spend}}
    ga_rf=cac_auc_rollforward({"channels":[ga_ch],"attrition_rate":0},24,12,assumptions=ga_assumptions)
    ck("CAC linked spend includes Workforce Count × amount/FTE Opex component",
       _eq(ga_rf["annual"][0]["total_spend"],360000)
       and _eq(ga_rf["annual"][1]["total_spend"],360000)
       and _eq(ga_rf["annual"][0]["new_cust"],360))

    unsafe=copy.deepcopy(ga_assumptions)
    unsafe["nie_detail"]["categories"][0]["linked_components"].append(
        {"driver":"fee_income","rate_spec":{"source":"entered","trajectory":"flat","value":.01}})
    unsafe_failed=False
    try: cac_auc_rollforward({"channels":[ga_ch],"attrition_rate":0},12,12,assumptions=unsafe)
    except ValueError as e: unsafe_failed="runtime metrics" in str(e)
    ck("CAC fails closed instead of silently omitting runtime-dependent Opex components", unsafe_failed)

    # Finer source cadence is explicit economic metadata: operands resolve monthly before the equation runs.
    monthly_ch={"name":"Monthly source","method":"spend_cac","params":{},"avg_auc_per_customer":1,
        "driver_specs":{
          "spend":{"source":"entered","trajectory":"explicit","cadence":"month","values":[10000]*12,"aggregation":"sum"},
          "cac":{"source":"entered","trajectory":"explicit","cadence":"month","values":[1200]*12,"aggregation":"average"},
          "avg_auc_per_customer":{"source":"entered","trajectory":"flat","value":1}}}
    mr=cac_auc_rollforward({"channels":[monthly_ch],"attrition_rate":0},12,12,assumptions={})
    ck("CAC explicit monthly Spend and CAC are evaluated month-by-month then aggregate annually",
       _eq(mr["annual"][0]["total_spend"],120000) and _eq(mr["annual"][0]["new_cust"],100))
    quarterly_ch={"name":"Quarterly source","method":"spend_cac","params":{},"avg_auc_per_customer":1,
        "driver_specs":{
          "spend":{"source":"entered","trajectory":"explicit","cadence":"quarter","values":[30000]*4,"aggregation":"sum","resolution":"smooth"},
          "cac":{"source":"entered","trajectory":"explicit","cadence":"quarter","values":[1200]*4,"aggregation":"average","resolution":"step"},
          "avg_auc_per_customer":{"source":"entered","trajectory":"flat","value":1}}}
    qr=cac_auc_rollforward({"channels":[quarterly_ch],"attrition_rate":0},12,12,assumptions={})
    ck("CAC quarterly Explicit flows resolve across constituent months without triple-counting",
       _eq(qr["annual"][0]["total_spend"],120000) and _eq(qr["annual"][0]["new_cust"],100))

    # Rename display label; stable series_id keeps link intact.
    renamed=copy.deepcopy(assumptions); renamed["nie_detail"]["categories"][0]["name"]="Partnership Growth"
    rr=cac_auc_rollforward({"channels":[ch],"attrition_rate":0},12,12,assumptions=renamed)
    ck("stable series ID survives source display-name change", _eq(rr["annual"][0]["total_spend"],120000))

    # Downstream Fee Products consume CAC AUC by stable feed ID, not the feed display/key name.
    import json
    from pathlib import Path
    from .run_q import run_v2
    fcfg=json.loads(Path("foundry/fixtures/parity/configs/pf_a_base.json").read_text())
    fcfg["assumptions"]["periods_per_year"]=4; fcfg["assumptions"]["n_periods"]=12
    fcfg["assumptions"]["cac_feeds"]={"retail":{"series_id":"cac-feed-retail","owner_module":"customer_acquisition",
        "attrition_rate":0,"channels":[{"name":"D","method":"spend_cac","params":{"spend":100000,"cac":1000},"avg_auc_per_customer":50000}]}}
    fcfg["assumptions"]["obs_exposures"]=[{"name":"Custody","call_report_line":"obs","_fee_product":True,
        "managed_notional_source":"stale-display-name","managed_notional_source_id":"cac-feed-retail",
        "fee_streams":[{"basis":"balance","driver":{"source":"managed_notional"},"rate":{"params":{"rate":0.001}},"timing":{"start_period":1}}]}]
    fbase=run_v2(fcfg)["financials"]["is"]["fees"]
    fren=copy.deepcopy(fcfg); fren["assumptions"]["cac_feeds"]={"renamed-feed":fren["assumptions"]["cac_feeds"]["retail"]}
    frename=run_v2(fren)["financials"]["is"]["fees"]
    ck("Fee-to-CAC link survives feed rename by stable series ID", fbase==frename and any(x>0 for x in fbase))

    # Workforce count link: annual productivity uses average active FTE population.
    fte_link={"source":"link","link":{"kind":"workforce_role_count","series_id":"wf-rm","aggregation":"average"}}
    fch={"name":"Relationship-led","method":"fte_productivity","params":{"per_fte":25,"comp_per_fte":120000},
         "avg_auc_per_customer":200000,"driver_specs":{"ftes":fte_link}}
    fr=cac_auc_rollforward({"channels":[fch],"attrition_rate":0},24,12,assumptions=assumptions)
    ck("CAC FTE productivity can consume Workforce Count series", _eq(fr["annual"][0]["new_cust"],50) and _eq(fr["annual"][1]["new_cust"],100))
    dch=copy.deepcopy(ch);dch["derived_series_ids"]={"new_customers":"cac-nc-1","new_auc":"cac-auc-add-1"}
    dr=cac_auc_rollforward({"series_id":"cac-feed-auc-1","channels":[dch],"attrition_rate":0},12,12,assumptions=assumptions)
    ck("CAC publishes module-owned Derived Series outputs with stable IDs",
       dr["derived_series"]["cac-nc-1"]["source"]=="derived"
       and dr["derived_series"]["cac-feed-auc-1"]["derived"]["kind"]=="cac.customer_auc_rollforward")

    # Circular-risk guard: metric-triggered workforce cannot be an upstream CAC operand.
    bad=copy.deepcopy(assumptions)
    bad["nie_detail"]["workforce"]["roles"][0]["activation"]={"metric":"managed_notional_end","source":"Custody","operator":">=","value":1e9,"timing":"same_period"}
    failed=False
    try: cac_auc_rollforward({"channels":[fch],"attrition_rate":0},12,12,assumptions=bad)
    except ValueError as e: failed="circular" in str(e).lower() or "metric-triggered" in str(e).lower()
    ck("CAC rejects metric-triggered workforce link that could create circularity", failed)

    # Legacy static count and CAC scalar/growth semantics remain unchanged.
    legacy_role={"role":"Legacy","count":3,"annual_comp":100000,"hire_period":1}
    ck("legacy workforce scalar count is frozen", workforce_role_count_series(legacy_role,4,4)==[3]*4)
    legacy_ch={"name":"Whatever","method":"pool_conversion","params":{"pool":1000,"pool_growth":.1,"conversion_rate":.02},"avg_auc_per_customer":1}
    ck("legacy CAC channel economics unchanged", _eq(channel_new_customers(legacy_ch,1),20) and _eq(channel_new_customers(legacy_ch,2),22))

    # Public run seam preserves Count in natural headcount units while compensation is $000s.
    pcfg=json.loads(Path("foundry/fixtures/parity/configs/pf_a_base.json").read_text())
    pcfg["assumptions"]["periods_per_year"]=12
    pcfg["assumptions"]["n_periods"]=24
    pcfg["assumptions"]["nie_detail"]={"categories":[],"other_gross_up_rate":0,
        "workforce":{"mode":"roles","total_count_series_id":"wf-total-public","default_payroll_load_rate":0,"roles":[role]}}
    pout=run_v2(pcfg).get("workforce") or {}
    ck("public Workforce output preserves Count in headcount units",
       pout.get("count_units")=="FTE/headcount" and pout.get("counts",[[]])[0][:12]==[2.0]*12
       and pout.get("counts",[[]])[0][12:24]==[4.0]*12)
    ck("public Workforce output exposes aggregate active Count under its stable Series ID",
       pout.get("total_count_series_id")=="wf-total-public"
       and pout.get("total_counts",[])[:12]==[2.0]*12
       and pout.get("total_counts",[])[12:24]==[4.0]*12)
    ck("public Workforce compensation remains monetary $000s",
       pout.get("comp_units")=="$000s" and _eq(sum(pout.get("comp",[])[:12]),240.0))

    # Full config validation fails closed on missing/ambiguous links and duplicate stable IDs.
    from .validate_q import validate_config_v2, ConfigErrorV2
    cfg=json.load(open("foundry/fixtures/core_bank_test_base.json"))
    cfg["assumptions"]["periods_per_year"]=12;cfg["assumptions"]["n_periods"]=12
    cfg["assumptions"]["nie_detail"]={"categories":[{"series_id":"dup","name":"BD","per_period":10000}],
        "workforce":{"mode":"roles","roles":[{"series_id":"dup","role":"RM","count":1,"annual_comp":100000,"hire_period":1}]}}
    cfg["assumptions"]["cac_feeds"]={"x":{"channels":[{"name":"x","method":"spend_cac","params":{"cac":1000},"avg_auc_per_customer":1,
        "driver_specs":{"spend":{"source":"link","link":{"kind":"operating_expense_category","series_id":"missing","aggregation":"sum"}}}}],"attrition_rate":0}}
    bad=False
    try: validate_config_v2(cfg)
    except ConfigErrorV2 as e: bad=("missing" in str(e) and "series_id" in str(e))
    ck("config validation fails closed on broken links and duplicate stable IDs", bad)

    basis_cfg=json.load(open("foundry/fixtures/core_bank_test_base.json"))
    basis_cfg["assumptions"]["periods_per_year"]=12; basis_cfg["assumptions"]["n_periods"]=12
    basis_cfg["assumptions"]["nie_detail"]={"categories":[],"workforce":{"mode":"roles","roles":[{
        "role":"Invalid basis","count":1,"annual_comp":120000,"compensation_basis":"mystery","hire_period":1
    }]}}
    bad_basis_cfg=False
    try: validate_config_v2(basis_cfg)
    except ConfigErrorV2 as e: bad_basis_cfg="compensation_basis" in str(e) and "total/per_unit" in str(e)
    ck("config validation rejects unsupported Workforce compensation basis before engine execution", bad_basis_cfg)

    print(f"\n{P} passed, {F} failed")
    return 0 if F==0 else 1

if __name__=="__main__": raise SystemExit(main())
