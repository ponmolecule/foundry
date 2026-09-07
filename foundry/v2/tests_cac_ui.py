"""Browser authoring regression gate for causal Customer Acquisition series dials."""
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
    a=html.index("var CAC_METHODS =")
    b=html.index("function _operatingExpenseMode", a)
    js=html[a:b]
    prefix=r'''
const window=globalThis;
let cfg={assumptions:{periods_per_year:12,n_periods:84,obs_exposures:[],nie_detail:{
  categories:[{series_id:'opex-bd',name:'Business Development',trajectory:'flat',per_period:10000}],
  workforce:{mode:'roles',roles:[{series_id:'wf-rm',role:'Relationship Managers',count:3,annual_comp:175000,hire_period:1}]}
},cac_feeds:{growth:{channels:[
  {name:'Partner referrals',method:'pool_conversion',params:{pool:1000,conversion_rate:.02},avg_auc_per_customer:500000},
  {name:'Relationship-led',method:'spend_cac',params:{spend:1000000,cac:1000},avg_auc_per_customer:250000}
],attrition_rate:.03,beginning_auc:0,beginning_customers:0,intra_year_shape:'linear'}}}};
function NP(){return cfg.assumptions.n_periods;} function PPY(){return cfg.assumptions.periods_per_year;} function MODELYEARS(){return Math.max(1,Math.ceil(NP()/PPY()));}
function _seriesSourcePeriods(cadence){const f={year:1,quarter:4,month:12}[cadence]||PPY();return Math.max(1,Math.ceil(NP()*f/PPY()));}
function _seriesCadenceOptions(){const p=PPY();return p===12?["year","quarter","month"]:(p===4?["year","quarter"]:["year"]);}
function _seriesPeriodLabel(cadence,i){return (cadence==="month"?"M":cadence==="quarter"?"Q":"Y")+(i+1);}
function _resizeSeriesValues(sp,fill){sp.values=sp.values||[];const n=_seriesSourcePeriods(sp.cadence||"year");while(sp.values.length<n)sp.values.push(sp.values.length?sp.values[sp.values.length-1]:fill);if(sp.values.length>n)sp.values=sp.values.slice(0,n);}
function renderContent(){} function refresh(){} function _pf(x){let n=parseFloat(String(x).replace(/[^0-9.\-]/g,''));return isNaN(n)?0:n;}
function fmtComma(x){return String(x)} function esc(x){return String(x)} function _seriesId(p){return p+'-test'}
window.confirm=()=>true;window.alert=()=>{};
'''
    suffix=r'''
const fd=cfg.assumptions.cac_feeds.growth;
// Materialize generic dials without changing channel names/equations.
fd.channels.forEach(ch=>_cacMeta(ch.method).forEach(m=>_cacEnsureSpec(ch,m.k)));
const seeded={m0:Object.keys(fd.channels[0].driver_specs).sort(),m1:Object.keys(fd.channels[1].driver_specs).sort()};
window.cacDriverTrajectory('growth',0,'pool','explicit');
window.cacScheduleValue('growth',0,'pool',1,'2,500','number');
window.cacDriverSource('growth',1,'spend','link');
const spendLink=fd.channels[1].driver_specs.spend;
window.cacMethodChange('growth',0,'fte_productivity');
window.cacDriverSource('growth',0,'ftes','link');
const fteLink=fd.channels[0].driver_specs.ftes;
window.nop=0;
console.log(JSON.stringify({seeded,pool:fd.channels[0].driver_specs.pool,spendLink,fteLink,method:fd.channels[0].method}));
'''
    br=subprocess.run(["node","-e",prefix+js+suffix],text=True,capture_output=True)
    bj={}
    if br.returncode==0 and br.stdout.strip():
        try: bj=json.loads(br.stdout.strip().splitlines()[-1])
        except Exception: pass
    sd=bj.get("seeded") or {}
    ck("driver dials are equation-driven, not hard-coded to channel names",
       br.returncode==0 and sd.get("m0")==["avg_auc_per_customer","conversion_rate","pool"]
       and sd.get("m1")==["avg_auc_per_customer","cac","spend"], br.stderr.strip())
    ck("explicit schedule is local to one primitive and derives horizon dynamically",
       len((bj.get("pool") or {}).get("values") or [])==7)
    sl=(bj.get("spendLink") or {}).get("link") or {}
    ck("Spend can link generically to an Operating Expense series by stable ID",
       sl.get("kind")=="operating_expense_category" and sl.get("series_id")=="opex-bd" and sl.get("aggregation")=="sum")
    fl=(bj.get("fteLink") or {}).get("link") or {}
    ck("FTE productivity can link generically to Workforce Count by stable ID",
       bj.get("method")=="fte_productivity" and fl.get("kind")=="workforce_role_count" and fl.get("series_id")=="wf-rm")

    ck("spreadsheet-style global annual input grid is removed",
       "Use annual source schedule" not in html and "Annual source driver" not in html
       and "Annual source schedule active" not in html)
    ck("CAC authoring explicitly presents per-driver equation-of-motion dials",
       "Each driver owns its own trajectory or links to a Foundry series owned elsewhere" in html
       and "Flat" in html and "Growth" in html and "Explicit" in html and "Link" in html)
    ck("CAC explains causal ownership instead of duplicating budgets/headcount",
       "CAC does not duplicate budgets or headcount assumptions" in html
       and "trajectory owned by source" in html)
    ck("acquisition equations remain the closed vocabulary while channel names are user-defined",
       "New customers = Pool × Conversion" in html and "New customers = Spend ÷ CAC" in html
       and "New customers = FTE Count × Productivity" in html
       and "Channel names are labels only" in html)
    ck("monetary CAC authoring follows Foundry $000s convention",
       'unit:"$000s / year",kind:"k"' in html
       and 'lab:"Cost per customer acquired",unit:"$000s / customer",kind:"k"' in html)
    ck("explicit schedule editor is compact/local and no longer a full-width year grid",
       "Explicit is local to this primitive." in html and "source cadence" in html.lower())
    ck("feed retains beginning book and within-year AUC resolution controls",
       "Beginning customers" in html and "Beginning AUC" in html and "AUC within each model year" in html)

    print(f"\n{p} passed, {f} failed")
    return 0 if f==0 else 1

if __name__ == "__main__": sys.exit(main())
