import sys
import json
import re
import subprocess
from pathlib import Path

html=Path('web/console_v2.html').read_text()
checks=[
 ('Opex advanced control is progressive disclosure', 'Hide advanced' in html and '>Advanced' in html),
 ('Opex UI exposes additive expense components', 'Additive expense components' in html and '+ Add linked component' in html and '+ New cost-pool / cost-recovery component' in html),
 ('Opex Advanced exposes generalized tiered / banded linked components', '+ Tiered / banded component' in html and 'Tiered / banded linked component' in html and 'Band schedule' in html),
 ('tiered Opex exposes composite upstream balance terms rather than regulator-specific drivers', all(x in html for x in ['Total Assets · bank balance sheet','AUC / managed notional · ','Balance quantity · ','Weight / multiplier']) and 'OCC' not in html[html.find('function _opexPiecewiseTermOptions'):html.find('function _opexPiecewiseEditorHtml')]),
 ('tiered Opex makes event timing and observation lag explicit', 'Event cadence' in html and 'Observation lag' in html and 'First event' in html and 'piecewise_linked' in html),
 ('tiered Opex band table preserves literal lower/upper/base/rate authoring', all(x in html for x in ['Lower bound ($000s)','Upper bound ($000s)','Base amount ($000s)','Marginal rate (decimal)','final band is open-ended'])),
 ('tiered Opex UX separates timing, composite driver, and band schedule into delineated sections', 'opex-piecewise-section' in html and 'Choose when the component evaluates and which prior observation it reads.' in html and 'Build the balance evaluated by the band schedule.' in html and 'Amounts are in $000s.' in html),
 ('tiered Opex timing controls share a purpose-built aligned grid', 'class="opex-piecewise-timing-grid"' in html and 'First event model period' in html and re.search(r'\.opex-piecewise-timing-grid\{[^}]*grid-template-columns:minmax\(190px,1\.2fr\) minmax\(140px,\.8fr\) minmax\(165px,\.9fr\)[^}]*align-items:end',html) is not None),
 ('tiered Opex band inputs use compact one-row columns with same-row remove action', 'class="opex-piecewise-band-row"' in html and 'class="btn-plain opex-piecewise-remove" onclick="nieCatPiecewiseRemoveBand' in html and re.search(r'\.opex-piecewise-band-head,\.opex-piecewise-band-row\{[^}]*grid-template-columns:minmax\(0,112px\) minmax\(0,112px\) minmax\(0,112px\) minmax\(0,128px\) auto',html) is not None),
 ('balance Fee streams receive stable quantity Series IDs for downstream tiered Opex', '["transaction","balance"].includes(st.basis)' in html and 'fee_stream_balance_quantity::' in html),
 ('linked Opex drivers retain narrow revenue choices', all(x in html for x in ['Fee income','Gain on sale','Net servicing fees','Total noninterest income'])),
 ('Opex can link to transaction-stream throughput by stable quantity Series ID', 'fee_stream_quantity::' in html and 'Throughput / notional' in html and 'quantity_series_id' in html),
 ('Opex can link to CAC-owned AUC by stable Series ID', 'customer_acquisition_auc::' in html and 'AUC / managed notional' in html and 'canonical monthly AUC' in html),
 ('AUC-linked Opex exposes explicit balance measure plus natural rate period', 'nieCatLinkedMeasure' in html and all(x in html for x in ['Period average','Period end','Month','Quarter','Year']) and 'Existing r64/r65 links with no saved measure remain Period end' in html),
 ('AUC-linked Opex preview exposes the resolved consumer measure rather than raw EOP for both selector states', 'Latest run · ${bmLabel}' in html and '$000s balance · resolved consumer measure' in html and "bm===\"period_average\"?(((k?monthly[k-1]:begin)+v)/2):v" in html),
 ('linked fee throughput is inspection-only and shows latest resolved pull', 'upstream fee-stream throughput; edit the source in Fee Product' in html and 'Latest run · resolved pull' in html),
 ('linked Opex multiplier preserves sub-basis-point precision in the editor', 'nieCatLinkedRate' in html and 'step="any"' in html and '_numInput(_rv,12)' in html and '_rv.toFixed(2)' not in html),
 ('Opex UI exposes ordinal recognition timing', 'Recognition timing' in html and 'Same as trajectory' in html and 'first recognition' in html and 'then every' in html and 'Semiannual' in html and 'Annual' in html),
 ('recognition copy makes first occurrence literal and ordinal', 'literal first model-period occurrence' in html and 'Nothing hits Noninterest Expense before that period' in html and 'never Jan–Dec' in html),
 ('Opex UI removes the short-lived separate commencement axis', 'Expense begins' not in html and 'nieCatFlowStart' not in html and '_migrateOpexR60Start' in html),
 ('Monthly recognition also exposes a first model period', "if(_rm!=='trajectory')" in html and 'then every ${iv}' in html),
 ('Opex UI exposes ordinal cash settlement', 'Cash settlement' in html and 'Same as recognition' in html and 'first payment' in html and 'Semiannual' in html and 'Annual' in html),
 ('settlement copy explains prepaid/accrued accounting consequence', 'prepaid assets or accrued operating-expense liabilities' in html),
 ('legacy simplified OCC is explicit opt-in and hides timing when off', 'Legacy / simplified OCC assessment' in html and 'nieOccSimplifiedToggle' in html and 'Off — no simplified OCC expense posts.' in html and 'first cash payment' in html),
 ('Opex item header gives the expense name a medium-width authoring field', 'class=\"opex-item-head\"' in html and re.search(r'\.opex-item-head\{[^}]*grid-template-columns:24px minmax\(220px,420px\) 24px',html) is not None and 'placeholder=\"Expense item name\"' in html),
 ('Opex categories expose mouse drag-reorder with insertion markers', 'class=\"opex-drag-handle\"' in html and 'nieCatDragStart(event,${i})' in html and 'nieCatDrop(event,${i})' in html and '.opex-item-card.drop-before:before' in html),
 ('new Opex authoring does not expose r67 exclusive calculation-mode selector', 'Calculation</span><select' not in html and 'nieCatAddCostPoolCharge' in html),
 ('Opex cost-pool charge is an additive typed component', 'driver:"cost_pool_charge"' in html and 'The entered recurring amount above remains active' in html and 'Cost-pool / cost-recovery component' in html),
 ('Opex cost-pool editor authors all three generic pool component types', 'nieCatCostPoolComponentAddLinked' in html and '+ entered cost base' in html and '+ balance-linked cost' in html and 'Balance-linked cost · non-posting' in html),
 ('Opex cost-pool balance driver is visibly typed as pre-multiplier AUC, not client count or cost output', '_feeCostPoolBalancePreviewHtml(bsid,bm)' in html and 'Selected balance Series' in html and '$000s balance · before multiplier' in html and 'Client-count Series are not valid balance sources' in html),
 ('typed Opex cost-pool consumer exposes recovery and markup terms', 'nieCatCostPoolComponentRecovery' in html and 'Recovery (% of eligible cost pool)' in html and 'nieCatCostPoolComponentMarkupTrajectory' in html and 'Markup path' in html and 'Operating Expense = eligible cost pool × recovery % × (1 + markup %)' in html),
 ('shared pool deletion protects both revenue and additive Opex consumers', 'function _costPoolUsage(ref)' in html and 'driver==="cost_pool_charge"' in html and 'shared cost pool has' in html),
 ('legacy r67 exclusive cost-pool config remains renderable but is not newly authored', 'Legacy r67 cost-pool-only compatibility mode' in html and 'nieCatCalculationKind' in html),
 ('new Opex categories are prepended and focused instead of appearing off-screen at the bottom', 'nd.categories.unshift' in html and 'data-opex-index="${i}"' in html and 'scrollIntoView({block:"nearest",behavior:"smooth"})' in html),
 ('prepending an Opex category reindexes existing Advanced open state', 'const prevOpen=window._nieCatAdvancedOpen||{},nextOpen={}' in html and 'nextOpen[(+k||0)+1]=true' in html),
 ('Opex cost-pool authoring is hard-contained inside the Operating Expense card', 'class="opex-cost-pool-editor"' in html and 'opex-cost-pool-attached-row' in html and 'opex-cost-pool-head' in html and 'opex-cost-pool-add-actions' in html and 'opex-cost-pool-grid' in html and '#card-nie{overflow-x:hidden}' in html and 'contain:inline-size' in html and '.opex-cost-pool-editor .cac-link-preview{margin-left:0 !important' in html),
 ('Opex cost-pool removal lives in the component header instead of as a detached trailing link', 'opex-cost-pool-titlebar' in html and 'opex-cost-pool-remove' in html and 'Remove cost-pool component</button>' in html and '× remove cost-pool component</a>' not in html),
 ('new typed Opex cost-pool authoring hides the global pool registry until explicit reuse', 'Link existing shared pool…' in html and 'Explicitly reuse another in-use pool' in html and 'Old orphaned pools are intentionally hidden' in html and '_opexReusableCostPools' in html),
 ('Opex-owned pools have explicit ownership metadata and orphan cleanup', 'authoring_owner_module:"operating_expense"' in html and '_cleanupOwnedPoolOnDetach' in html and 'authoring_owner_component_id' in html),
 ('Opex shared-pool disclosure state is keyed by stable category/component identity', 'return owner+"::"+component' in html and 'lc.component_id||lc.ref' in html),
 ('deleting/clearing Opex categories and active Detailed render purge Opex-owned orphan pools', 'nieCatDelete=function' in html and '_purgeDeletedOpexOwnedPools([ct])' in html and '_purgeDeletedOpexOwnedPools(removed)' in html and 'function _pruneOrphanedOpexOwnedPools()' in html and '_pruneOrphanedOpexOwnedPools();' in html),
]
p=f=0
for name,ok in checks:
    if ok: p+=1; print('  PASS ',name)
    else: f+=1; print('  FAIL ',name)
# Execute the actual reorder handler in isolation: moving item A after C must preserve
# the category objects (and therefore their stable Series IDs) and the advanced-open state.
clear_m=re.search(r"function _nieCatClearDropMarkers\(\)\{.*?\}\n", html, re.S)
drop_m=re.search(r"window\.nieCatDrop=function\(ev,targetIndex\)\{.*?\};\n", html, re.S)
if clear_m and drop_m:
    js = r"""
const cfg={assumptions:{nie_detail:{categories:[
  {name:'A',series_id:'sid-a'}, {name:'B',series_id:'sid-b'}, {name:'C',series_id:'sid-c'}
]}}};
const document={querySelectorAll:()=>[]};
function _ensureNieDetail(){return cfg.assumptions.nie_detail;}
let rendered=0,refreshed=0; function renderContent(){rendered++;} function refresh(){refreshed++;}
window=globalThis; window._nieCatAdvancedOpen={0:true,2:true}; window._nieCatDragIndex=0;
""" + clear_m.group(0) + drop_m.group(0) + r"""
const card={dataset:{dropAfter:'1'}};
nieCatDrop({preventDefault(){},currentTarget:card},2);
console.log(JSON.stringify({order:cfg.assumptions.nie_detail.categories.map(x=>x.series_id),open:window._nieCatAdvancedOpen,rendered,refreshed}));
"""
    pr=subprocess.run(['node','-e',js],text=True,capture_output=True)
    ok=False
    if pr.returncode==0 and pr.stdout.strip():
        try:
            got=json.loads(pr.stdout.strip().splitlines()[-1])
            ok=(got.get('order')==['sid-b','sid-c','sid-a'] and got.get('open')=={'1':True,'2':True} and got.get('rendered')==1 and got.get('refreshed')==1)
        except Exception:
            pass
else:
    ok=False
if ok: p+=1; print('  PASS ', 'Opex drag reorder moves objects without losing stable identity/open state')
else: f+=1; print('  FAIL ', 'Opex drag reorder moves objects without losing stable identity/open state')

# Execute the actual Opex-owned cost-pool lifecycle. A new component must own a fresh
# empty pool; removing the sole consumer must clean up that owned pool; a second new
# component must get another fresh pool, not stale values from an orphan. The global
# registry may still contain old legacy orphans, but they are not implicitly reused.
block=re.search(r"window\._opexCostPoolReuseOpen=window\._opexCostPoolReuseOpen\|\|\{\};.*?window\.nieCatCostPoolComponentAdd=function\(i,j\)\{.*?\};\n", html, re.S)
if block:
    js=r"""
const cfg={assumptions:{nie_detail:{categories:[{series_id:'opex-1',name:'Platform',flow_spec:{trajectory:'flat',value:123,period:'year'}}]},cost_pools:[{series_id:'pool-old',owner_module:'cost_pool',name:'Legacy orphan',components:[{kind:'assumption_cost_base',flow_spec:{value:999}}]}],obs_exposures:[]}};
window=globalThis;let rendered=0,refreshed=0,seq=0;function renderContent(){rendered++;}function refresh(){refreshed++;}
function _ensureNieDetail(){return cfg.assumptions.nie_detail;}function _feeCostPools(){return cfg.assumptions.cost_pools;}
function _seriesId(prefix){seq++;return prefix+'-'+seq;}
function _feeCostPoolByRef(ref){return _feeCostPools().find(p=>p&&String(p.series_id||'')===String(ref||''))||null;}
function _costPoolUsage(ref){let opex=0;for(const ct of cfg.assumptions.nie_detail.categories||[])for(const lc of ct.linked_components||[])if(lc&&lc.driver==='cost_pool_charge'&&String(lc.ref||'')===String(ref||''))opex++;return {fee:[],opex:Array(opex).fill(0),total:opex};}
"""+block.group(0)+r"""
nieCatAddCostPoolCharge(0);
let ct=cfg.assumptions.nie_detail.categories[0],first=ct.linked_components[0],firstRef=first.ref,firstPool=_feeCostPoolByRef(firstRef);
firstPool.components.push({kind:'assumption_cost_base',flow_spec:{value:777}});
nieCatRemoveLinked(0,0);
const removedOwned=!_feeCostPoolByRef(firstRef);
nieCatAddCostPoolCharge(0);
ct=cfg.assumptions.nie_detail.categories[0];const second=ct.linked_components[0],secondPool=_feeCostPoolByRef(second.ref);
const reusable=_opexReusableCostPools(second.ref).map(p=>p.series_id);
console.log(JSON.stringify({flow:ct.flow_spec.value,firstRef,secondRef:second.ref,removedOwned,secondEmpty:secondPool&&secondPool.components.length===0,legacyStill:_feeCostPoolByRef('pool-old')!=null,reusable,pools:_feeCostPools().map(p=>p.series_id),componentId:second.component_id}));
"""
    pr=subprocess.run(['node','-e',js],text=True,capture_output=True)
    ok=False
    if pr.returncode==0 and pr.stdout.strip():
        try:
            got=json.loads(pr.stdout.strip().splitlines()[-1])
            ok=(got.get('flow')==123 and got.get('removedOwned') is True and got.get('secondEmpty') is True and got.get('legacyStill') is True and got.get('firstRef')!=got.get('secondRef') and got.get('reusable')==[] and bool(got.get('componentId')))
        except Exception:
            pass
else: ok=False
if ok: p+=1; print('  PASS ', 'Opex-owned pool lifecycle is fresh, cleans sole-use pools, and hides legacy orphans from implicit reuse')
else: f+=1; print('  FAIL ', 'Opex-owned pool lifecycle is fresh, cleans sole-use pools, and hides legacy orphans from implicit reuse')

# Explicit reuse is separate from new authoring. Linking an in-use shared pool should
# switch only after the user chooses it, and should clean the previous private pool.
if block:
    js=r"""
const cfg={assumptions:{nie_detail:{categories:[{series_id:'opex-1',name:'Platform',linked_components:[]}]},cost_pools:[{series_id:'pool-shared',owner_module:'cost_pool',name:'Shared fee pool',components:[{kind:'assumption_cost_base',flow_spec:{value:555}}]}],obs_exposures:[{fee_streams:[{driver:{source:'cost_pool',ref:'pool-shared'}}]}]}};
window=globalThis;let seq=0;function renderContent(){}function refresh(){}function _ensureNieDetail(){return cfg.assumptions.nie_detail;}function _feeCostPools(){return cfg.assumptions.cost_pools;}function _seriesId(prefix){seq++;return prefix+'-'+seq;}
function _feeCostPoolByRef(ref){return _feeCostPools().find(p=>p&&String(p.series_id||'')===String(ref||''))||null;}
function _costPoolUsage(ref){let fee=0,opex=0;for(const p of cfg.assumptions.obs_exposures||[])for(const st of p.fee_streams||[])if((st.driver||{}).source==='cost_pool'&&String((st.driver||{}).ref||'')===String(ref||''))fee++;for(const ct of cfg.assumptions.nie_detail.categories||[])for(const lc of ct.linked_components||[])if(lc&&lc.driver==='cost_pool_charge'&&String(lc.ref||'')===String(ref||''))opex++;return {fee:Array(fee).fill(0),opex:Array(opex).fill(0),total:fee+opex};}
"""+block.group(0)+r"""
nieCatAddCostPoolCharge(0);const privateRef=cfg.assumptions.nie_detail.categories[0].linked_components[0].ref;
const before=_opexReusableCostPools(privateRef).map(p=>p.series_id);
nieCatCostPoolComponentSelect(0,0,'pool-shared');
const lc=cfg.assumptions.nie_detail.categories[0].linked_components[0];
console.log(JSON.stringify({before,ref:lc.ref,privateGone:_feeCostPoolByRef(privateRef)==null,sharedStill:_feeCostPoolByRef('pool-shared')!=null,sharedValue:_feeCostPoolByRef('pool-shared').components[0].flow_spec.value}));
"""
    pr=subprocess.run(['node','-e',js],text=True,capture_output=True)
    ok=False
    if pr.returncode==0 and pr.stdout.strip():
        try:
            got=json.loads(pr.stdout.strip().splitlines()[-1]);ok=(got.get('before')==['pool-shared'] and got.get('ref')=='pool-shared' and got.get('privateGone') is True and got.get('sharedStill') is True and got.get('sharedValue')==555)
        except Exception: pass
else: ok=False
if ok: p+=1; print('  PASS ', 'existing shared pool reuse is explicit and preserves the shared pool while cleaning the replaced private pool')
else: f+=1; print('  FAIL ', 'existing shared pool reuse is explicit and preserves the shared pool while cleaning the replaced private pool')


# Render the actual typed Opex cost-pool editor with an attached private pool, one old orphan,
# and one in-use shared pool. The default card must not expose either registry entry; opening the
# explicit reuse affordance may show the in-use shared pool but still must hide the orphan.
editor=re.search(r"function _opexCostPoolEditorHtml\(i,ct,calc,j\)\{.*?\n\}\nfunction _opexTimingInterval", html, re.S)
if editor:
    fn=editor.group(0).rsplit('\nfunction _opexTimingInterval',1)[0]
    js=r"""
window=globalThis; window._opexCostPoolReuseOpen={};
const ct0={series_id:'opex-1',linked_components:[{driver:'cost_pool_charge',component_id:'comp-1',ref:'pool-own'}]};
const cfg={assumptions:{nie_detail:{categories:[ct0]},obs_exposures:[]}};
const pools=[
 {series_id:'pool-own',name:'Private platform pool',components:[],authoring_owner_module:'operating_expense',authoring_owner_series_id:'opex-1',authoring_owner_component_id:'comp-1'},
 {series_id:'pool-orphan',name:'OLD ORPHAN SHOULD NOT APPEAR',components:[]},
 {series_id:'pool-shared',name:'Reusable fee pool',components:[]}
];
function _ensureNieDetail(){return cfg.assumptions.nie_detail;} function _opexCostPoolReuseKey(i,j){const ct=(_ensureNieDetail().categories||[])[i]||{},lc=(ct.linked_components||[])[j]||{};return String(ct.series_id||('opex-index-'+i))+'::'+String(lc.component_id||lc.ref||('component-index-'+j));} function _feeCostPools(){return pools;} function _feeCostPoolByRef(r){return pools.find(p=>p.series_id===r)||null;} function _feeCostPoolIndex(r){return pools.findIndex(p=>p.series_id===r);}
function _costPoolDirectConsumerCount(r){return r==='pool-own'?1:r==='pool-shared'?1:0;}
function _costPoolOwnedByOpexComponent(p,ct,lc){return p.series_id==='pool-own'&&ct.series_id==='opex-1'&&lc.component_id==='comp-1';}
function _opexReusableCostPools(current){return pools.filter(p=>p.series_id!==current&&_costPoolDirectConsumerCount(p.series_id)>0);} function _feeCostPoolSourceOptions(){return [];} function PPY(){return 12;}
function esc(x){return String(x==null?'':x);} function fmtComma(x){return String(x);} function growthSpecInline(){return '';} const lastRes={};
"""+fn+r"""
const ct={series_id:'opex-1'}; const calc={driver:'cost_pool_charge',component_id:'comp-1',ref:'pool-own',recovery_pct:1,markup:{value:0,period:'year',trajectory:'flat',resolution:'step'}};
const closed=_opexCostPoolEditorHtml(0,ct,calc,0);
window._opexCostPoolReuseOpen['opex-1::comp-1']=true; const open=_opexCostPoolEditorHtml(0,ct,calc,0);
console.log(JSON.stringify({closedHasOrphan:closed.includes('OLD ORPHAN'),closedHasShared:closed.includes('Reusable fee pool'),closedHasOwn:closed.includes('Private platform pool'),openHasOrphan:open.includes('OLD ORPHAN'),openHasShared:open.includes('Reusable fee pool')}));
"""
    pr=subprocess.run(['node','-e',js],text=True,capture_output=True)
    ok=False
    if pr.returncode==0 and pr.stdout.strip():
        try:
            got=json.loads(pr.stdout.strip().splitlines()[-1]);ok=(got.get('closedHasOrphan') is False and got.get('closedHasShared') is False and got.get('closedHasOwn') is True and got.get('openHasOrphan') is False and got.get('openHasShared') is True)
        except Exception: pass
else: ok=False
if ok: p+=1; print('  PASS ', 'typed Opex pool editor hides the global registry by default and reveals only in-use pools on explicit reuse')
else: f+=1; print('  FAIL ', 'typed Opex pool editor hides the global registry by default and reveals only in-use pools on explicit reuse')


# Stable disclosure state must not bleed from an old row index into a newly inserted
# category/component that lands at the same i:j coordinates.
key_m=re.search(r"function _opexCostPoolReuseKey\(i,j\)\{.*?\n\}", html, re.S)
if key_m:
    js=r"""
window=globalThis;
const old={series_id:'opex-old',linked_components:[{driver:'cost_pool_charge',component_id:'comp-old',ref:'pool-old'}]};
const fresh={series_id:'opex-new',linked_components:[{driver:'cost_pool_charge',component_id:'comp-new',ref:'pool-new'}]};
const cfg={assumptions:{nie_detail:{categories:[old]}}}; function _ensureNieDetail(){return cfg.assumptions.nie_detail;}
"""+key_m.group(0)+r"""
window._opexCostPoolReuseOpen={}; const oldKey=_opexCostPoolReuseKey(0,0); window._opexCostPoolReuseOpen[oldKey]=true;
cfg.assumptions.nie_detail.categories.unshift(fresh); const newKey=_opexCostPoolReuseKey(0,0);
console.log(JSON.stringify({oldKey,newKey,newOpen:!!window._opexCostPoolReuseOpen[newKey]}));
"""
    pr=subprocess.run(['node','-e',js],text=True,capture_output=True)
    ok=False
    if pr.returncode==0 and pr.stdout.strip():
        try:
            got=json.loads(pr.stdout.strip().splitlines()[-1]);ok=(got.get('oldKey')=='opex-old::comp-old' and got.get('newKey')=='opex-new::comp-new' and got.get('newOpen') is False)
        except Exception: pass
else: ok=False
if ok: p+=1; print('  PASS ', 'Opex shared-pool disclosure cannot bleed by row index into a new category')
else: f+=1; print('  FAIL ', 'Opex shared-pool disclosure cannot bleed by row index into a new category')

# Deleting an entire Opex category must clean private pools created for that category;
# r73 only cleaned them when the cost-pool component itself was removed first.
purge_m=re.search(r"function _costPoolDirectConsumerCount\(ref\)\{.*?\n\}\nfunction _purgeDeletedOpexOwnedPools\(categories\)\{.*?\n\}", html, re.S)
del_m=re.search(r"window\.nieCatDelete=function\(i\)\{.*?\n\};", html, re.S)
if purge_m and del_m:
    js=r"""
window=globalThis;
const owned={series_id:'pool-own',name:'Private',authoring_owner_module:'operating_expense',authoring_owner_series_id:'opex-1',authoring_owner_component_id:'comp-1',components:[{kind:'assumption_cost_base'}]};
const globalPool={series_id:'pool-global',name:'Global',components:[]};
const cfg={assumptions:{nie_detail:{categories:[{series_id:'opex-1',linked_components:[{driver:'cost_pool_charge',component_id:'comp-1',ref:'pool-own'}]}]},cost_pools:[owned,globalPool],obs_exposures:[]}};
function _ensureNieDetail(){return cfg.assumptions.nie_detail;} function _feeCostPools(){return cfg.assumptions.cost_pools;} function _clearOpexCostPoolUiStateForCategory(){} function renderContent(){} function refresh(){}
"""+purge_m.group(0)+"\n"+del_m.group(0)+r"""
nieCatDelete(0); console.log(JSON.stringify({categories:cfg.assumptions.nie_detail.categories.length,pools:cfg.assumptions.cost_pools.map(p=>p.series_id)}));
"""
    pr=subprocess.run(['node','-e',js],text=True,capture_output=True)
    ok=False
    if pr.returncode==0 and pr.stdout.strip():
        try:
            got=json.loads(pr.stdout.strip().splitlines()[-1]);ok=(got.get('categories')==0 and got.get('pools')==['pool-global'])
        except Exception: pass
else: ok=False
if ok: p+=1; print('  PASS ', 'deleting an Opex category purges its orphaned private cost pool but preserves unrelated pools')
else: f+=1; print('  FAIL ', 'deleting an Opex category purges its orphaned private cost pool but preserves unrelated pools')


# Migration hygiene: pools leaked by r72/r73 already have Opex ownership metadata.
# When Detailed Opex is active they should be pruned only if no live consumer remains;
# shared/in-use pools and non-Opex pools must survive.
block=re.search(r"function _costPoolDirectConsumerCount\(ref\)\{.*?function _cleanupOwnedPoolOnDetach", html, re.S)
ok=False
if block:
    js=block.group(0).rsplit('function _cleanupOwnedPoolOnDetach',1)[0]
    js += r"""
const cfg={assumptions:{nie_detail:{categories:[{series_id:'opex-live',linked_components:[{driver:'cost_pool_charge',ref:'pool-live'}]}]},obs_exposures:[],cost_pools:[
 {series_id:'pool-ghost',authoring_owner_module:'operating_expense',authoring_owner_series_id:'opex-deleted',components:[{kind:'assumption_cost_base'}]},
 {series_id:'pool-live',authoring_owner_module:'operating_expense',authoring_owner_series_id:'opex-live',components:[]},
 {series_id:'pool-global',owner_module:'cost_pool',components:[]}
]}};
function _feeCostPools(){return cfg.assumptions.cost_pools;}
"""
    prune=re.search(r"function _pruneOrphanedOpexOwnedPools\(\)\{.*?\n\}", html, re.S)
    if prune:
        js += prune.group(0)+"\n_pruneOrphanedOpexOwnedPools();\nconsole.log(JSON.stringify(cfg.assumptions.cost_pools.map(x=>x.series_id)));\n"
        cp=subprocess.run(['node','-e',js],capture_output=True,text=True)
        if cp.returncode==0:
            try:
                refs=json.loads(cp.stdout.strip())
                ok=refs==['pool-live','pool-global']
            except Exception: pass
if ok: p+=1; print('  PASS ', 'Detailed-mode migration hygiene prunes leaked Opex-owned orphans only')
else: f+=1; print('  FAIL ', 'Detailed-mode migration hygiene prunes leaked Opex-owned orphans only')


# Execute the actual AUC preview helper with a deliberately rising balance path. Flipping
# Period end -> Period average must change the exposed Series, including the opening-AUC
# convention, rather than merely changing a label over the same EOP values.
preview_m=re.search(r"function _opexLinkedSourcePreview\(lc\)\{.*?\n\}", html, re.S)
if preview_m:
    js=r"""
const cfg={assumptions:{cac_feeds:{Wealth:{series_id:'auc-1',beginning_auc:0}}}};
const lastRes={customer_acquisition:{Wealth:{aucEndByMonth:[83333.333,166666.667,250000]}}};
function _opexLinkedDriverOptions(){return [{value:'customer_acquisition_auc::auc-1',driver:'customer_acquisition_auc',series_id:'auc-1',feed:'Wealth'}];}
function _opexLinkedDriverValue(lc){return 'customer_acquisition_auc::'+String(lc.series_id||'');}
function esc(x){return String(x);} function fmtComma(x){return Number(x).toFixed(4).replace(/\.0000$/,'');}
"""+preview_m.group(0)+r"""
const eop=_opexLinkedSourcePreview({driver:'customer_acquisition_auc',series_id:'auc-1',measure:'period_end'});
const avg=_opexLinkedSourcePreview({driver:'customer_acquisition_auc',series_id:'auc-1',measure:'period_average'});
console.log(JSON.stringify({eop,avg}));
"""
    pr=subprocess.run(['node','-e',js],text=True,capture_output=True)
    ok=False
    if pr.returncode==0 and pr.stdout.strip():
        try:
            got=json.loads(pr.stdout.strip().splitlines()[-1])
            eop,avg=got.get('eop',''),got.get('avg','')
            ok=('M1 83333.3330' in eop and 'M2 166666.6670' in eop and
                'M1 41666.6665' in avg and 'M2 125000' in avg and
                'Period-end AUC' in eop and 'Period-average AUC' in avg and eop!=avg)
        except Exception:
            pass
else:
    ok=False
if ok: p+=1; print('  PASS ', 'AUC-linked Opex preview visibly switches between EOP and period-average consumed Series')
else: f+=1; print('  FAIL ', 'AUC-linked Opex preview visibly switches between EOP and period-average consumed Series')

# Execute the simplified OCC toggle itself: modern Detailed Opex starts disabled;
# enabling materializes visible legacy rate/timing while disabling preserves those
# draft settings without posting the shortcut.
toggle_m=re.search(r"window\.nieOccSimplifiedToggle = function\(on\)\{.*?\n\};", html, re.S)
if toggle_m:
    js=r"""
window=globalThis;
const cfg={assumptions:{nie_detail:{categories:[],fdic_bp_ann:5.0,occ_simplified_enabled:false}}};
function _ensureNieDetail(){return cfg.assumptions.nie_detail;}
function PPY(){return 12;} function renderContent(){} function refresh(){}
"""+toggle_m.group(0)+r"""
nieOccSimplifiedToggle(true);
const enabled=JSON.parse(JSON.stringify(cfg.assumptions.nie_detail));
nieOccSimplifiedToggle(false);
const disabled=JSON.parse(JSON.stringify(cfg.assumptions.nie_detail));
console.log(JSON.stringify({enabled,disabled}));
"""
    pr=subprocess.run(['node','-e',js],text=True,capture_output=True)
    ok=False
    if pr.returncode==0 and pr.stdout.strip():
        try:
            got=json.loads(pr.stdout.strip().splitlines()[-1]); en=got.get('enabled',{}); dis=got.get('disabled',{})
            ok=(en.get('occ_simplified_enabled') is True
                and abs(en.get('occ_bp_ann',0)-1.5)<1e-12
                and en.get('occ_payment_first_period')==3
                and dis.get('occ_simplified_enabled') is False
                and abs(dis.get('occ_bp_ann',0)-1.5)<1e-12
                and dis.get('occ_payment_first_period')==3)
        except Exception:
            pass
else:
    ok=False
if ok: p+=1; print('  PASS ', 'simplified OCC toggle is explicit opt-in and preserves disabled draft settings')
else: f+=1; print('  FAIL ', 'simplified OCC toggle is explicit opt-in and preserves disabled draft settings')


print(f'\n{p} passed, {f} failed')
sys.exit(0 if f==0 else 1)
