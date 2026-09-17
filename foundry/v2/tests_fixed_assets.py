import copy
from foundry.v2.fixed_assets import fixed_asset_formula_level, fixed_asset_schedule
from foundry.v2.engine_q_a import run_pf_a
from foundry.v2.engine_q_b import run_pf_b
from foundry.v2.parity import run_parity
from foundry.v2.excel_q import results_workbook_v2
from foundry.v2.run_q import run_v2
from foundry.v2.validate_q import validate_errors_v2
from foundry.v2.fiw import build_fiw, diff_import
from foundry.v2.audit_workbook import calculation_audit_workbook


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

    # Formula / level is the second methodology, not a third asset-vintage carve-out.
    # The stock is authored directly as base + linked Series × multiplier; depreciation
    # remains a separate flow and the engine derives gross/accumulated PP&E for presentation.
    fa_ass={"nie_detail":{"workforce":{"total_count_series_id":"wf-total",
              "roles":[{"series_id":"wf-role-a","role":"Operations","count":10,"hire_period":1}]}}}
    flcfg={"mode":"formula_level","formula_level":{"opening_net":120000,
           "base_spec":{"source":"entered","trajectory":"flat","value":100000},
           "components":[{"component_id":"fa-level-1","name":"Linked asset component",
             "driver_spec":{"source":"link","link":{"kind":"workforce_role_count","series_id":"wf-total","aggregation":"end"}},
             "multiplier_spec":{"source":"entered","trajectory":"flat","value":5000}}],
           "depreciation":{"kind":"rate_of_level","rate_spec":{"source":"entered","trajectory":"flat","value":0.12,"period":"year"}}}}
    fl=fixed_asset_formula_level(flcfg,fa_ass,3,12)
    ck("Formula / level computes base plus linked driver × multiplier",
       fl["net"]==[120000.0,150000.0,150000.0,150000.0])
    ck("Formula / level annual depreciation rate periodizes exactly once",
       all(abs(x-1500)<1e-8 for x in fl["depreciation_expense"][1:]))
    ck("Formula / level reconciles gross, accumulated depreciation and implied CAPEX",
       abs(fl["gross"][1]-151500)<1e-8 and abs(fl["accumulated_depreciation"][2]-3000)<1e-8
       and abs(fl["capex"][1]-31500)<1e-8 and abs(fl["capex"][2]-1500)<1e-8)

    fl_month=copy.deepcopy(flcfg);fl_month["formula_level"]["depreciation"]["rate_spec"]={"source":"entered","trajectory":"flat","value":0.01,"period":"month"}
    flm=fixed_asset_formula_level(fl_month,fa_ass,1,12)
    ck("1%/month and 12%/year depreciation are economically equivalent in monthly cadence",
       abs(flm["depreciation_expense"][1]-fl["depreciation_expense"][1])<1e-8)

    # End-to-end engine seam: the Formula / level resolver must consume the same stable
    # Workforce Count Series the rest of Foundry publishes, then post net PP&E and depreciation.
    fl_engine=_base_cfg(); fl_engine=copy.deepcopy(fl_engine)
    fea=fl_engine["assumptions"]; fea["periods_per_year"]=12; fea["n_periods"]=12
    fea["premises_equipment"]=0; fea["premises_depreciation_annual"]=0
    fea["nie_detail"]={
        "categories":[], "other_gross_up_rate":0, "fdic_bp_ann":0, "occ_bp_ann":0,
        "workforce":{"mode":"roles","total_count_series_id":"wf-total-fa","default_payroll_load_rate":0,
          "roles":[{"series_id":"wf-fa-ops","role":"Operations","count":10,"annual_comp":0,"hire_period":1}]}}
    fea["fixed_assets"]={"mode":"formula_level","formula_level":{
        "opening_net":120000,
        "base_spec":{"source":"entered","trajectory":"flat","value":100000},
        "components":[{"component_id":"fa-level-engine","name":"Equipment capacity",
          "driver_spec":{"source":"link","link":{"kind":"workforce_role_count","series_id":"wf-total-fa","aggregation":"end"}},
          "multiplier_spec":{"source":"entered","trajectory":"flat","value":5000}}],
        "depreciation":{"kind":"rate_of_level","rate_spec":{"source":"entered","trajectory":"flat","value":0.12,"period":"year"}}}}
    fer=run_pf_a(copy.deepcopy(fl_engine))
    ck("Profile A posts Formula / level net PP&E from linked Workforce Count",
       abs(fer["bs"]["premises"][0]-120000)<1e-8 and abs(fer["bs"]["premises"][1]-150000)<1e-8
       and (fer.get("fixed_assets") or {}).get("mode")=="formula_level")
    ck("Profile A posts Formula / level depreciation to NIE",
       abs(fer["is"]["depreciationExpense"][0]-1500)<1e-8)
    ck("Formula / level validates end-to-end", not validate_errors_v2(copy.deepcopy(fl_engine)),
       str(validate_errors_v2(copy.deepcopy(fl_engine))[:3]))
    fer_public=run_parity(copy.deepcopy(fl_engine))
    ffl=(fer_public.get("fixed_assets") or {}).get("formula_level") or {}
    ck("public Formula / level audit units convert balances and multipliers to $000s",
       abs((ffl.get("opening_net") or 0)-120)<1e-8
       and abs(((ffl.get("base") or [0])[0])-100)<1e-8
       and abs(((((ffl.get("components") or [{}])[0]).get("multiplier") or [0])[0])-5)<1e-8
       and abs(((((ffl.get("components") or [{}])[0]).get("amount") or [0])[0])-50)<1e-8)

    import io, openpyxl
    fl_data,_=build_fiw(fl_engine); fl_wb=openpyxl.load_workbook(io.BytesIO(fl_data))
    ck("FIW exports Formula / level without flattening it to an asset schedule",
       "ASSM_FIXED_ASSETS_LEVEL" in fl_wb.sheetnames and "ASSM_FIXED_ASSETS" not in fl_wb.sheetnames)
    fl_ws=fl_wb["ASSM_FIXED_ASSETS_LEVEL"]
    fl_rows={str(r[0].value):r for r in fl_ws.iter_rows(min_row=2) if r[0].value}
    mkey="fixed_assets.formula_level.components.0.multiplier_spec.value"
    ck("FIW Formula / level exposes linked multiplier in $000s per driver unit",
       mkey in fl_rows and abs(float(fl_rows[mkey][3].value)-5.0)<1e-9
       and "$000s/driver-unit" in str(fl_rows[mkey][4].value))
    if mkey in fl_rows: fl_rows[mkey][3].value=6.0
    fl_buf=io.BytesIO(); fl_wb.save(fl_buf)
    fl_merged,fl_rep=diff_import(fl_buf.getvalue(),copy.deepcopy(fl_engine))
    ck("FIW Formula / level multiplier edit round-trips with correct units",
       abs(fl_merged["assumptions"]["fixed_assets"]["formula_level"]["components"][0]["multiplier_spec"]["value"]-6000)<1e-9
       and any(e.get("key")==mkey and abs(float(e.get("to") or 0)-6000)<1e-9 for e in (fl_rep.get("edits") or [])),
       str(fl_rep.get("edit_count")))

    fl_public=run_v2(copy.deepcopy(fl_engine))
    fl_audit=calculation_audit_workbook(copy.deepcopy(fl_engine), fl_public)
    fl_labels={str(r[1].value).strip():r for r in fl_audit["Fixed Assets"].iter_rows(min_row=4) if len(r)>1 and r[1].value}
    ck("Calculation Audit exposes Formula / level driver, multiplier, contribution, depreciation and implied CAPEX",
       all(x in fl_labels for x in ("Linked driver quantity","Multiplier","Calculated level contribution",
                                    "Depreciation expense","CAPEX / (disposal)")))

    # Simple-mode disclosure: the Balance Sheet must show gross PP&E and accumulated
    # depreciation even when the user did not opt into the asset-level schedule.  Net
    # PP&E and total assets remain the same accounting series as before.
    simple=_base_cfg(); simple=copy.deepcopy(simple)
    sa=simple["assumptions"]; sa["periods_per_year"]=12; sa["n_periods"]=12
    sa["premises_equipment"]=1200000; sa["premises_depreciation_annual"]=120000
    sa.pop("fixed_assets",None)
    sr=run_pf_a(copy.deepcopy(simple))
    ck("Simple Profile A exposes gross and accumulated depreciation",
       "premisesGross" in sr["bs"] and "premisesAccumDep" in sr["bs"]
       and sr["bs"]["premisesGross"][1]==1200000
       and abs(sr["bs"]["premisesAccumDep"][1]-10000)<1e-9
       and abs(sr["bs"]["premises"][1]-1190000)<1e-9)

    simple_public=run_v2(copy.deepcopy(simple))
    spbs=simple_public["financials"]["bs"]
    ck("public Balance Sheet payload surfaces Simple accumulated depreciation",
       "premisesGross" in spbs and "premisesAccumDep" in spbs
       and abs(spbs["premisesAccumDep"][1]-10.0)<1e-9
       and abs(spbs["premises"][1]-1190.0)<1e-9)

    simple_rp=run_parity(copy.deepcopy(simple))
    simple_wb=results_workbook_v2(simple,simple_rp)
    simple_labels={str(row[0].value).strip():row for row in simple_wb["Balance Sheet"].iter_rows(min_row=2) if len(row)>0 and row[0].value}
    _ad_row=simple_labels.get("Less: accumulated depreciation")
    ck("results workbook surfaces accumulated depreciation in Simple mode",
       _ad_row is not None and _ad_row[6].value == -10.0, str(_ad_row[6].value if _ad_row else None))

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
    ck("Income Statement exposes depreciation separately without changing overhead",
       abs(r["is"]["depreciationExpense"][0]-10000)<1e-9
       and abs((r["is"]["workforceComp"][0]+r["is"]["otherOpex"][0]+r["is"]["depreciationExpense"][0])-r["is"]["overhead"][0])<1e-9)

    import json, pathlib
    cfgb_simple=json.loads((pathlib.Path(__file__).parents[1]/"fixtures"/"parity"/"configs"/"pf_b_base.json").read_text())
    cfgb_simple["assumptions"]["premises_equipment"]=1200000
    cfgb_simple["assumptions"]["premises_depreciation_annual"]=120000
    cfgb_simple["assumptions"].pop("fixed_assets",None)
    rbs=run_pf_b(copy.deepcopy(cfgb_simple))
    ck("Simple Profile B exposes gross and accumulated depreciation",
       "premisesGross" in rbs["bs"] and "premisesAccumDep" in rbs["bs"]
       and rbs["bs"]["premisesGross"][0]==1200000
       and abs(rbs["bs"]["premisesAccumDep"][0]-30000)<1e-9
       and abs(rbs["bs"]["premises"][0]-1170000)<1e-9)

    cfgb=json.loads((pathlib.Path(__file__).parents[1]/"fixtures"/"parity"/"configs"/"pf_b_base.json").read_text())
    cfgb["assumptions"]["premises_equipment"]=0; cfgb["assumptions"]["premises_depreciation_annual"]=0
    cfgb["assumptions"]["fixed_assets"]={"mode":"schedule","assets":[{"name":"Branch buildout","cost":400000,"in_service_period":0,"useful_life_years":4}]}
    rb=run_pf_b(copy.deepcopy(cfgb))
    ck("Profile B consumes the same fixed-asset schedule contract",
       abs(rb["bs"]["premises"][0]-375000)<1e-6 and (rb.get("fixed_assets") or {}).get("mode")=="schedule")
    ck("Profile B Income Statement also separates depreciation",
       abs(rb["is"]["depreciationExpense"][0]-25000)<1e-9
       and abs((rb["is"]["workforceComp"][0]+rb["is"]["otherOpex"][0]+rb["is"]["depreciationExpense"][0])-rb["is"]["fixedOpex"][0])<1e-9)

    rp=run_parity(copy.deepcopy(cfg))
    wb_res=results_workbook_v2(cfg,rp)
    bs_labels={str(row[0].value).strip():row for row in wb_res["Balance Sheet"].iter_rows(min_row=2) if len(row)>0 and row[0].value}
    ck("results workbook exposes gross, accumulated depreciation, and net PP&E in schedule mode",
       "Premises and fixed assets, gross" in bs_labels and "Less: accumulated depreciation" in bs_labels
       and "Premises and fixed assets, net of accumulated depreciation" in bs_labels)
    is_labels={str(row[0].value).strip():row for row in wb_res["Income Statement"].iter_rows(min_row=2) if len(row)>0 and row[0].value}
    ck("results workbook breaks out workforce, other Opex, and depreciation",
       "Workforce compensation" in is_labels and "Other operating expense" in is_labels
       and "Depreciation expense" in is_labels
       and "Salaries, occupancy, and other overhead" not in is_labels)

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
    ck("on-screen Balance Sheet renders gross, accumulated depreciation, and net PP&E",
       "Premises & Equipment, gross" in html
       and "Less: Accumulated Depreciation" in html
       and "Premises & Equipment, net" in html
       and "fin.bs.premisesGross" in html
       and "fin.bs.premisesAccumDep" in html)

    ck("on-screen Income Statement renders the promised NIE breakout",
       "rowIS('Workforce compensation', fin.is.workforceComp" in html
       and "rowIS('Other operating expense', fin.is.otherOpex" in html
       and "rowIS('Depreciation expense', fin.is.depreciationExpense" in html
       and "rowIS('Product operating expense', fin.is.prodOpex || fin.is.opexProd" in html
       and "rowIS('Fee product operating costs', fin.is.feeOpex" in html
       and "rowIS('Total noninterest expense', D.nie, 'subtotal')" in html)
    _is_start=html.index('if(currentTab==="is")')
    _is_end=html.index('if(currentTab==="ratios")', _is_start) if 'if(currentTab==="ratios")' in html[_is_start:] else len(html)
    _is_block=html[_is_start:_is_end]
    ck("on-screen Income Statement no longer collapses detail into Corporate Overhead",
       "Noninterest Expense: Corporate Overhead" not in _is_block)

    ck("Configuration separates pre-opening expenses from Fixed assets / CAPEX",
       '>Pre-opening expenses</span><button class="nie-section-toggle"' in html
       and '>Fixed assets / CAPEX</span><button class="nie-section-toggle"' in html
       and "cfgSectionSetOpen('preopening'" in html and "cfgSectionSetOpen('fixedassets'" in html
       and '>Asset schedule</button>' in html)
    ck("fixed-asset bulk entry has Paste/Add/Clear authoring",
       'Paste assets' in html and '+ Add asset' in html and 'faClear()' in html)
    ck("Operating Expense no longer owns the fixed-asset inputs",
       'Fixed assets</div><div class="nie-section-note">Applies in either operating-expense mode.' not in html)

    print(f"Fixed assets: {p}/{p+f} passed")
    return 0 if f==0 else 1

if __name__=="__main__": raise SystemExit(main())
