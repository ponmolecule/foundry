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
        f"Role {i+1}\t{60000+i*1000}\tM{1+(i*7)%57}\t{2+(i%4)}" for i in range(48)
    )
    prefix=r'''
const window=globalThis;
let cfg={assumptions:{obs_exposures:[{name:'Custody',managed_notional:{day1:1}},{name:'Wealth',managed_notional:{day1:1}}]},pre_opening:{expenses:[]}};
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
window.nieWorkforcePaste("Custody Ops\t120000\tEOP AUC [Custody] >= 1B\t3.5");
const trigger=JSON.parse(JSON.stringify(wf.roles[wf.roles.length-1].activation));
window.nieWorkforcePaste("Controller, $95,000, M36, 4.0");
const csv=JSON.parse(JSON.stringify(wf.roles[wf.roles.length-1]));
window.nieWorkforcePaste("Role\tCount\tAnnual Comp ($000s/FTE)\tStart\tEnd\tEscalation %\tPayroll Load %\nTreasurer\t2\t130\tM8\tM36\t\t27.5");
const hdr=JSON.parse(JSON.stringify(wf.roles[wf.roles.length-1]));
window.nieWorkforcePaste("Role\tAnnual Comp ($/FTE)\tStart\tEnd\tEscalation %\tBenefits/Payroll %\nTreasurer 2\t145000\tM9\tM40\t3.5\t24");
const canon=JSON.parse(JSON.stringify(wf.roles[wf.roles.length-1]));
window.nieWorkforcePaste("Role\tAnnualSalary\tHireMonth\tAnnualEscalation\nCFO\t300,000\t12\t4.0");
const compactHdr=JSON.parse(JSON.stringify(wf.roles[wf.roles.length-1]));
// Unit-parity audit: every bulk paste stores the same raw value as its manual field path.
cfg.pre_opening.expenses=[]; window.poPaste("Legal\t300","replace"); const poAmt=cfg.pre_opening.expenses[0].total;
window.faPaste("Asset\tCost\tInService\tUsefulLife\nServers\t300\tAt opening\t5","replace"); const faAmt=cfg.assumptions.fixed_assets.assets[0].cost;
const ndParity=_ensureNieDetail(); ndParity.categories=[]; window.nieCatPaste("Insurance\t300","flat",0,"month","smooth","model_period",1); const catAmt=ndParity.categories[0].per_period;
window.nieWorkforcePaste("Role\tAnnual Comp ($/FTE)\tStart\tEscalation %\nParity Role\t300000\tM1\t3"); const wfAmt=wf.roles[wf.roles.length-1].annual_comp;
window.nieWorkforceMetric(wf.roles.length-1,"mn::Wealth"); const mnMetric=JSON.parse(JSON.stringify(wf.roles[wf.roles.length-1].activation));
window.nieWorkforceMetric(wf.roles.length-1,"net_income_py"); const pyMetric=JSON.parse(JSON.stringify(wf.roles[wf.roles.length-1].activation));
cfg.assumptions.nie_detail.categories=[{name:'Saved detail',per_period:1}];
window.nieOff(); const simpleHasDraft=!!cfg.assumptions._nie_detail_draft && cfg.assumptions.nie_detail===null;
window.nieOn(); const restored=(cfg.assumptions.nie_detail.categories||[])[0].name;
cfg.pre_opening.expenses=[{category:'Legal',total:1000}];
window.poClear(); window.nieWorkforceClear(); window.nieCatClear();
console.log(JSON.stringify({fresh,cat,nroles,maxhire,trigger,csv,hdr,canon,compactHdr,unitParity:{poAmt,faAmt,catAmt,wfAmt},mnMetric,pyMetric,simpleHasDraft,restored,cleared:{po:cfg.pre_opening.expenses.length,wf:wf.roles.length,cat:cfg.assumptions.nie_detail.categories.length}}));
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
       trig.get("metric")=="managed_notional_end" and trig.get("source")=="Custody"
       and trig.get("operator")==">=" and abs(trig.get("value",0)-1_000_000_000)<1
       and trig.get("timing")=="same_period")
    csv=bj.get("csv") or {}
    ck("workforce CSV keeps thousands commas inside compensation",
       csv.get("role")=="Controller" and abs(csv.get("annual_comp",0)-95000)<1e-9 and csv.get("hire_period")==36)
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
       compact.get("role")=="CFO" and abs(compact.get("annual_comp",0)-300000)<1e-9
       and compact.get("hire_period")==12 and abs((compact.get("salary_growth_spec") or {}).get("rate",0)-.04)<1e-12)
    up=bj.get("unitParity") or {}
    ck("paste/manual unit semantics are aligned across every bulk-entry surface",
       up=={"poAmt":300000,"faAmt":300000,"catAmt":300000,"wfAmt":300000}, str(up))
    mn=bj.get("mnMetric") or {}; py=bj.get("pyMetric") or {}
    ck("metric choice folds managed-notional source into the metric and derives safe timing",
       mn.get("metric")=="managed_notional_end" and mn.get("source")=="Wealth" and mn.get("timing")=="same_period"
       and py.get("metric")=="net_income" and py.get("reference")=="prior_year" and py.get("timing")=="next_period")
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
    ck("fee GUT proportional trajectory uses shared growth controls without altering other axes",
       'Driver growth</label>${growthSpecInline(sb+".driver.params.growth_spec"' in html
       and 'Trajectory (how the driver moves)' in html and 'Rate behavior' in html and 'Cost side' in html)
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
    ck("workforce paste guidance describes clipboard columns rather than asking users to type tabs",
       'you do not need to type tab characters' in html and 'Tabs preferred' not in html
       and 'Annual Comp<br>($/FTE)' in html and '<span>Count</span>' not in html)
    ck("manual workforce row treats one row as one position and reclaims Count space for compensation/start",
       '<span class="wf-field-label">Count</span>' not in html
       and 'title="$/FTE per year"' in html and '.annual_comp=_pf(this.value);refresh();fmtField(this)' in html
       and 'max="84" step="1" title="${EVENTUNIT()} number (1–84)"' in html
       and 'max="84" step="1" placeholder="—"' in html)
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
