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
    a=html.index("function _newNieDetail()")
    b=html.index("// Risk-based capital ratios", a)
    js=html[a:b]
    roles="\n".join(
        f"Role {i+1}\t{60000+i*1000}\tM{1+(i*7)%57}\t{2+(i%4)}" for i in range(48)
    )
    prefix=r'''
const window=globalThis;
let cfg={assumptions:{}};
function renderContent(){} function refresh(){} function appStatus(){}
function _pf(x){ let n=parseFloat(String(x).replace(/[^0-9.\-]/g,'')); return isNaN(n)?0:n; }
'''
    suffix=f'''
cfg.assumptions.nie_detail=_newNieDetail();
const fresh=JSON.parse(JSON.stringify(cfg.assumptions.nie_detail));
window.nieCatPaste("Occupancy\\t30","growth",3,"year","step","model_year",1);
const cat=JSON.parse(JSON.stringify(cfg.assumptions.nie_detail.categories[0]));
window.nieWorkforcePaste({json.dumps(roles)});
const wf=cfg.assumptions.nie_detail.workforce;
console.log(JSON.stringify({{fresh,cat,nroles:wf.roles.length,maxhire:Math.max(...wf.roles.map(r=>r.hire_period))}}));
'''
    br=subprocess.run(["node","-e",prefix+js+suffix],text=True,capture_output=True)
    bj={}
    if br.returncode==0 and br.stdout.strip():
        try: bj=json.loads(br.stdout.strip().splitlines()[-1])
        except Exception: pass
    ck("new NIE activation has zero categories and role-mode workforce, not FTE Y1/Y2/Y3",
       br.returncode==0 and bj.get("fresh",{}).get("categories")==[]
       and "fte_by_year" not in bj.get("fresh",{})
       and bj.get("fresh",{}).get("workforce",{}).get("mode")=="roles"
       and "window.nieOn = function(){ cfg.assumptions.nie_detail = _newNieDetail();" in html, br.stderr.strip())
    gs=(bj.get("cat") or {}).get("growth_spec") or {}
    ck("category batch paste writes canonical 3%/year/step growth semantics",
       (bj.get("cat") or {}).get("trajectory")=="growth" and abs(gs.get("rate",0)-.03)<1e-12
       and gs.get("period")=="year" and gs.get("method")=="step")
    ck("one workforce paste compactly consumes 48 heterogeneous rows including M57",
       bj.get("nroles")==48 and bj.get("maxhire")==57)
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
       '⎘ Paste categories' in html and '+ Add one manually' in html and '_catPasteGrowthSpec' in html)
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
