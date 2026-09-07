"""Browser authoring regression gate for the generic Customer Acquisition annual schedule UI."""
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
    a=html.index("var CAC_METHODS =")
    b=html.index("function _operatingExpenseMode", a)
    js=html[a:b]
    prefix=r'''
const window=globalThis;
let cfg={assumptions:{periods_per_year:12,n_periods:84,obs_exposures:[],cac_feeds:{growth:{
  channels:[
    {name:'Affiliate',method:'pool_conversion',params:{pool:1000,conversion_rate:.02},avg_auc_per_customer:500000},
    {name:'Direct / BD',method:'spend_cac',params:{spend:1000000,cac:1000},avg_auc_per_customer:250000}
  ], attrition_rate:.03, beginning_auc:0, beginning_customers:0, intra_year_shape:'linear'
}}}};
function NP(){return cfg.assumptions.n_periods;} function PPY(){return cfg.assumptions.periods_per_year;}
function renderContent(){} function refresh(){} function _pf(x){let n=parseFloat(String(x).replace(/[^0-9.\-]/g,''));return isNaN(n)?0:n;}
window.confirm=()=>true;
'''
    suffix=r'''
window.cacUseAnnual('growth');
const fd=cfg.assumptions.cac_feeds.growth;
const seeded={mode:fd.authoring_mode,years:fd.driver_specs.attrition_rate.values.length,
  ch0:Object.keys(fd.channels[0].driver_specs).sort(),ch1:Object.keys(fd.channels[1].driver_specs).sort(),
  pool:fd.channels[0].driver_specs.pool.values.slice(),spend:fd.channels[1].driver_specs.spend.values.slice()};
window.cacSetAnnual('growth',1,'spend',1,'2,500','k');
window.cacSetAnnual('growth',0,'conversion_rate',2,'4.5','pct');
window.cacSetAttrAnnual('growth',3,'6');
window.cacMethodChange('growth',0,'fte_productivity');
const edited={spend:fd.channels[1].driver_specs.spend.values[1],conv:fd.channels[0].driver_specs.conversion_rate.values[2],
  attr:fd.driver_specs.attrition_rate.values[3],method:fd.channels[0].method,
  methodKeys:Object.keys(fd.channels[0].driver_specs).sort()};
console.log(JSON.stringify({seeded,edited}));
'''
    br=subprocess.run(["node","-e",prefix+js+suffix],text=True,capture_output=True)
    bj={}
    if br.returncode==0 and br.stdout.strip():
        try: bj=json.loads(br.stdout.strip().splitlines()[-1])
        except Exception: pass
    sd=bj.get("seeded") or {}; ed=bj.get("edited") or {}
    ck("annual authoring seeds the full configured seven-year horizon",
       br.returncode==0 and sd.get("mode")=="annual_schedule" and sd.get("years")==7, br.stderr.strip())
    ck("annual schedule is method-driven, not hard-coded to Affiliate/Direct names",
       sd.get("ch0")==["avg_auc_per_customer","conversion_rate","pool"]
       and sd.get("ch1")==["avg_auc_per_customer","cac","spend"])
    ck("annual seed preserves Year-1 simple values instead of resetting economics",
       sd.get("pool",[None])[0]==1000 and sd.get("spend",[None])[0]==1000000)
    ck("annual $000s entry converts to raw dollars exactly once",
       abs((ed.get("spend") or 0)-2_500_000)<1e-9)
    ck("annual percentage entry converts percent to decimal exactly once",
       abs((ed.get("conv") or 0)-.045)<1e-12 and abs((ed.get("attr") or 0)-.06)<1e-12)
    ck("switching acquisition method seeds the new generic method drivers",
       ed.get("method")=="fte_productivity" and all(k in ed.get("methodKeys",[]) for k in ["ftes","per_fte","comp_per_fte","avg_auc_per_customer"]))

    ck("Customer Acquisition UI explains N-channel/shapeshifter semantics",
       "Channels are user-named. Foundry only knows acquisition methods" in html
       and "+ acquisition channel" in html)
    ck("Customer Acquisition UI exposes annual source schedule and within-year resolution",
       "Use annual source schedule" in html and "Annual source driver" in html
       and "Within-year resolution" in html and "Smooth ramp" in html)
    ck("annual schedule columns derive from model horizon instead of a hard-coded seven years",
       "for(let y=1;y<=CACYEARS();y++)" in html and "function CACYEARS(){ return Math.max(1,Math.ceil(NP()/PPY())); }" in html)
    ck("feed exposes beginning customers and beginning AUC rather than assuming a zero-start engagement",
       "Beginning customers" in html and "Beginning AUC" in html)

    print(f"\n{p} passed, {f} failed")
    return 0 if f==0 else 1

if __name__ == "__main__":
    sys.exit(main())
