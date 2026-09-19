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
let _idn=0;
let cfg={assumptions:{other_liabilities:250000,
  nie_detail:{workforce:{total_count_series_id:'wf-total-ui',roles:[{series_id:'wf-role-ui',role:'Ops'}]}},
  fixed_assets:{mode:'formula_level',formula_level:{base_name:'Fixed Asset ROU',base_spec:{source:'entered',trajectory:'flat',value:120000},components:[{component_id:'fa-ui-fte',name:'Workforce-linked fixed assets'}]}}
}};
function renderContent(){} function refresh(){} function _pf(x){let n=parseFloat(String(x).replace(/[^0-9.\-]/g,''));return isNaN(n)?0:n;}
function _ensureLinkableSeriesIds(){} function _seriesId(prefix){_idn++;return String(prefix||'id')+'-'+_idn;}
'''
    suffix=r'''
const before=JSON.stringify(cfg.assumptions);
olEnable();
const enabled=JSON.parse(JSON.stringify(cfg.assumptions.other_liabilities_model));
olAddComponent();
const afterAdd=JSON.parse(JSON.stringify(cfg.assumptions.other_liabilities_model));
olDriver(0,0,'fixed_asset_level::bank.fixed_assets.formula_level.base');
olAddTerm(0);
olDriver(0,1,'fixed_asset_level::bank.fixed_assets.accumulated_depreciation');
const afterFA=JSON.parse(JSON.stringify(cfg.assumptions.other_liabilities_model));
console.log(JSON.stringify({before,enabled,afterAdd,afterFA,opts:_olDriverOptions()}));
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
    t0=((aa[0].get("terms") or [{}])[0] if aa else {})
    l0=((t0.get("driver_spec") or {}).get("link") or {})
    ck("new liability component defaults to stable Total Workforce Count when available",
       len(aa)==1 and l0.get("kind")=="workforce_role_count" and l0.get("series_id")=="wf-total-ui")
    af=(out.get("afterFA") or {}).get("components") or []
    terms=(af[0].get("terms") or []) if af else []
    links=[((t.get("driver_spec") or {}).get("link") or {}) for t in terms]
    ck("liability component supports additive Fixed Asset formula terms",
       len(links)==2
       and links[0].get("series_id")=="bank.fixed_assets.formula_level.base"
       and links[1].get("series_id")=="bank.fixed_assets.accumulated_depreciation")
    opts=out.get("opts") or []
    labels={x.get("label") for x in opts}
    ck("Fixed Asset base, named components, accumulated depreciation and totals are linkable",
       "Fixed assets · Fixed Asset ROU" in labels
       and "Fixed assets · Workforce-linked fixed assets" in labels
       and "Fixed assets · Accumulated depreciation" in labels
       and "Fixed assets · Net total" in labels)
    ck("UI exposes additive liability Formula / level in the existing funding/balance-sheet area",
       'Funding waterfall &amp; other balance sheet' in html and 'Use Formula / level' in html
       and '+ Add liability component' in html and '+ Add formula term' in html
       and 'Signed multipliers are allowed' in html)
    ck("Balance Sheet renders named liability detail and multi-term contributions",
       "r.other_liabilities||null" in html and "_terms.length>1" in html and "↳ " in html)
    ck("Balance Sheet renders Formula / level fixed-asset components for reconciliation",
       "_fl.base_name||'Base asset level'" in html and "_fl.components" in html)
    print(f"\n{p} passed, {f} failed")
    return 0 if f==0 else 1

if __name__=="__main__": sys.exit(main())
