import copy
from foundry.v2.fixed_assets import fixed_asset_schedule
from foundry.v2.engine_q_a import run_pf_a
from foundry.v2.engine_q_b import run_pf_b
from foundry.v2.parity import run_parity
from foundry.v2.excel_q import results_workbook_v2
from foundry.v2.run_q import run_v2
from foundry.v2.validate_q import validate_errors_v2
from foundry.v2.fiw import build_fiw, diff_import


def _base_cfg():
    import json, pathlib
    p = pathlib.Path(__file__).parents[1] / "fixtures" / "patrick_default_v31.json"
    return json.loads(p.read_text())


def main():
    p=f=0
    def ck(name, ok, detail=""):
        nonlocal p,f
        if ok: p+=1; print("  PASS ", name + (f" — {detail}" if detail else ""))
        else: f+=1; print("  FAIL ", name + (f" — {detail}" if detail else ""))

    s=fixed_asset_schedule({"assets":[{"name":"Furniture","cost":600000,"in_service_period":0,"useful_life_years":5}]},36,12)
    ck("pre-opening CAPEX lands in opening gross PP&E", s["gross"][0]==600000 and s["preopening_capex"]==600000)
    ck("at-opening asset depreciates from M1 at straight-line monthly rate", abs(s["depreciation_expense"][1]-10000)<1e-9 and abs(s["net"][1]-590000)<1e-9)

    s2=fixed_asset_schedule({"assets":[{"name":"Expansion","cost":240000,"in_service_period":7,"useful_life_years":2}]},36,12)
    ck("post-opening asset is absent before placed-in-service period", s2["gross"][6]==0 and s2["depreciation_expense"][6]==0)
    ck("post-opening CAPEX and depreciation begin in placed-in-service period", s2["gross"][7]==240000 and s2["capex"][7]==240000 and abs(s2["depreciation_expense"][7]-10000)<1e-9)

    s3=fixed_asset_schedule({"assets":[{"name":"Existing","opening_gross_cost":800000,"opening_accumulated_depreciation":300000,"remaining_life_years":4}]},16,4)
    ck("existing asset preserves opening gross and accumulated depreciation", s3["gross"][0]==800000 and s3["accumulated_depreciation"][0]==300000 and s3["net"][0]==500000)
    ck("existing asset depreciates remaining NBV across remaining life", abs(s3["depreciation_expense"][1]-31250)<1e-9 and abs(s3["net"][16])<1e-9)

    # Engine accounting: CAPEX is capitalized, not burned through opening retained earnings.
    cfg=_base_cfg(); cfg=copy.deepcopy(cfg)
    a=cfg["assumptions"]; a["periods_per_year"]=12; a["n_periods"]=36
    a["premises_equipment"]=0; a["premises_depreciation_annual"]=0
    cfg["pre_opening"]={"expenses":[{"category":"Legal","total":100000}], "min_day1_capital":0}
    a["fixed_assets"]={"mode":"schedule","assets":[{"name":"IT","cost":600000,"in_service_period":0,"useful_life_years":5}]}
    r=run_pf_a(cfg)
    ck("engine exposes gross/accumulated/net fixed-asset series", "premisesGross" in r["bs"] and "premisesAccumDep" in r["bs"] and abs(r["bs"]["premises"][0]-600000)<1e-9)
    ck("pre-opening CAPEX does not reduce opening retained earnings", abs(r["bs"]["re"][0] + 100000)<1e-6, str(r["bs"]["re"][0]))
    ck("scheduled depreciation feeds NIE", r["is"]["overhead"][0] >= 10000)

    import json, pathlib
    cfgb=json.loads((pathlib.Path(__file__).parents[1]/"fixtures"/"parity"/"configs"/"pf_b_base.json").read_text())
    cfgb["assumptions"]["premises_equipment"]=0; cfgb["assumptions"]["premises_depreciation_annual"]=0
    cfgb["assumptions"]["fixed_assets"]={"mode":"schedule","assets":[{"name":"Branch buildout","cost":400000,"in_service_period":0,"useful_life_years":4}]}
    rb=run_pf_b(copy.deepcopy(cfgb))
    ck("Profile B consumes the same fixed-asset schedule contract",
       abs(rb["bs"]["premises"][0]-375000)<1e-6 and (rb.get("fixed_assets") or {}).get("mode")=="schedule")

    rp=run_parity(copy.deepcopy(cfg))
    wb_res=results_workbook_v2(cfg,rp)
    bs_labels={str(row[0].value).strip():row for row in wb_res["Balance Sheet"].iter_rows(min_row=2) if len(row)>0 and row[0].value}
    ck("results workbook exposes gross, accumulated depreciation, and net PP&E in schedule mode",
       "Premises and fixed assets, gross" in bs_labels and "Less: accumulated depreciation" in bs_labels
       and "Premises and fixed assets, net of accumulated depreciation" in bs_labels)

    errs=validate_errors_v2(cfg)
    ck("fixed-asset schedule validates cleanly", not errs, str(errs[:3]))
    bad=copy.deepcopy(cfg); bad["assumptions"]["fixed_assets"]["assets"][0]["residual_value"]=700000
    ck("validation rejects residual value above cost", any("residual_value cannot exceed cost" in str((x or {}).get("message",x)) for x in validate_errors_v2(bad)))

    rr=run_v2(copy.deepcopy(cfg))
    po=rr.get("pre_open") or {}
    ck("public run distinguishes expense burn from capitalized pre-opening CAPEX",
       abs(po.get("burn_total",0)-100000)<1 and abs(po.get("preopening_capex",0)-600000)<1
       and abs(po.get("cash_uses_total",0)-700000)<1, str(po))
    ck("public run exposes fixed-asset audit schedule",
       (rr.get("fixed_assets") or {}).get("mode")=="schedule" and len((rr.get("fixed_assets") or {}).get("assets") or [])==1)

    import io, openpyxl
    data,_=build_fiw(cfg); wb=openpyxl.load_workbook(io.BytesIO(data))
    ck("FIW exports an editable fixed-asset schedule", "ASSM_FIXED_ASSETS" in wb.sheetnames)
    ws=wb["ASSM_FIXED_ASSETS"]; rows={str(r[0].value):r for r in ws.iter_rows(min_row=2)}
    key="fixed_assets.assets.0.useful_life_years"
    if key in rows: rows[key][3].value=7
    buf=io.BytesIO(); wb.save(buf)
    merged,rep=diff_import(buf.getvalue(),copy.deepcopy(cfg))
    ck("FIW fixed-asset useful-life edit round-trips",
       abs(merged["assumptions"]["fixed_assets"]["assets"][0]["useful_life_years"]-7)<1e-12
       and rep.get("edit_count")==1, str(rep.get("edit_count")))

    html=__import__("pathlib").Path("web/console_v2.html").read_text(encoding="utf-8")
    ck("Configuration separates pre-opening expenses from Fixed assets / CAPEX",
       '<div class="csub">Pre-opening expenses</div>' in html and '<div class="csub">Fixed assets / CAPEX</div>' in html
       and '>Asset schedule</button>' in html)
    ck("fixed-asset bulk entry has Paste/Add/Clear authoring",
       'Paste assets' in html and '+ Add asset' in html and 'faClear()' in html)
    ck("Operating Expense no longer owns the fixed-asset inputs",
       'Fixed assets</div><div class="nie-section-note">Applies in either operating-expense mode.' not in html)

    print(f"Fixed assets: {p}/{p+f} passed")
    return 0 if f==0 else 1

if __name__=="__main__": raise SystemExit(main())
