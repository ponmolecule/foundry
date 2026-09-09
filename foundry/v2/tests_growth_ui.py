"""Browser authoring regression gate for growth/workforce controls."""
from __future__ import annotations
import json, subprocess, sys
from pathlib import Path


def main():
    p=f=0
    def ck(name, cond, detail=""):
        nonlocal p,f
        if cond:
            p+=1; print("  PASS ", name + (f" — {detail}" if detail else ""))
        else:
            f+=1; print("  FAIL ", name + (f" — {detail}" if detail else ""))

    html=Path("web/console_v2.html").read_text(encoding="utf-8")
    a=html.index("window.poPaste = function(")
    b=html.index("// Risk-based capital ratios", a)
    js=html[a:b]
    ma=html.index("window.nieOff = function(){")
    mb=html.index("// Static mirror", ma)
    js += "\n" + html[ma:mb]
    roles="\n".join(
        f"Role {i+1}\t{60+i}\tM{1+(i*7)%57}\t{2+(i%4)}" for i in range(48)
    )
    prefix=r'''
const window=globalThis;
let cfg={assumptions:{
  cac_feeds:{growth:{series_id:'cac-feed-growth',owner_module:'customer_acquisition'},wealth:{series_id:'cac-feed-wealth',owner_module:'customer_acquisition'}},
  obs_exposures:[
    {name:'Custody',managed_notional_source:'growth',managed_notional_source_id:'cac-feed-growth'},
    {name:'Settlement',managed_notional_source:'growth',managed_notional_source_id:'cac-feed-growth'},
    {name:'Wealth Fees',managed_notional_source:'wealth',managed_notional_source_id:'cac-feed-wealth'}
  ]},pre_opening:{expenses:[]}};
window.confirm=()=>true;
function renderContent(){} function refresh(){} function appStatus(){}
function NP(){return 84;}
function PPY(){return 12;}
function _pf(x){ let n=parseFloat(String(x).replace(/[^0-9.\-]/g,'')); return isNaN(n)?0:n; }
'''
    suffix=r'''
cfg.assumptions.nie_detail=_newNieDetail();
const fresh=JSON.parse(JSON.stringify(cfg.assumptions.nie_detail));
window.nieCatPaste("Occupancy\t30","growth",3,"year","step","model_year",1);
const cat=JSON.parse(JSON.stringify(cfg.assumptions.nie_detail.categories[0]));
window.nieWorkforcePaste(__ROLES__);
const wf=cfg.assumptions.nie_detail.workforce;
const nroles=wf.roles.length, maxhire=Math.max(...wf.roles.map(r=>r.hire_period));
window.nieWorkforcePaste("Custody Ops\t120\tEOP AUC [Custody] >= 1B\t3.5");
const trigger=JSON.parse(JSON.stringify(wf.roles[wf.roles.length-1].activation));
window.nieWorkforcePaste("Controller, 3,000, M36, 4.0");
const csv=JSON.parse(JSON.stringify(wf.roles[wf.roles.length-1]));
window.nieWorkforcePaste("Role\tCount\tAnnual Comp ($000s/FTE)\tStart\tEnd\tEscalation %\tPayroll Load %\nTreasurer\t2\t130\tM8\tM36\t\t27.5");
const hdr=JSON.parse(JSON.stringify(wf.roles[wf.roles.length-1]));
window.nieWorkforcePaste("Role\tAnnual Comp ($000s/FTE)\tStart\tEnd\tEscalation %\tBenefits/Payroll %\nTreasurer 2\t145\tM9\tM40\t3.5\t24");
const canon=JSON.parse(JSON.stringify(wf.roles[wf.roles.length-1]));
window.nieWorkforcePaste("Role\tAnnualSalary\tHireMonth\tAnnualEscalation\nCFO\t3,000\t12\t4.0");
const compactHdr=JSON.parse(JSON.stringify(wf.roles[wf.roles.length-1]));
// Unit-parity audit: every bulk/manual user entry uses $000s. 3,000 means $3,000,000.
const entered="3,000", manualAmt=_pf(entered)*1000;
cfg.pre_opening.expenses=[]; window.poPaste("Legal\t3,000","replace"); const poAmt=cfg.pre_opening.expenses[0].total;
window.faPaste("Asset\tCost\tInService\tUsefulLife\nServers\t3,000\tAt opening\t5","replace"); const faAmt=cfg.assumptions.fixed_assets.assets[0].cost;
const ndParity=_ensureNieDetail(); ndParity.categories=[]; window.nieCatPaste("Insurance\t3,000","flat",0,"month","smooth","model_period",1); const catAmt=ndParity.categories[0].per_period;
window.nieWorkforcePaste("Role\tAnnual Comp ($000s/FTE)\tStart\tEscalation %\nParity Role\t3,000\tM1\t3"); const wfAmt=wf.roles[wf.roles.length-1].annual_comp;
window.nieWorkforceMetric(wf.roles.length-1,"mn::cac-feed-wealth"); const mnMetric=JSON.parse(JSON.stringify(wf.roles[wf.roles.length-1].activation));
const aucSources=_aucTriggerSources().map(x=>({key:x.key,label:x.label,aliases:x.aliases.slice().sort()}));
window.nieWorkforceMetric(wf.roles.length-1,"net_income_py"); const pyMetric=JSON.parse(JSON.stringify(wf.roles[wf.roles.length-1].activation));
cfg.assumptions.nie_detail.categories=[{name:'Saved detail',per_period:1}];
window.nieOff(); const simpleHasDraft=!!cfg.assumptions._nie_detail_draft && cfg.assumptions.nie_detail===null;
window.nieOn(); const restored=(cfg.assumptions.nie_detail.categories||[])[0].name;
cfg.pre_opening.expenses=[{category:'Legal',total:1000}];
window.poClear(); window.nieWorkforceClear(); window.nieCatClear();
console.log(JSON.stringify({fresh,cat,nroles,maxhire,trigger,csv,hdr,canon,compactHdr,unitParity:{manualAmt,poAmt,faAmt,catAmt,wfAmt},mnMetric,pyMetric,aucSources,simpleHasDraft,restored,cleared:{po:cfg.pre_opening.expenses.length,wf:wf.roles.length,cat:cfg.assumptions.nie_detail.categories.length}}));
'''.replace('__ROLES__', json.dumps(roles))
    br=subprocess.run(["node","-e",prefix+js+suffix],text=True,capture_output=True)
    bj={}
    if br.returncode==0 and br.stdout.strip():
        try: bj=json.loads(br.stdout.strip().splitlines()[-1])
        except Exception: pass
    ck("new NIE activation has zero categories and role-mode workforce, not FTE Y1/Y2/Y3",
       br.returncode==0 and bj.get("fresh",{}).get("categories")==[]
       and "fte_by_year" not in bj.get("fresh",{})
       and bj.get("fresh",{}).get("workforce",{}).get("mode")=="roles"
       and bj.get("fresh",{}).get("fdic_bp_ann")==5.0 and bj.get("fresh",{}).get("occ_bp_ann")==1.5,
       br.stderr.strip())
    gs=(bj.get("cat") or {}).get("growth_spec") or {}
    ck("category batch paste writes canonical 3%/year/step growth semantics",
       (bj.get("cat") or {}).get("trajectory")=="growth" and abs(gs.get("rate",0)-.03)<1e-12
       and gs.get("period")=="year" and gs.get("method")=="step")
    ck("one workforce paste compactly consumes 48 heterogeneous rows including M57",
       bj.get("nroles")==48 and bj.get("maxhire")==57)
    trig=bj.get("trigger") or {}
    ck("workforce paste accepts a compact named EOP-AUC trigger",
       trig.get("metric")=="managed_notional_end" and trig.get("source")=="cac-feed-growth"
       and trig.get("operator")==">=" and abs(trig.get("value",0)-1_000_000_000)<1
       and trig.get("timing")=="same_period")
    csv=bj.get("csv") or {}
    ck("workforce CSV keeps thousands commas inside compensation",
       csv.get("role")=="Controller" and abs(csv.get("annual_comp",0)-3_000_000)<1e-9 and csv.get("hire_period")==36)
    hdr=bj.get("hdr") or {}
    ck("header-aware workforce paste uses the same canonical schema and units as manual entry",
       hdr.get("role")=="Treasurer" and hdr.get("count")==2 and abs(hdr.get("annual_comp",0)-130000)<1e-9
       and hdr.get("hire_period")==8 and hdr.get("end_period")==36
       and "salary_growth_spec" not in hdr and abs(hdr.get("payroll_load_rate",0)-.275)<1e-12)
    canon=bj.get("canon") or {}
    ck("new canonical workforce paste needs no Count column and accepts Benefits/Payroll wording",
       canon.get("role")=="Treasurer 2" and canon.get("count")==1
       and abs(canon.get("annual_comp",0)-145000)<1e-9 and canon.get("hire_period")==9
       and canon.get("end_period")==40 and abs(canon.get("payroll_load_rate",0)-.24)<1e-12)
    compact=bj.get("compactHdr") or {}
    ck("compact spreadsheet headers AnnualSalary / HireMonth / AnnualEscalation are recognized",
       compact.get("role")=="CFO" and abs(compact.get("annual_comp",0)-3_000_000)<1e-9
       and compact.get("hire_period")==12 and abs((compact.get("salary_growth_spec") or {}).get("rate",0)-.04)<1e-12)
    up=bj.get("unitParity") or {}
    ck("paste/manual unit semantics are aligned across every bulk-entry surface",
       up=={"manualAmt":3000000,"poAmt":3000000,"faAmt":3000000,"catAmt":3000000,"wfAmt":3000000}, str(up))
    mn=bj.get("mnMetric") or {}; py=bj.get("pyMetric") or {}
    ck("metric choice binds EOP AUC to the stable CAC-feed Series ID and derives safe timing",
       mn.get("metric")=="managed_notional_end" and mn.get("source")=="cac-feed-wealth" and mn.get("timing")=="same_period"
       and py.get("metric")=="net_income" and py.get("reference")=="prior_year" and py.get("timing")=="next_period")
    srcs=bj.get("aucSources") or []
    ck("workforce AUC trigger choices deduplicate fee products onto underlying CAC sources",
       len(srcs)==2 and srcs[0].get("key")=="cac-feed-growth"
       and set(srcs[0].get("aliases") or [])=={"Custody","Settlement","growth"}
       and srcs[1].get("key")=="cac-feed-wealth")
    ck("Simple/Detailed mode switching preserves authored detail instead of deleting it",
       bj.get("simpleHasDraft") is True and bj.get("restored")=="Saved detail")
    cleared=bj.get("cleared") or {}
    ck("Clear actions independently wipe pre-opening, workforce, and operating-expense loads",
       cleared=={"po":0,"wf":0,"cat":0}, str(cleared))
    ck("every bulk-entry Load surface renders an associated Clear button",
       'poClear()' in html and 'nieWorkforceClear()' in html and 'nieCatClear()' in html
       and html.count('>Clear</button>')>=3)
    ck("opening workforce paste UI does not activate/supersede legacy staffing",
       'onclick="cfg.assumptions.nie_detail._wfPasteOpen=true;renderContent();return false"' in html
       and 'onclick="var w=_ensureWorkforce();w._pasteOpen=true' not in html)
    ck("workforce activation results are surfaced in the operating-expense UI",
       "Workforce activation tracking · latest run" in html and "resolved_hire_periods" in html
       and "End-horizon active count" in html)
    ck("fee GUT proportional trajectory uses shared growth controls without altering other axes",
       'growthSpecInline(sb+".driver.params.growth_spec"' in html
       and 'Trajectory (how the driver moves)' in html and 'Rate behavior' in html and 'Cost side' in html)
    ck("fee cost UI separates revenue share from operating-cost % and uses percent-entry semantics",
       '["pct_of_revenue","Revenue share (% of revenue)"]' in html
       and '["pct_of_revenue_opex","Operating cost (% of revenue)"]' in html
       and 'Operating cost (% of gross fee revenue)' in html
       and '.cost.params.pct=_pf(this.value)/100' in html
       and 'Noninterest Expense: Fee Product Costs' in html)
    ck("Income Statement surfaces Fee Product Costs inside the explicit NIE breakout",
       "rowIS('Fee product operating costs', fin.is.feeOpex" in html
       and "rowIS('Workforce compensation', fin.is.workforceComp" in html
       and "rowIS('Other operating expense', fin.is.otherOpex" in html
       and "rowIS('Depreciation expense', fin.is.depreciationExpense" in html
       and "rowIS('Noninterest Expense: Corporate Overhead'" not in html)
    ck("manual managed AUC exposes only compact Ramp / Growth / Flat trajectory choices",
       'AUC trajectory' in html and '[["ramp_to_target","Ramp to target"],["proportional","Growth"],["flat","Flat"]]' in html
       and 'AUC growth</label>${growthSpecInline(mnb+".growth_spec"' in html)
    # Execute the actual fee-product field renderer. A prior regression kept valid
    # JavaScript syntax but threw at render time because SEL was used before initialization.
    fa=html.index("function fieldsFor("); fb=html.index("function lineOptionsFor",fa)
    fjs=html[fa:fb]
    fp=("const cfg={assumptions:{obs_exposures:[],cac_feeds:{}}};\n"
        "function esc(x){return String(x==null?'':x);}\n"
        "function PLAB(){return 'Mth';}\n"
        "function numInput(){return '<input>'; }\n"
        "function growthSpecInline(){return '<growth>'; }\n"
        "function _qGrowthToPeriod(x){return x||0;}\n"
        "function _feeBasisTileHtml(){return '<tile>'; }\n"
        + fjs +
        "\nconst p={name:'Trust',_fee_product:true,managed_notional:{day1:100,target:200,ramp_periods:8,trajectory:'ramp_to_target'},fee_streams:[]};"
        "\ncfg.assumptions.obs_exposures=[p];"
        "\nconst out=fieldsFor('obs',p,'assumptions.obs_exposures.0');"
        "\nconsole.log(JSON.stringify({ok:out.includes('AUC trajectory') && out.includes('Ramp to target')}));")
    fr=subprocess.run(["node","-e",fp],text=True,capture_output=True)
    fj={}
    if fr.returncode==0 and fr.stdout.strip():
        try: fj=json.loads(fr.stdout.strip().splitlines()[-1])
        except Exception: pass
    ck("Product tab renders a manual-AUC fee product without a runtime initialization error",
       fr.returncode==0 and fj.get("ok") is True, fr.stderr.strip())
    # Natural-period Fee Product authoring: render the actual transaction/account/flat paths.
    ha=html.index("function _feeCoeffScheduleText("); hb=html.index("function fieldsFor(",ha)
    hjs=html[ha:hb]
    fp2=("const cfg={assumptions:{obs_exposures:[],cac_feeds:{}}};\n"
         "function esc(x){return String(x==null?'':x);} function PLAB(k){return k==='full'?'month':'Mth';} function PPY(){return 12;}\n"
         "function numInput(){return '<input>'; } function growthSpecInline(){return '<growth>'; } function _qGrowthToPeriod(x){return x||0;} function _pf(x){return +(String(x).replace(/,/g,''))||0;}\n"
         + hjs + fjs +
         "\nconst p={name:'Custody',_fee_product:true,managed_notional:{day1:120000000,trajectory:'flat'},fee_streams:["
         "{name:'Settlement',basis:'transaction',driver:{source:'managed_notional',trajectory:'derived',params:{coefficient:{kind:'multiple',value:4,period:'year',trajectory:'explicit_schedule',schedule:{'1':1.5,'2':2.4}}}},rate:{behavior:'flat',params:{per_unit:.0005}},cost:{kind:'none',params:{}}},"
         "{name:'Retainer',basis:'account',driver:{source:'constant',trajectory:'flat',params:{base:10}},rate:{behavior:'flat',params:{unit_fee:{value:12000,period:'year'}}},cost:{kind:'none',params:{}}},"
         "{name:'Escrow',basis:'flat',driver:{source:'constant',trajectory:'flat',params:{}},rate:{behavior:'flat',params:{flat_amount:{value:120000,period:'year'}}},cost:{kind:'none',params:{}}}]};"
         "\ncfg.assumptions.obs_exposures=[p]; const out=fieldsFor('obs',p,'assumptions.obs_exposures.0'); console.log(JSON.stringify({ok:out.includes('Flow coefficient')&&out.includes('Fee (% of throughput)')&&out.includes('Fee ($000s/account)')&&out.includes('Amount ($000s)')&&out.includes('Turns schedule by year')}));")
    fr2=subprocess.run(["node","-e",fp2],text=True,capture_output=True)
    fj2={}
    if fr2.returncode==0 and fr2.stdout.strip():
        try: fj2=json.loads(fr2.stdout.strip().splitlines()[-1])
        except Exception: pass
    ck("Product tab renders natural-period flow/account/flat fee controls without runtime error",
       fr2.returncode==0 and fj2.get("ok") is True, fr2.stderr.strip())
    ck("Fee streams use a stronger visual separator for quick stream delineation",
       ".fee-stream-block{border-top:2px solid #3E4B61;margin-top:14px;padding-top:10px}" in html
       and '<div class="fld wide fee-stream-block">' in html
       and 'border-top:1px solid #333;margin-top:8px;padding-top:6px' not in html)
    # Trustee authoring: Account EOP count levels + sourced Balance stock % + Series rate path.
    fp2b=("const cfg={assumptions:{obs_exposures:[],cac_feeds:{Growth:{series_id:'cac:Growth:customers'}}}};\n"
          "function esc(x){return String(x==null?'':x);} function PLAB(k){return k==='full'?'month':'Mth';} function PPY(){return 12;}\n"
          "function numInput(){return '<input>'; } function growthSpecInline(){return '<growth>'; } function _qGrowthToPeriod(x){return x||0;} function _pf(x){return +(String(x).replace(/,/g,''))||0;}\n"
          + hjs + fjs +
          "\nconst p={name:'Trustee',_fee_product:true,managed_notional_source:'Growth',managed_notional_source_id:'cac:Growth:customers',managed_notional:{day1:0,trajectory:'flat'},fee_streams:["
          "{name:'Retainer',basis:'account',driver:{source:'constant',trajectory:'explicit_schedule',params:{level_schedule:{period:'year',resolution:'smooth',schedule:{'1':2,'2':4}}}},rate:{behavior:'flat',params:{unit_fee:{value:200000,period:'year',trajectory:'flat'}}},cost:{kind:'none',params:{}},timing:{start_period:13}},"
          "{name:'Reserve trustee',basis:'balance',driver:{source:'managed_notional',trajectory:'derived',params:{stock_multiplier:{kind:'pct',value:.30,trajectory:'flat'}}},rate:{behavior:'flat',params:{rate_path:{value:.0012,trajectory:'flat'}}},cost:{kind:'none',params:{}},timing:{start_period:13}}]};"
          "\ncfg.assumptions.obs_exposures=[p]; const out=fieldsFor('obs',p,'assumptions.obs_exposures.0'); console.log(JSON.stringify({ok:out.includes('Count path')&&out.includes('Period-end count schedule by year')&&out.includes('Smooth')&&out.includes('Stock % of source')&&out.includes('Stock % trajectory')&&out.includes('Rate path')&&out.includes('Rate (bp/yr on balance)')}));")
    fr2b=subprocess.run(["node","-e",fp2b],text=True,capture_output=True); fj2b={}
    if fr2b.returncode==0 and fr2b.stdout.strip():
        try: fj2b=json.loads(fr2b.stdout.strip().splitlines()[-1])
        except Exception: pass
    ck("Product tab renders trustee Account/Balance authoring without runtime error",
       fr2b.returncode==0 and fj2b.get("ok") is True, fr2b.stderr.strip())
    # Explicit coefficient schedules own the value path; the single-value input must not compete visually.
    fp3=("const cfg={assumptions:{obs_exposures:[],cac_feeds:{}}};\n"
         "function esc(x){return String(x==null?'':x);} function PLAB(k){return k==='full'?'month':'Mth';} function PPY(){return 12;}\n"
         "function numInput(){return '<input>'; } function growthSpecInline(){return '<growth>'; } function _qGrowthToPeriod(x){return x||0;} function _pf(x){return +(String(x).replace(/,/g,''))||0;}\n"
         + hjs + fjs +
         "\nconst p={name:'Conversion',_fee_product:true,managed_notional:{day1:1,trajectory:'flat'},fee_streams:["
         "{name:'Conversion fee',basis:'transaction',driver:{source:'managed_notional',trajectory:'derived',params:{coefficient:{kind:'pct',value:.12,period:'year',trajectory:'explicit_schedule',schedule:{'1':.12,'2':.10}}}},rate:{behavior:'flat',params:{per_unit:.0008}},cost:{kind:'none',params:{}}}]};"
         "\ncfg.assumptions.obs_exposures=[p]; const out=fieldsFor('obs',p,'assumptions.obs_exposures.0'); console.log(JSON.stringify({pctTraj:out.includes('Volume % trajectory'),pctSchedule:out.includes('Volume % schedule by year'),singleHidden:!out.includes('<label>Flow %</label>')}));")
    fr3=subprocess.run(["node","-e",fp3],text=True,capture_output=True); fj3={}
    if fr3.returncode==0 and fr3.stdout.strip():
        try: fj3=json.loads(fr3.stdout.strip().splitlines()[-1])
        except Exception: pass
    ck("explicit transaction schedule hides inactive single Flow % and uses economic labels",
       fr3.returncode==0 and fj3.get("pctTraj") and fj3.get("pctSchedule") and fj3.get("singleHidden"), fr3.stderr.strip())
    ck("Fee Product basis tiles expose circled info affordances for all five stream ontologies",
       'class="fee-basis-info"' in html and 'class="fee-basis-popover"' in html
       and '["balance","transaction","account","flat","event"].forEach(bz=>{ h += _feeBasisTileHtml(bz,_fi); })' in html)
    _fee_help = [
        "Use when revenue is earned as a rate on a balance/notional stock, e.g. custody fee = AUC × annual bps.",
        "Use when revenue depends on throughput/volume, e.g. AUC × settlement turns × settlement fee %, or AUC × conversion % × conversion spread.",
        "Use when revenue is count × fee per account/customer/unit, e.g. 20,000 accounts × $5/month.",
        "Use when revenue is a periodic fixed dollar amount independent of volume, e.g. $150k/year escrow fee.",
        "Use when revenue is a one-time amount occurring in a specific period, e.g. a $500k implementation/setup fee in Month 4.",
    ]
    ck("Fee Product basis info copy preserves the five canonical use-when definitions and examples",
       all(x in html for x in _fee_help))
    # Execute the actual info-toggle helper: one tile opens and an already-open sibling closes.
    ia=html.index("const _FEE_BASIS_HELP="); ib=html.index("function _seriesExplicitValues(",ia)
    ijs=html[ia:ib]
    info_js=(
        "function esc(x){return String(x==null?'':x);}\n" + ijs +
        "function classes(open){return {open:!!open,contains(k){return k==='open'&&this.open;},toggle(k,v){if(k==='open')this.open=!!v;},remove(k){if(k==='open')this.open=false;}};}\n"
        "const p1={classList:classes(false)},p2={classList:classes(true)}; const host={querySelectorAll(){return [p2];}};\n"
        "const tile={parentElement:host,querySelector(){return p1;}}; const btn={parentElement:tile,setAttribute(k,v){this[k]=v;}};\n"
        "_feeBasisInfoToggle('balance',btn); const markup=_feeBasisTileHtml('transaction',3);\n"
        "console.log(JSON.stringify({opened:p1.classList.open,closedSibling:!p2.classList.open,expanded:btn['aria-expanded']==='true',markup:markup.includes('Transaction stream')&&markup.includes('settlement turns')}));")
    ir=subprocess.run(["node","-e",info_js],text=True,capture_output=True); ij={}
    if ir.returncode==0 and ir.stdout.strip():
        try: ij=json.loads(ir.stdout.strip().splitlines()[-1])
        except Exception: pass
    ck("Fee Product basis info click opens its definition and closes an open sibling",
       ir.returncode==0 and ij.get("opened") and ij.get("closedSibling") and ij.get("expanded") and ij.get("markup"), ir.stderr.strip())
    ck("new Fee Product authoring exposes explicit natural periods and cadence-aware timing labels",
       'const _coefNoun=_ckind==="pct"?"Volume %":"Turns"' in html and '${_coefNoun} trajectory' in html and 'Use natural-period flow' in html
       and 'Revenue start (${PLAB' in html and 'Ramp-in (${PLAB' in html)
    ck("Fee Product explicit coefficient path uses live-validating pastebox/load workflow",
       'feeCoeffPaste_' in html and 'comma, tab, semicolon, or new line' in html
       and 'placeholder="e.g. 8, 10, 12, 10, 10, 10, 9"' in html
       and 'oninput="_feeCoeffPasteInput(' in html
       and 'class="pillbtn" disabled onclick="_feeSetCoeffSchedule' in html
       and '_feeClearCoeffSchedule(${_fi},${si})' in html)
    ck("Account/Balance trustee paths expose Flat/Growth/Explicit and Step/Smooth controls",
       'feeAccountLevelPaste_' in html and 'feeStockPctPaste_' in html and 'feeBalanceRatePaste_' in html and 'feeAccountFeePaste_' in html
       and 'Stock % trajectory' in html and 'Count schedule period' in html and 'Foundry does not round interpolated counts' in html)
    ck("Flat fee explicit amount path uses the same live-validating pastebox workflow",
       'feeFlatAmountPaste_' in html
       and 'oninput="_feeFlatAmountPasteInput(' in html
       and 'id="${_fid}_load" class="pillbtn" disabled onclick="_feeSetFlatAmountSchedule' in html
       and '_feeClearFlatAmountSchedule(${_fi},${si})' in html
       and 'function _feeExplicitPasteInput(id)' in html)
    # Execute the exact transaction-coefficient paste workflow that regressed in r33.
    paste_js=(
        "const cfg={assumptions:{obs_exposures:[{fee_streams:[{driver:{params:{coefficient:{kind:'multiple',schedule:{}}}}}]}]}};\n"
        "let rendered=0,refreshed=0; function renderContent(){rendered++;} function refresh(){refreshed++;}\n"
        "const ta={value:'',classList:{toggle(){}}}, btn={disabled:true,classList:{toggle(k,v){this.ready=v;}}};\n"
        "const document={getElementById:(id)=>id.endsWith('_load')?btn:ta};\n"
        + hjs +
        "\nta.value='8,10,12,10,10,10,9'; _feeCoeffPasteInput('feeCoeffPaste_0_0'); const enabled=!btn.disabled && btn.classList.ready===true;"
        " _feeSetCoeffSchedule(0,0,ta.value); const c=cfg.assumptions.obs_exposures[0].fee_streams[0].driver.params.coefficient;"
        " const loaded=Object.values(c.schedule); _feeClearCoeffSchedule(0,0);"
        " console.log(JSON.stringify({enabled,loaded,rendered,refreshed,cleared:Object.keys(c.schedule).length===0,invalid:_feeParseExplicitValues('8,banana,12').length===0}));"
    )
    pr=subprocess.run(["node","-e",paste_js],text=True,capture_output=True)
    pj={}
    if pr.returncode==0 and pr.stdout.strip():
        try: pj=json.loads(pr.stdout.strip().splitlines()[-1])
        except Exception: pass
    ck("transaction coefficient comma paste enables Load and loads exact turns schedule",
       pr.returncode==0 and pj.get("enabled") is True
       and pj.get("loaded")==[8,10,12,10,10,10,9]
       and pj.get("rendered")==2 and pj.get("refreshed")==2
       and pj.get("cleared") is True and pj.get("invalid") is True, pr.stderr.strip())
    # Regression: use Settlement then Escrow pasteboxes sequentially in the same Fee Product.
    dual_paste_js=(
        "const cfg={assumptions:{obs_exposures:[{fee_streams:["
        "{driver:{params:{coefficient:{kind:'multiple',schedule:{}}}}},"
        "{rate:{behavior:'flat',params:{flat_amount:{value:150000,period:'year',trajectory:'explicit_schedule',schedule:{}}}}}"
        "]}]}};\n"
        "let rendered=0,refreshed=0; function renderContent(){rendered++;} function refresh(){refreshed++;} function PPY(){return 12;}\n"
        "const els={}; function mk(id){const b={disabled:true,classList:{ready:false,toggle(k,v){this.ready=v;}}}; const t={value:'',classList:{toggle(){}}}; els[id]=t; els[id+'_load']=b; return [t,b];}\n"
        "const [settle,settleBtn]=mk('feeCoeffPaste_0_0'); const [escrow,escrowBtn]=mk('feeFlatAmountPaste_0_1'); const document={getElementById:(id)=>els[id]||null};\n"
        "function _pf(x){return +(String(x).replace(/,/g,''))||0;}\n"
        + hjs +
        "\nsettle.value='8,10,12,10,10,10,9'; _feeCoeffPasteInput('feeCoeffPaste_0_0'); const settleEnabled=!settleBtn.disabled && settleBtn.classList.ready===true; _feeSetCoeffSchedule(0,0,settle.value);"
        " escrow.value='150,200,250,300,350,400,450'; _feeFlatAmountPasteInput('feeFlatAmountPaste_0_1'); const escrowEnabled=!escrowBtn.disabled && escrowBtn.classList.ready===true; _feeSetFlatAmountSchedule(0,1,escrow.value);"
        " const turns=Object.values(cfg.assumptions.obs_exposures[0].fee_streams[0].driver.params.coefficient.schedule); const amounts=Object.values(cfg.assumptions.obs_exposures[0].fee_streams[1].rate.params.flat_amount.schedule);"
        " console.log(JSON.stringify({settleEnabled,escrowEnabled,turns,amounts,rendered,refreshed,independent:settleBtn!==escrowBtn}));"
    )
    dpr=subprocess.run(["node","-e",dual_paste_js],text=True,capture_output=True)
    dpj={}
    if dpr.returncode==0 and dpr.stdout.strip():
        try: dpj=json.loads(dpr.stdout.strip().splitlines()[-1])
        except Exception: pass
    ck("Settlement then Escrow explicit pasteboxes activate and load independently",
       dpr.returncode==0 and dpj.get("settleEnabled") is True and dpj.get("escrowEnabled") is True
       and dpj.get("turns")==[8,10,12,10,10,10,9]
       and dpj.get("amounts")==[150000,200000,250000,300000,350000,400000,450000]
       and dpj.get("rendered")==2 and dpj.get("refreshed")==2 and dpj.get("independent") is True, dpr.stderr.strip())
    ck("operating-expense paste retains separate batch defaults and manual-add workflow",
       '⎘ Paste categories' in html and '+ Add category' in html and '_catPasteGrowthSpec' in html)
    ck("Operating Expense presents mutually exclusive Simple/Detailed authoring modes and three detailed panels",
       'Simple overhead</button>' in html and '>Detailed</button>' in html
       and 'Workforce compensation' in html and 'Operating expense categories' in html
       and 'Assessments &amp; other NIE' in html and 'class="nie-section"' in html)
    ck("workforce UI makes default inheritance explicit and removes implementation-language load override",
       'Roles inherit the workforce defaults unless a row explicitly overrides them.' in html
       and 'Benefits / Payroll</span>' in html and 'load override' not in html)
    ck("workforce UI gives concise economic-aggregation guidance",
       '<b>User note.</b> Aggregate roles until timing, escalation, benefits/payroll, or triggers differ.' in html
       and 'This keeps large staffing plans compact without losing model fidelity.' not in html)
    ck("assessment defaults are visible economic values rather than blank placeholders",
       'fdic_bp_ann:5.0' in html and 'occ_bp_ann:1.5' in html
       and 'blank=5.0' not in html and 'blank=1.5' not in html)
    ck("workforce paste guidance describes clipboard columns and restores optional Count",
       'you do not need to type tab characters' in html and 'Tabs preferred' not in html
       and 'Annual Comp<br>($000s/FTE)' in html and '<span>Count</span>' in html)
    ck("workforce main row stays compact while advanced Count/Compensation paths remain available",
       '<span class="wf-field-label">Count</span>' in html
       and '<span class="wf-field-label">Annual Comp</span>' in html
       and '<span class="wf-field-label">Escalation</span>' in html
       and 'Legacy escalation' not in html and '>↗</option>' not in html and '>⋯</option>' not in html
       and 'Advanced trajectories' in html and 'Count path' in html and 'Compensation path' in html
       and 'nieWorkforceCountMode' in html and 'nieWorkforceCompMode' in html and 'nieWorkforceCompLegacy' in html
       and 'Count schedule' in html and 'One row = one economically homogeneous population' in html
       and '$000s/FTE/year' in html and 'nieWorkforceCompValue' in html and 'Compensation trajectory' in html)
    ck("Series Explicit authoring uses pasteboxes instead of period-by-period typing",
       'nieWorkforceCountPaste' in html and 'nieWorkforceCompPaste' in html
       and 'nieCatSchedulePaste' in html and 'Load (replace)' in html
       and 'Paste Count values from a row or column' in html and 'Paste Compensation values' in html)
    ck("Hold/Interpolate appears only where coarse source levels need native-cadence resolution",
       'Between source points' in html and '>Hold</option>' in html and '>Interpolate</option>' in html
       and '_seriesResolutionUseful(_cad)' in html)
    ck("every Load companion manual amount field uses the same $000s-to-raw-dollar conversion",
       'cfg.pre_opening.expenses[${i}].total=_pf(this.value)*1000' in html
       and 'cfg.assumptions.fixed_assets.assets[${i}].cost=_pf(this.value)*1000' in html
       and '${_cb}.per_period=_pf(this.value)*1000' in html
       and 'nieWorkforceCompValue(${wi},this.value)' in html)
    ck("trigger editor is metric + comparator + value with source/timing folded into metric semantics",
       'Managed-notional source product' not in html and 'Fixed value</option>' not in html
       and 'same period</option>' not in html and 'net_income_py' in html and 'mn::' in html)
    ck("payroll burden wording explains that the percentage is additive to base compensation",
       'Benefits &amp; payroll default' in html and 'Added on top of base compensation' in html)
    ck("pre-opening expenses are not given growth semantics",
       'pre_opening.growth_spec' not in html and 'poPaste' in html)
    ga=html.index("function setGrowthField("); gb=html.index("function EVENTVAL",ga)
    gjs=html[ga:gb]
    gp=("let cfg={assumptions:{x:null}}; function PPY(){return 12;} "
        "function getPath(p){return p.split('.').reduce((o,k)=>o==null?o:o[k],cfg);}"
        "function setPath(p,v){let ks=p.split('.'),o=cfg;for(let i=0;i<ks.length-1;i++){if(o[ks[i]]==null)o[ks[i]]={};o=o[ks[i]];}o[ks[ks.length-1]]=v;}\n"
        + gjs + "\nsetGrowthField('assumptions.x','period','year',0.03); console.log(JSON.stringify(cfg.assumptions.x));")
    gr=subprocess.run(["node","-e",gp],text=True,capture_output=True)
    gj=json.loads(gr.stdout.strip()) if gr.returncode==0 and gr.stdout.strip() else {}
    ck("legacy first-edit preserves the visible rate while materializing new growth semantics",
       abs(gj.get("rate",0)-.03)<1e-12 and gj.get("period")=="year"
       and gj.get("method")=="smooth" and gj.get("anchor")=="model_year", gr.stderr.strip())
    ck("quarterly fiscal-year authoring disables non-quarter boundary months",
       "PPY()===4 && ![1,4,7,10].includes(n)" in html and "dis?' disabled':''" in html)

    print(f"\n{p} passed, {f} failed")
    return 0 if f==0 else 1

if __name__ == "__main__":
    sys.exit(main())
