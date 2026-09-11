import sys
import json
import re
import subprocess
from pathlib import Path

html=Path('web/console_v2.html').read_text()
checks=[
 ('Opex advanced control is progressive disclosure', 'Hide advanced' in html and '>Advanced' in html),
 ('Opex UI exposes linked expense components', 'Linked expense components' in html and '+ Add linked component' in html),
 ('linked Opex drivers retain narrow revenue choices', all(x in html for x in ['Fee income','Gain on sale','Net servicing fees','Total noninterest income'])),
 ('Opex can link to transaction-stream throughput by stable quantity Series ID', 'fee_stream_quantity::' in html and 'Throughput / notional' in html and 'quantity_series_id' in html),
 ('Opex can link to CAC-owned AUC by stable Series ID', 'customer_acquisition_auc::' in html and 'AUC / managed notional' in html and 'canonical monthly EOP AUC' in html),
 ('AUC-linked Opex exposes explicit balance measure plus natural rate period', 'nieCatLinkedMeasure' in html and all(x in html for x in ['Period average','Period end','Month','Quarter','Year']) and 'Existing r64/r65 links with no saved measure remain Period end' in html),
 ('linked fee throughput is inspection-only and shows latest resolved pull', 'upstream fee-stream throughput; edit the source in Fee Product' in html and 'Latest run · resolved pull' in html),
 ('linked Opex multiplier preserves sub-basis-point precision in the editor', 'nieCatLinkedRate' in html and 'step="any"' in html and '_numInput(_rv,12)' in html and '_rv.toFixed(2)' not in html),
 ('Opex UI exposes ordinal recognition timing', 'Recognition timing' in html and 'Same as trajectory' in html and 'first recognition' in html and 'then every' in html and 'Semiannual' in html and 'Annual' in html),
 ('recognition copy makes first occurrence literal and ordinal', 'literal first model-period occurrence' in html and 'Nothing hits Noninterest Expense before that period' in html and 'never Jan–Dec' in html),
 ('Opex UI removes the short-lived separate commencement axis', 'Expense begins' not in html and 'nieCatFlowStart' not in html and '_migrateOpexR60Start' in html),
 ('Monthly recognition also exposes a first model period', "if(_rm!=='trajectory')" in html and 'then every ${iv}' in html),
 ('Opex UI exposes ordinal cash settlement', 'Cash settlement' in html and 'Same as recognition' in html and 'first payment' in html and 'Semiannual' in html and 'Annual' in html),
 ('settlement copy explains prepaid/accrued accounting consequence', 'prepaid assets or accrued operating-expense liabilities' in html),
 ('OCC UI uses ordinal semiannual payment timing', 'Semiannual ordinal cycle' in html and 'occ_payment_first_period' in html and 'Client calendar dates are translated' in html),
 ('Opex item header gives the expense name a medium-width authoring field', 'class=\"opex-item-head\"' in html and 'minmax(220px,420px)' in html and 'minmax(220px,1fr)' not in html and 'placeholder=\"Expense item name\"' in html),
 ('Opex categories expose mouse drag-reorder with insertion markers', 'class=\"opex-drag-handle\"' in html and 'nieCatDragStart(event,${i})' in html and 'nieCatDrop(event,${i})' in html and '.opex-item-card.drop-before:before' in html),
 ('Opex category exposes accounting-destination calculation selector', 'Calculation</span><select' in html and 'Entered recurring expense' in html and 'Cost pool / cost-plus' in html and 'Final calculated charge posts to this Operating Expense category' in html),
 ('Opex cost-pool editor keeps calculation inputs non-posting and final charge single-posting', 'Cost pool / cost-plus calculation' in html and 'Cost-pool inputs do not post expense themselves' in html and 'posts once to NIE' in html),
 ('Opex cost-pool editor authors all three generic component types', 'nieCatCostPoolAddLinked' in html and '+ entered cost base' in html and '+ balance-linked cost' in html and 'Balance-linked cost · non-posting' in html),
 ('Opex cost-pool consumer exposes recovery and markup terms', 'nieCatCostPoolRecovery' in html and 'Recovery (% of eligible cost pool)' in html and 'nieCatCostPoolMarkupTrajectory' in html and 'Markup path' in html and 'Operating Expense = eligible cost pool × recovery % × (1 + markup %)' in html),
 ('shared pool deletion protects both revenue and Opex consumers', 'function _costPoolUsage(ref)' in html and 'calc.kind==="cost_pool"' in html and 'shared cost pool has' in html),
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

# Execute the Opex calculation-source switch in isolation. A legacy entered category must keep its
# dormant entered draft while Cost pool / cost-plus becomes active, and switching back must restore
# entered semantics without deleting that draft.
calc_helper=re.search(r"function _ensureNieCostPoolCalc\(i\)\{.*?\n\}", html, re.S)
calc_switch=re.search(r"window\.nieCatCalculationKind=function\(i,kind\)\{.*?\n\};", html, re.S)
if calc_helper and calc_switch:
    js=r"""
const cfg={assumptions:{nie_detail:{categories:[{series_id:'opex-1',name:'Platform',flow_spec:{trajectory:'flat',value:123,period:'year'}}]},cost_pools:[]}};
window=globalThis;let rendered=0,refreshed=0;function renderContent(){rendered++;}function refresh(){refreshed++;}
function _ensureNieDetail(){return cfg.assumptions.nie_detail;}function _feeCostPools(){return cfg.assumptions.cost_pools;}
function _seriesId(){return 'pool-new';}
"""+calc_helper.group(0)+"\n"+calc_switch.group(0)+r"""
nieCatCalculationKind(0,'cost_pool');
const afterCost=JSON.parse(JSON.stringify(cfg));
nieCatCalculationKind(0,'entered');
console.log(JSON.stringify({afterCost,afterEntered:cfg,rendered,refreshed}));
"""
    pr=subprocess.run(['node','-e',js],text=True,capture_output=True)
    ok=False
    if pr.returncode==0 and pr.stdout.strip():
        try:
            got=json.loads(pr.stdout.strip().splitlines()[-1]); ac=got['afterCost']['assumptions']; ae=got['afterEntered']['assumptions']
            cc=ac['nie_detail']['categories'][0].get('calculation') or {}
            ok=(cc.get('kind')=='cost_pool' and cc.get('ref')=='pool-new' and cc.get('recovery_pct')==1 and
                (cc.get('markup') or {}).get('value')==0 and len(ac.get('cost_pools') or [])==1 and
                ac['nie_detail']['categories'][0]['flow_spec']['value']==123 and
                'calculation' not in ae['nie_detail']['categories'][0] and ae['nie_detail']['categories'][0]['flow_spec']['value']==123)
        except Exception:
            pass
else: ok=False
if ok: p+=1; print('  PASS ', 'Opex calculation switch preserves dormant entered draft and creates cost-pool defaults')
else: f+=1; print('  FAIL ', 'Opex calculation switch preserves dormant entered draft and creates cost-pool defaults')

print(f'\n{p} passed, {f} failed')
sys.exit(0 if f==0 else 1)
