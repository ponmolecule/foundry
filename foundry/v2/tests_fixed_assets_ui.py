"""Browser authoring regression gate for Fixed assets / CAPEX."""
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
    a=html.index("function _fixedAssetState()")
    b=html.index("window.nieCatClear",a)
    js=html[a:b]
    prefix=r'''
const window=globalThis;
let cfg={assumptions:{periods_per_year:12,n_periods:84},pre_opening:{expenses:[]}};
window.confirm=()=>true;
function renderContent(){} function refresh(){}
let msgs=[]; function appStatus(k,m){msgs.push([k,m]);}
function NP(){return 84;} function PPY(){return 12;} function PLAB(){return 'M';} function _nativeFlowPeriod(){return 'month';}
function _pf(x){let n=parseFloat(String(x).replace(/[^0-9.\-]/g,''));return isNaN(n)?0:n;}
function _clearLoaded(kind,n,fn){fn();return true;}
function getPath(path){let o=cfg; for(const k of String(path).split('.')){if(o==null)return null;o=o[k];}return o;}
function setPath(path,v){let o=cfg,ks=String(path).split('.');for(let i=0;i<ks.length-1;i++){o[ks[i]]=o[ks[i]]||{};o=o[ks[i]];}o[ks[ks.length-1]]=v;}
function _seriesSourcePeriods(){return 84;} function _resizeSeriesValues(){} function _seriesExplicitValues(){return [];} function _seriesPasteSummary(){return '';} function _seriesResolutionUseful(){return false;} function _seriesCadenceOptions(){return ['month'];} function growthSpecInline(){return '';} function fmtComma(x){return String(x);} function esc(x){return String(x);} function _explicitPreviewHtml(){return '';} function fmtField(){} function _seriesId(){return 'sid';} function _ensureLinkableSeriesIds(){} function _opexLinkedDriverOptions(){return [{value:'workforce_count::wf-total-ui',driver:'workforce_count',series_id:'wf-total-ui',label:'Workforce headcount · Total workforce'}];}
'''
    suffix=r'''
cfg.assumptions.premises_equipment=1200000; cfg.assumptions.premises_depreciation_annual=120000;
faSetMode("formula_level");
const fl=JSON.parse(JSON.stringify(cfg.assumptions.fixed_assets.formula_level));
faFormulaAddComponent();
const linked=JSON.parse(JSON.stringify(cfg.assumptions.fixed_assets.formula_level.components));
faPaste("Asset\tCost\tIn Service\tUseful Life\nFurniture\t350\tAt opening\t7\nServers\t250\tM18\t5", "replace");
const rows=JSON.parse(JSON.stringify(cfg.assumptions.fixed_assets.assets));
faClear();
console.log(JSON.stringify({rows,mode:cfg.assumptions.fixed_assets.mode,n:cfg.assumptions.fixed_assets.assets.length,msgs,fl,linked}));
'''
    r=subprocess.run(["node","-e",prefix+js+suffix],text=True,capture_output=True)
    out={}
    if r.returncode==0 and r.stdout.strip():
        try: out=json.loads(r.stdout.strip().splitlines()[-1])
        except Exception: pass
    rows=out.get("rows") or []
    ck("asset paste resolves opening and later placed-in-service periods",
       len(rows)==2 and rows[0].get("in_service_period")==0 and rows[1].get("in_service_period")==18,
       r.stderr.strip())
    ck("asset paste converts $000s costs to raw dollars",
       len(rows)==2 and rows[0].get("cost")==350000 and rows[1].get("cost")==250000)
    ck("asset paste supplies straight-line default and useful lives",
       len(rows)==2 and rows[0].get("method")=="straight_line" and rows[0].get("useful_life_years")==7
       and rows[1].get("useful_life_years")==5)
    ck("fixed-asset clear independently empties the loaded schedule",
       out.get("mode")=="schedule" and out.get("n")==0)
    fl=out.get("fl") or {}
    ck("legacy Simple conversion preserves the historical monthly level/depreciation path",
       fl.get("level_basis")=="net" and fl.get("opening_level")==1200000 and (fl.get("base_spec") or {}).get("trajectory")=="explicit"
       and abs(((fl.get("base_spec") or {}).get("values") or [0])[0]-1190000)<1e-9
       and abs((((fl.get("depreciation") or {}).get("amount_spec") or {}).get("values") or [0])[0]-10000)<1e-9)
    ck("fixed-asset editor exposes Formula / level versus Asset schedule without a third methodology",
       'Fixed assets / CAPEX' in html and '>Formula / level</button>' in html and '>Asset schedule</button>' in html
       and 'Use generalized Formula / level' in html)
    ck("Formula / level UI exposes explicit gross/net basis, linked components and depreciation",
       'Level basis' in html and 'Gross PP&amp;E' in html and 'Net PP&amp;E target' in html
       and '+ Add linked component' in html and 'Driver Series' in html and 'Multiplier' in html
       and '% of asset level' in html and 'Entered amount' in html
       and 'Opening accumulated depreciation' in html)
    linked=out.get("linked") or []
    ck("Formula / level Add linked component stores a stable Workforce Count Series link",
       len(linked)==1 and (linked[0].get("driver_spec") or {}).get("source")=="link"
       and (((linked[0].get("driver_spec") or {}).get("link") or {}).get("series_id"))=="wf-total-ui"
       and (linked[0].get("multiplier_spec") or {}).get("trajectory")=="flat")
    ck("new fixed-asset component gets an economic driver-derived name, not an implementation placeholder",
       len(linked)==1 and linked[0].get("name")=="Fixed assets · Total workforce"
       and 'name:"Linked asset component"' not in html)
    print(f"\n{p} passed, {f} failed")
    return 0 if f==0 else 1

if __name__=="__main__": sys.exit(main())
