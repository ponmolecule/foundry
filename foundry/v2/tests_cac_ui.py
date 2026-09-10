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
    ha=html.index("function _seriesPasteNumbers")
    hb=html.index("function _newNieDetail", ha)
    helpers=html[ha:hb]
    # Scalar Explicit schedules share the canonical fail-closed parser/controller,
    # defined with the Fee helpers but used by CAC/Workforce/Opex as well.
    ca=html.index("function _seriesExplicitValues")
    cb=html.index("function _feeParseExplicitValues", ca)
    helpers += "\n" + html[ca:cb]
    prefix=r'''
const window=globalThis;
const document={querySelectorAll:()=>[]};
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
function renderContent(){} function refresh(){} function appStatus(){} function _pf(x){let n=parseFloat(String(x).replace(/[^0-9.\-]/g,''));return isNaN(n)?0:n;}
function fmtComma(x){return String(x)} function esc(x){return String(x)} function _seriesId(p){return p+'-test'} function PLAB(full){return full?'month':'M'} function _qGrowthToPeriod(x){return x}
window.confirm=()=>true;window.alert=()=>{};
let lastRes={customer_acquisition:{growth:{annual:[{channels:[{}, {spend:120}]},{channels:[{}, {spend:135}]}]}}};
'''
    suffix=r'''
const fd=cfg.assumptions.cac_feeds.growth;
// Materialize generic dials without changing channel names/equations.
fd.channels.forEach(ch=>_cacMeta(ch.method).forEach(m=>_cacEnsureSpec(ch,m.k)));
const seeded={m0:Object.keys(fd.channels[0].driver_specs).sort(),m1:Object.keys(fd.channels[1].driver_specs).sort()};
window.cacDriverTrajectory('growth',0,'pool','explicit');
const poolDefaultClosed=_cacExplicitIsClosed('growth',0,'pool');
window.cacSchedulePaste('growth',0,'pool','1,000\t2,500\t3,000','number');
const poolLoaded=[...fd.channels[0].driver_specs.pool.values];
window.cacExplicitClose('growth',0,'pool'); const poolClosed=_cacExplicitIsClosed('growth',0,'pool');
window.cacExplicitOpen('growth',0,'pool'); const poolOpen=!_cacExplicitIsClosed('growth',0,'pool');
window.cacScheduleClear('growth',0,'pool'); const poolCleared=[...fd.channels[0].driver_specs.pool.values];
window.cacSchedulePaste('growth',0,'pool','1,000\t2,500\t3,000','number');
const unitProbe={pool:_cacStored('2,500','number'),spend:_cacStored('1,250','k'),cac:_cacStored('1,250','price'),auc:_cacStored('500','k')};
window.cacDriverSource('growth',1,'spend','link');
const spendLink=fd.channels[1].driver_specs.spend;
const spendPreviewFlat=_cacLinkedSourcePreview('growth',1,_cacMeta(fd.channels[1].method).find(x=>x.k==='spend'),spendLink);
cfg.assumptions.nie_detail.categories[0].trajectory='explicit'; cfg.assumptions.nie_detail.categories[0].schedule=[10000,12000,14000];
const spendPreviewExplicit=_cacLinkedSourcePreview('growth',1,_cacMeta(fd.channels[1].method).find(x=>x.k==='spend'),spendLink);
window.cacMethodChange('growth',0,'fte_productivity');
window.cacDriverSource('growth',0,'ftes','link');
const fteLink=fd.channels[0].driver_specs.ftes;
const ftePreview=_cacLinkedSourcePreview('growth',0,_cacMeta(fd.channels[0].method).find(x=>x.k==='ftes'),fteLink);
const firstChannel=fd.channels[0],secondChannel=fd.channels[1];_cacEnsureDerivedIds(firstChannel);_cacEnsureDerivedIds(secondChannel);const firstSeries=firstChannel.derived_series_ids.new_customers;
window._cacExplicitClosed[_cacExplicitUiKey('growth',0,'per_fte')]=false;
window._cacChannelDrag={feed:'growth',index:0};
window.cacChannelDrop({preventDefault(){},currentTarget:{dataset:{dropAfter:'1'}}},'growth',1);
const reordered={names:fd.channels.map(x=>x.name),movedSameObject:fd.channels[1]===firstChannel,seriesPreserved:fd.channels[1].derived_series_ids.new_customers===firstSeries,explicitStateMoved:_cacExplicitIsClosed('growth',1,'per_fte')===false};
window._cacChannelDrag={feed:'growth',index:1};
window.cacChannelDrop({preventDefault(){},currentTarget:{dataset:{dropAfter:'0'}}},'growth',0);
const reorderedUp={names:fd.channels.map(x=>x.name),movedSameObject:fd.channels[0]===firstChannel,seriesPreserved:fd.channels[0].derived_series_ids.new_customers===firstSeries,explicitStateMoved:_cacExplicitIsClosed('growth',0,'per_fte')===false};
cfg.assumptions.cac_feeds.other={channels:[{name:'Other feed channel',method:'explicit',driver_specs:{},derived_series_ids:{new_customers:'other-nc',new_auc:'other-na'}}]};
window._cacChannelDrag={feed:'growth',index:0};
window.cacChannelDrop({preventDefault(){},currentTarget:{dataset:{dropAfter:'1'}}},'other',0);
const crossFeedGuard={growthNames:fd.channels.map(x=>x.name),otherNames:cfg.assumptions.cac_feeds.other.channels.map(x=>x.name)};
window.nop=0;
console.log(JSON.stringify({seeded,pool:fd.channels[0].driver_specs.pool,poolLoaded,poolCleared,poolDefaultClosed,poolClosed,poolOpen,spendLink,spendPreviewFlat,spendPreviewExplicit,fteLink,ftePreview,method:fd.channels[0].method,unitProbe,reordered,reorderedUp,crossFeedGuard}));
'''
    br=subprocess.run(["node","-e",prefix+helpers+js+suffix],text=True,capture_output=True)
    bj={}
    if br.returncode==0 and br.stdout.strip():
        try: bj=json.loads(br.stdout.strip().splitlines()[-1])
        except Exception: pass
    sd=bj.get("seeded") or {}
    ck("driver dials are equation-driven, not hard-coded to channel names",
       br.returncode==0 and sd.get("m0")==["avg_auc_per_customer","conversion_rate","pool"]
       and sd.get("m1")==["avg_auc_per_customer","cac","spend"], br.stderr.strip())
    ck("CAC Explicit paste editors are closed by default", bj.get("poolDefaultClosed") is True)
    ck("explicit CAC values load through a pastebox instead of one cell per period",
       bj.get("poolLoaded")==[1000,2500,3000] and (bj.get("pool") or {}).get("values")==[1000,2500,3000])
    ck("CAC Explicit Close is UI-only and can be reopened without changing schedule values",
       bj.get("poolClosed") is True and bj.get("poolOpen") is True and bj.get("poolLoaded")==[1000,2500,3000])
    ck("CAC Explicit Clear removes the loaded schedule without changing trajectory mode",
       bj.get("poolCleared")==[] and (bj.get("pool") or {}).get("mode")=="explicit")
    sl=(bj.get("spendLink") or {}).get("link") or {}
    ck("Spend can link generically to an Operating Expense series by stable ID",
       sl.get("kind")=="operating_expense_category" and sl.get("series_id")=="opex-bd" and sl.get("aggregation")=="sum")
    fl=(bj.get("fteLink") or {}).get("link") or {}
    ck("FTE productivity can link generically to Workforce Count by stable ID",
       bj.get("method")=="fte_productivity" and fl.get("kind")=="workforce_role_count" and fl.get("series_id")=="wf-rm")
    ck("linked Workforce Count is also inspectable rather than opaque",
       "Relationship Managers" in (bj.get("ftePreview") or "")
       and "Linked source path" in (bj.get("ftePreview") or "")
       and "Flat · 3 FTE" in (bj.get("ftePreview") or ""))

    ck("spreadsheet-style global annual input grid is removed",
       "Use annual source schedule" not in html and "Annual source driver" not in html
       and "Annual source schedule active" not in html)
    ck("CAC authoring explicitly presents per-driver equation-of-motion dials",
       "Each driver owns its own trajectory or links to a Foundry series owned elsewhere" in html
       and "Flat" in html and "Growth" in html and "Explicit" in html and "Link" in html)
    ck("CAC explains causal ownership instead of duplicating budgets/headcount",
       "CAC does not duplicate budgets or headcount assumptions" in html
       and "trajectory owned by source" in html)
    ck("Acquisition Spend link explains the required upstream Opex source instead of reporting a generic broken link",
       "Acquisition spend can link only to an Operating expense category" in html
       and "keep Acquisition spend entered directly in Customer Acquisition" in html)
    ck("linked Acquisition Spend exposes the upstream source path instead of hiding it",
       "Business Development" in (bj.get("spendPreviewFlat") or "")
       and "Linked source path" in (bj.get("spendPreviewFlat") or "")
       and "Flat" in (bj.get("spendPreviewFlat") or "")
       and "Latest run · resolved pull" in (bj.get("spendPreviewFlat") or "")
       and "Y1 120" in (bj.get("spendPreviewFlat") or ""))
    ck("linked Explicit Acquisition Spend exposes the complete read-only source schedule",
       "cac-link-readonly" in (bj.get("spendPreviewExplicit") or "")
       and "10 · 12 · 14" in (bj.get("spendPreviewExplicit") or "")
       and "3 source values" in (bj.get("spendPreviewExplicit") or "")
       and "read-only here; edit the source in Operating Expense" in (bj.get("spendPreviewExplicit") or ""))
    ck("acquisition equations remain the closed vocabulary while channel names are user-defined",
       "New customers = Pool × Conversion" in html and "New customers = Spend ÷ CAC" in html
       and "New customers = FTE Count × Productivity" in html
       and "Channel names are labels only" in html)
    up=bj.get("unitProbe") or {}
    ck("CAC units distinguish balances/spend from per-unit prices and natural counts",
       up=={"pool":2500,"spend":1250000,"cac":1250,"auc":500000}
       and 'unit:"$000s / year",kind:"k"' in html
       and 'lab:"Cost per customer acquired",unit:"$ / customer",kind:"price"' in html
       and 'lab:"Addressable pool",unit:"customers",kind:"number"' in html)
    ck("every CAC Explicit primitive uses a visible pastebox with Clear and Close actions",
       "cacSchedulePaste(" in html and "Paste a row or column from Excel/Sheets" in html
       and "cacFeedExplicitPaste(" in html and "Load (replace)" in html
       and "cacScheduleClear(" in html and "cacExplicitClose(" in html
       and "cacFeedExplicitClear(" in html and "cacFeedExplicitClose(" in html
       and ">Clear</button>" in html and ">Close</button>" in html and "Edit schedule" in html)
    ck("CAC Explicit keeps source cadence but removes meaningless Step/Smooth interpolation",
       "CAC does not interpolate between source points" in html and "cacScheduleResolution" not in html)
    ck("feed retains beginning book and within-year AUC resolution controls",
       "Beginning customers" in html and "Beginning AUC" in html and "AUC within each model year" in html)
    ck("calculated customer-base audit view is a thin fully gridded table",
       'class="cac-audit-grid"' in html
       and "table.cac-audit-grid th,table.cac-audit-grid td{border:1px solid" in html
       and "Calculated customer-base roll-forward · audit view" in html)
    ck("customer-base audit view uses integer display and labels monetary balances as $000s in the header",
       'const _auditInt=v=>Math.round(v).toLocaleString("en-US")' in html
       and 'Calculated output · monetary balances in $000s' in html
       and 'maximumFractionDigits:1' not in html[html.index("Calculated customer-base roll-forward · audit view"):html.index("Calculated customer-base roll-forward · audit view")+2200])
    ck("Customer Acquisition tile has the same compact expand/collapse pattern as other long Config sections",
       'window.cacSectionSetOpen=function(isOpen)' in html
       and "_cfgSectionIsOpen('customeracq'" in html
       and "${_cacOpen?'Collapse':'Expand'}" in html
       and 'expand to inspect or edit' in html)
    ck("CAC hierarchy uses distinct feed containers with visibly nested acquisition-channel cards",
       'class="cac-feed-card"' in html and 'class="cac-channel-card"' in html
       and '.cac-feed-card{border:1px solid rgba(223,168,90,.30)' in html
       and '.cac-channel-card:before' in html
       and 'Acquisition channels below are visually nested' in html)
    ck("Acquisition channels expose a dedicated mouse drag handle and drop affordance",
       'class="cac-channel-drag-handle"' in html
       and 'draggable="true" aria-label="Drag acquisition channel to reorder"' in html
       and 'ondragover="cacChannelDragOver(' in html
       and 'ondrop="cacChannelDrop(' in html
       and '.cac-channel-card.drop-before' in html and '.cac-channel-card.drop-after' in html)
    ro=bj.get("reordered") or {}
    ck("dragging an acquisition channel reorders the actual channel object with Series identity intact",
       ro.get("names")==["Relationship-led","Partner referrals"]
       and ro.get("movedSameObject") is True and ro.get("seriesPreserved") is True)
    ck("CAC drag reorder carries Explicit editor state with the moved channel",
       ro.get("explicitStateMoved") is True)
    ru=bj.get("reorderedUp") or {}
    ck("acquisition channels can be dragged upward as well as downward without losing identity",
       ru.get("names")==["Partner referrals","Relationship-led"]
       and ru.get("movedSameObject") is True and ru.get("seriesPreserved") is True
       and ru.get("explicitStateMoved") is True)
    cg=bj.get("crossFeedGuard") or {}
    ck("CAC drag reorder is feed-scoped and cannot silently move a channel across feeds",
       cg.get("growthNames")==["Partner referrals","Relationship-led"]
       and cg.get("otherNames")==["Other feed channel"])

    print(f"\n{p} passed, {f} failed")
    return 0 if f==0 else 1

if __name__ == "__main__": sys.exit(main())
