"""Browser authoring regression gate for generalized Other liabilities."""
from __future__ import annotations
import json, subprocess, sys
from pathlib import Path


def main():
    p=f=0
    def ck(name, cond, detail=""):
        nonlocal p,f
        if cond: p+=1; print("  PASS ", name + (f" — {detail}" if detail else ""))
        else: f+=1; print("  FAIL ", name + (f" — {detail}" if detail else ""))

    html=Path("web/console_v2.html").read_text(encoding="utf-8")
    a=html.index("function _olState(create)")
    b=html.index("window.faAdd=function()",a)
    js=html[a:b]
    prefix=r'''
const window=globalThis;
let cfg={assumptions:{other_liabilities:250000,nie_detail:{workforce:{total_count_series_id:'wf-total-ui',roles:[{series_id:'wf-role-ui',role:'Ops'}]}}}};
function renderContent(){} function refresh(){} function _pf(x){let n=parseFloat(String(x).replace(/[^0-9.\-]/g,''));return isNaN(n)?0:n;}
function _ensureLinkableSeriesIds(){} function _seriesId(){return 'ol-ui-id';}
'''
    suffix=r'''
const before=JSON.stringify(cfg.assumptions);
olEnable();
const enabled=JSON.parse(JSON.stringify(cfg.assumptions.other_liabilities_model));
olAddComponent();
const afterAdd=JSON.parse(JSON.stringify(cfg.assumptions.other_liabilities_model));
olDriver(0,'fixed_asset_net');
const afterFA=JSON.parse(JSON.stringify(cfg.assumptions.other_liabilities_model));
console.log(JSON.stringify({before,enabled,afterAdd,afterFA}));
'''
    r=subprocess.run(["node","-e",prefix+js+suffix],text=True,capture_output=True)
    out={}
    if r.returncode==0 and r.stdout.strip():
        try: out=json.loads(r.stdout.strip().splitlines()[-1])
        except Exception: pass
    en=out.get("enabled") or {}
    ck("enabling Formula / level preserves the legacy flat balance as opening and base",
       en.get("opening_balance")==250000 and (en.get("base_spec") or {}).get("value")==250000,
       r.stderr.strip())
    aa=(out.get("afterAdd") or {}).get("components") or []
    ck("new liability component defaults to stable Total Workforce Count when available",
       len(aa)==1 and (aa[0].get("driver") or {}).get("kind")=="workforce_count"
       and (aa[0].get("driver") or {}).get("series_id")=="wf-total-ui")
    af=(out.get("afterFA") or {}).get("components") or []
    ck("liability component can switch generically to net fixed assets",
       len(af)==1 and (af[0].get("driver") or {}).get("kind")=="fixed_asset_net")
    ck("UI exposes Formula / level Other liabilities in the existing funding/balance-sheet area",
       'Funding waterfall &amp; other balance sheet' in html and 'Use Formula / level' in html
       and '+ Add linked liability component' in html and 'Liability per FTE' in html)
    ck("Balance Sheet renders named liability component detail when Formula / level is active",
       "r.other_liabilities||null" in html and "'&nbsp;&nbsp;'+esc(_c.name" in html)
    print(f"\n{p} passed, {f} failed")
    return 0 if f==0 else 1

if __name__=="__main__": sys.exit(main())
