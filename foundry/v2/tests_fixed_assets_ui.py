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
function NP(){return 84;} function PLAB(){return 'M';}
function _pf(x){let n=parseFloat(String(x).replace(/[^0-9.\-]/g,''));return isNaN(n)?0:n;}
function _clearLoaded(kind,n,fn){fn();return true;}
'''
    suffix=r'''
faPaste("Asset\tCost\tIn Service\tUseful Life\nFurniture\t350\tAt opening\t7\nServers\t250\tM18\t5", "replace");
const rows=JSON.parse(JSON.stringify(cfg.assumptions.fixed_assets.assets));
faClear();
console.log(JSON.stringify({rows,mode:cfg.assumptions.fixed_assets.mode,n:cfg.assumptions.fixed_assets.assets.length,msgs}));
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
    ck("fixed-asset editor is separated from pre-opening expenses and simple mode remains available",
       'Fixed assets / CAPEX' in html and '>Simple</button>' in html and '>Asset schedule</button>' in html)
    print(f"\n{p} passed, {f} failed")
    return 0 if f==0 else 1

if __name__=="__main__": sys.exit(main())
