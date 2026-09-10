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

print(f'\n{p} passed, {f} failed')
sys.exit(0 if f==0 else 1)
