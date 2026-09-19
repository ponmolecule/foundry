"""Regression gate for generalized Other liabilities Formula / level."""
from __future__ import annotations
import copy, json
from pathlib import Path

from foundry.v2.engine_q_a import run_pf_a
from foundry.v2.engine_q_b import run_pf_b
from foundry.v2.parity import run_parity
from foundry.v2.present import derived_lines
from foundry.v2.run_q import run_v2
from foundry.v2.validate_q import validate_errors_v2
from foundry.v2.fiw import build_fiw, diff_import
from foundry.v2.audit_workbook import calculation_audit_workbook
from foundry.v2.fixed_assets import (
    FIXED_ASSET_FORMULA_BASE_SERIES_ID, FIXED_ASSET_ACCUM_DEP_SERIES_ID,
    fixed_asset_series_by_id,
)


def _cfg():
    return json.loads((Path(__file__).parents[1]/"fixtures"/"patrick_default_v31.json").read_text())


def _term(tid, kind, sid, mult):
    return {"term_id":tid,
            "driver_spec":{"source":"link","link":{"kind":kind,"series_id":sid,"aggregation":"end"}},
            "multiplier_spec":{"source":"entered","trajectory":"flat","value":mult}}


def _activate(a, ppy=12, n=12):
    a["periods_per_year"]=ppy; a["n_periods"]=n
    a["other_liabilities"]=155000.0
    a["premises_equipment"]=0; a["premises_depreciation_annual"]=0
    a["nie_detail"]={
        "categories":[], "other_gross_up_rate":0, "fdic_bp_ann":0, "occ_bp_ann":0,
        "workforce":{"mode":"roles","total_count_series_id":"wf-total-ol","default_payroll_load_rate":0,
                     "roles":[{"series_id":"wf-ops-ol","role":"Operations","count":10,
                               "annual_comp":0,"hire_period":1}]}}
    # Source-model shape: gross fixed assets = entered ROU level + Total FTE * $800.
    a["fixed_assets"]={"mode":"formula_level","formula_level":{
        "level_basis":"gross","opening_level":128000,"base_name":"Fixed Asset ROU",
        "base_spec":{"source":"entered","trajectory":"flat","value":120000},
        "components":[{"component_id":"fa-fte-fixtures","name":"Workforce-linked fixed assets",
                       "driver_spec":{"source":"link","link":{"kind":"workforce_role_count","series_id":"wf-total-ol","aggregation":"end"}},
                       "multiplier_spec":{"source":"entered","trajectory":"flat","value":800}}],
        "depreciation":{"kind":"entered","amount_spec":{"source":"entered","trajectory":"flat",
                                                              "value":12000,"period":"year"}}}}
    # Source-model lease logic: ROU + negative cumulative depreciation. Foundry carries
    # accumulated depreciation positive, so the algebraic equivalent is ROU - accum dep.
    a["other_liabilities_model"]={
        "opening_balance":155000,
        "base_spec":{"source":"entered","trajectory":"flat","value":5000},
        "components":[
            {"component_id":"ol-ap","name":"Accounts Payable & Accrued Expenses",
             "terms":[_term("ol-ap-wf","workforce_role_count","wf-total-ol",3000)]},
            {"component_id":"ol-lease","name":"Operating Lease Liability",
             "terms":[
                 _term("ol-lease-rou","fixed_asset_level",FIXED_ASSET_FORMULA_BASE_SERIES_ID,1.0),
                 _term("ol-lease-ad","fixed_asset_level",FIXED_ASSET_ACCUM_DEP_SERIES_ID,-1.0),
             ]},
        ]}


def main():
    p=f=0
    def ck(name, ok, detail=""):
        nonlocal p,f
        if ok: p+=1; print("  PASS ", name + (f" — {detail}" if detail else ""))
        else: f+=1; print("  FAIL ", name + (f" — {detail}" if detail else ""))

    # Legacy scalar remains byte-for-byte economically flat when the generalized model is absent.
    c=_cfg(); a=c["assumptions"]; a["other_liabilities"]=777000
    r=run_pf_a(copy.deepcopy(c))
    ck("legacy other_liabilities keeps historical result shape and economics when generalized model is absent",
       "otherLiab" not in r["bs"] and abs(float(r["bs"]["totalAssets"][0] or 0.0))>0)

    c=_cfg(); a=c["assumptions"]; _activate(a)
    errs=validate_errors_v2(copy.deepcopy(c))
    ck("generalized other-liability model validates", not errs, str(errs[:3]))
    r=run_pf_a(copy.deepcopy(c))
    fa=r["fixed_assets"]["formula_level"]
    ck("Fixed Asset Formula / level publishes the entered ROU base as a stable Series",
       fa.get("base_series_id")==FIXED_ASSET_FORMULA_BASE_SERIES_ID
       and fa.get("base_name")=="Fixed Asset ROU"
       and abs(fa["base"][0]-120000)<1e-9)
    ck("Fixed Asset Formula / level publishes named linked component contributions",
       abs(fa["components"][0]["amount"][0]-8000)<1e-9
       and abs(r["fixed_assets"]["gross"][1]-128000)<1e-9)
    ck("published Fixed Asset Series resolve by stable ID",
       abs(fixed_asset_series_by_id(a,FIXED_ASSET_FORMULA_BASE_SERIES_ID,12,12)[0]-120000)<1e-9
       and abs(fixed_asset_series_by_id(a,"fa-fte-fixtures",12,12)[0]-8000)<1e-9)
    od=r["other_liabilities_detail"]
    ck("AP/accrued expense link uses Total workforce × liability/FTE",
       abs(od["components"][0]["amount"][0]-30000)<1e-9)
    lease=od["components"][1]
    ck("Operating Lease Liability uses ROU gross component less accumulated depreciation",
       abs(lease["terms"][0]["driver"][0]-120000)<1e-9
       and abs(lease["terms"][1]["driver"][0]-1000)<1e-9
       and abs(lease["terms"][1]["multiplier"][0]+1.0)<1e-9
       and abs(lease["amount"][0]-119000)<1e-9)
    ck("lease liability excludes unrelated Workforce-linked fixed assets",
       abs(r["fixed_assets"]["net"][1]-127000)<1e-9
       and abs(lease["amount"][0]-119000)<1e-9
       and abs((r["fixed_assets"]["net"][1]-lease["amount"][0])-8000)<1e-9)
    ck("Formula / level sums base plus named liability components",
       abs(r["bs"]["otherLiab"][0]-155000)<1e-9 and abs(r["bs"]["otherLiab"][1]-154000)<1e-9)
    c_more=copy.deepcopy(c)
    c_more["assumptions"]["other_liabilities_model"]["base_spec"]["value"] += 1000
    r_more=run_pf_a(c_more)
    _fund0=(r["bs"]["cash"][1]+r["bs"]["sec"][1]-r["bs"]["borrow"][1])
    _fund1=(r_more["bs"]["cash"][1]+r_more["bs"]["sec"][1]-r_more["bs"]["borrow"][1])
    ck("dynamic other liabilities participate in funding waterfall",
       (r_more["bs"]["otherLiab"][1]-r["bs"]["otherLiab"][1])==1000
       and (_fund1-_fund0)>999.0)

    pub=run_parity(copy.deepcopy(c))
    od=pub.get("other_liabilities_detail") or {}
    comps=od.get("components") or []
    ck("public liability audit preserves driver units and signed multipliers",
       abs((od.get("total") or [0,0])[1]-154.0)<1e-9
       and abs(comps[0]["terms"][0]["driver"][0]-10.0)<1e-9
       and abs(comps[0]["terms"][0]["multiplier"][0]-3.0)<1e-9
       and abs(comps[1]["terms"][0]["driver"][0]-120.0)<1e-9
       and abs(comps[1]["terms"][1]["driver"][0]-1.0)<1e-9
       and abs(comps[1]["terms"][1]["multiplier"][0]+1.0)<1e-9)
    d=derived_lines(pub,c)
    ck("presentation uses modeled other-liability series rather than stale scalar",
       abs(d["otherLiab"][1]-154.0)<1e-9)

    rv=run_v2(copy.deepcopy(c))
    ck("public run exposes modeled other-liability balance and formula terms",
       abs((((rv.get("presentation") or {}).get("derived") or {}).get("otherLiab") or [0,0])[1]-154.0)<1e-9
       and abs((((rv.get("other_liabilities") or {}).get("total") or [0,0])[1]-154.0))<1e-9
       and len((((rv.get("other_liabilities") or {}).get("components") or [{},{}])[1].get("terms") or []))==2)

    import io, openpyxl
    fiw_bytes,_=build_fiw(copy.deepcopy(c)); wb=openpyxl.load_workbook(io.BytesIO(fiw_bytes))
    ck("FIW exports generalized other liabilities as Formula / level", "ASSM_OTHER_LIAB" in wb.sheetnames)
    if "ASSM_OTHER_LIAB" in wb.sheetnames:
        ws=wb["ASSM_OTHER_LIAB"]
        rows={str(rr[0].value):rr for rr in ws.iter_rows(min_row=2) if rr[0].value}
        k="other_liabilities_model.components.0.terms.0.multiplier_spec.value"
        ck("FIW shows workforce liability multiplier in $000s/FTE",
           k in rows and abs(float(rows[k][3].value)-3.0)<1e-9 and "$000s/FTE" in str(rows[k][4].value))
        if k in rows: rows[k][3].value=4.0
        b=io.BytesIO(); wb.save(b)
        merged, rep=diff_import(b.getvalue(),copy.deepcopy(c))
        ck("FIW liability multiplier edit round-trips without unit drift",
           abs(merged["assumptions"]["other_liabilities_model"]["components"][0]["terms"][0]["multiplier_spec"]["value"]-4000)<1e-9)

    awb=calculation_audit_workbook(copy.deepcopy(c),rv)
    labels={str(rr[1].value).strip() for rr in awb["Other Liabilities"].iter_rows(min_row=4) if len(rr)>1 and rr[1].value}
    ck("Calculation Audit exposes liability terms, signed contributions and component subtotal",
       any(x.startswith("Term 1 driver") for x in labels)
       and "Term 2 contribution" in labels and "Calculated liability component" in labels)

    bad=copy.deepcopy(c)
    bad["assumptions"]["other_liabilities_model"]["components"][0]["terms"][0]["driver_spec"]["link"]["series_id"]="missing"
    ck("validation rejects missing Workforce Count liability link",
       any("linked Workforce Count Series" in str((x or {}).get("message",x)) for x in validate_errors_v2(bad)))
    badfa=copy.deepcopy(c)
    badfa["assumptions"]["other_liabilities_model"]["components"][1]["terms"][0]["driver_spec"]["link"]["series_id"]="missing-fa"
    ck("validation rejects missing Fixed Asset liability link",
       any("linked Fixed Asset Series" in str((x or {}).get("message",x)) for x in validate_errors_v2(badfa)))
    shadow=copy.deepcopy(c)
    shadow["assumptions"]["fixed_assets"]["formula_level"]["components"][0]["component_id"]=FIXED_ASSET_FORMULA_BASE_SERIES_ID
    ck("validation reserves canonical Fixed Asset Series IDs against component shadowing",
       any("series_id values must be unique" in str((x or {}).get("message",x)) for x in validate_errors_v2(shadow)))

    # r127 single-driver storage remains readable with historical net-fixed-asset semantics.
    legacy=copy.deepcopy(c)
    legacy["assumptions"]["other_liabilities_model"]["components"]=[{
        "component_id":"legacy-lease","name":"Legacy r127 link",
        "driver":{"kind":"fixed_asset_net"},
        "multiplier_spec":{"source":"entered","trajectory":"flat","value":1.0}}]
    lr=run_pf_a(legacy)
    ck("r127 single-driver liability configs remain readable without silent economic migration",
       abs(lr["other_liabilities_detail"]["components"][0]["amount"][0]-127000)<1e-9)

    # Profile B parity: same generalized contract at quarterly cadence.
    cb=json.loads((Path(__file__).parents[1]/"fixtures"/"parity"/"configs"/"pf_b_base.json").read_text())
    ab=cb["assumptions"]; _activate(ab,4,12)
    rb=run_pf_b(copy.deepcopy(cb))
    # Q1: 5k base + 30k AP + (120k ROU - 3k accumulated depreciation) = 152k.
    ck("Profile B consumes the same multi-term liability Formula / level contract",
       abs(rb["bs"]["otherLiab"][0]-152000)<1e-9)

    print(f"Other liabilities: {p}/{p+f} passed")
    return 0 if f==0 else 1

if __name__=="__main__": raise SystemExit(main())
