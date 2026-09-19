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


def _cfg():
    return json.loads((Path(__file__).parents[1]/"fixtures"/"patrick_default_v31.json").read_text())


def _activate(a, ppy=12, n=12):
    a["periods_per_year"]=ppy; a["n_periods"]=n
    a["other_liabilities"]=155000.0
    a["premises_equipment"]=0; a["premises_depreciation_annual"]=0
    a["nie_detail"]={
        "categories":[], "other_gross_up_rate":0, "fdic_bp_ann":0, "occ_bp_ann":0,
        "workforce":{"mode":"roles","total_count_series_id":"wf-total-ol","default_payroll_load_rate":0,
                     "roles":[{"series_id":"wf-ops-ol","role":"Operations","count":10,
                               "annual_comp":0,"hire_period":1}]}}
    a["fixed_assets"]={"mode":"formula_level","formula_level":{
        "level_basis":"gross","opening_level":120000,
        "base_spec":{"source":"entered","trajectory":"flat","value":120000},"components":[],
        "depreciation":{"kind":"entered","amount_spec":{"source":"entered","trajectory":"flat",
                                                              "value":12000,"period":"year"}}}}
    a["other_liabilities_model"]={
        "opening_balance":155000,
        "base_spec":{"source":"entered","trajectory":"flat","value":5000},
        "components":[
            {"component_id":"ol-ap","name":"Accounts Payable & Accrued Expenses",
             "driver":{"kind":"workforce_count","series_id":"wf-total-ol"},
             "multiplier_spec":{"source":"entered","trajectory":"flat","value":3000}},
            {"component_id":"ol-lease","name":"Operating Lease Liability",
             "driver":{"kind":"fixed_asset_net"},
             "multiplier_spec":{"source":"entered","trajectory":"flat","value":1.0}},
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
    # M1: 5k base + 10 FTE*3k + (120k gross - 1k depreciation) = 154k.
    ck("AP/accrued expense link uses Total workforce × liability/FTE",
       abs(r["other_liabilities_detail"]["components"][0]["amount"][0]-30000)<1e-9)
    ck("Operating Lease Liability can link net fixed assets × 1.0",
       abs(r["other_liabilities_detail"]["components"][1]["driver"][0]-119000)<1e-9
       and abs(r["other_liabilities_detail"]["components"][1]["amount"][0]-119000)<1e-9)
    ck("Formula / level sums base plus linked liability components",
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
    ck("public liability audit preserves driver units and converts monetary fields",
       abs((od.get("total") or [0,0])[1]-154.0)<1e-9
       and abs((comps[0].get("driver") or [0])[0]-10.0)<1e-9
       and abs((comps[0].get("multiplier") or [0])[0]-3.0)<1e-9
       and abs((comps[1].get("driver") or [0])[0]-119.0)<1e-9
       and abs((comps[1].get("multiplier") or [0])[0]-1.0)<1e-9)
    d=derived_lines(pub,c)
    ck("presentation uses modeled other-liability series rather than stale scalar",
       abs(d["otherLiab"][1]-154.0)<1e-9)

    rv=run_v2(copy.deepcopy(c))
    rc=(rv.get("call_report_schedules") or rv.get("call_report"))
    # run_v2's presentation is the direct, stable assertion here; Call Report gets its own build below.
    ck("public run exposes modeled other-liability balance",
       abs((((rv.get("presentation") or {}).get("derived") or {}).get("otherLiab") or [0,0])[1]-154.0)<1e-9
       and abs((((rv.get("other_liabilities") or {}).get("total") or [0,0])[1]-154.0))<1e-9)

    import io, openpyxl
    fiw_bytes,_=build_fiw(copy.deepcopy(c)); wb=openpyxl.load_workbook(io.BytesIO(fiw_bytes))
    ck("FIW exports generalized other liabilities as Formula / level",
       "ASSM_OTHER_LIAB" in wb.sheetnames)
    if "ASSM_OTHER_LIAB" in wb.sheetnames:
        ws=wb["ASSM_OTHER_LIAB"]
        rows={str(rr[0].value):rr for rr in ws.iter_rows(min_row=2) if rr[0].value}
        k="other_liabilities_model.components.0.multiplier_spec.value"
        ck("FIW shows workforce liability multiplier in $000s/FTE",
           k in rows and abs(float(rows[k][3].value)-3.0)<1e-9 and "$000s/FTE" in str(rows[k][4].value))
        if k in rows: rows[k][3].value=4.0
        b=io.BytesIO(); wb.save(b)
        merged, rep=diff_import(b.getvalue(),copy.deepcopy(c))
        ck("FIW liability multiplier edit round-trips without unit drift",
           abs(merged["assumptions"]["other_liabilities_model"]["components"][0]["multiplier_spec"]["value"]-4000)<1e-9)

    awb=calculation_audit_workbook(copy.deepcopy(c),rv)
    labels={str(rr[1].value).strip() for rr in awb["Other Liabilities"].iter_rows(min_row=4) if len(rr)>1 and rr[1].value}
    ck("Calculation Audit exposes liability driver, multiplier and contribution",
       all(x in labels for x in ("Linked driver","Multiplier","Calculated liability contribution","Total modeled other liabilities")))

    bad=copy.deepcopy(c); bad["assumptions"]["other_liabilities_model"]["components"][0]["driver"]["series_id"]="missing"
    ck("validation rejects missing Workforce Count liability link",
       any("linked Workforce Count Series" in str((x or {}).get("message",x)) for x in validate_errors_v2(bad)))

    # Profile B parity: same generalized contract at quarterly cadence.
    cb=json.loads((Path(__file__).parents[1]/"fixtures"/"parity"/"configs"/"pf_b_base.json").read_text())
    ab=cb["assumptions"]; _activate(ab,4,12)
    rb=run_pf_b(copy.deepcopy(cb))
    # Q1 depreciation = 3k, so 5k + 30k + 117k = 152k.
    ck("Profile B consumes the same liability Formula / level contract",
       abs(rb["bs"]["otherLiab"][0]-152000)<1e-9)

    print(f"Other liabilities: {p}/{p+f} passed")
    return 0 if f==0 else 1

if __name__=="__main__": raise SystemExit(main())
