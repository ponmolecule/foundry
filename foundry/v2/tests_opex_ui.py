import sys
from pathlib import Path

html=Path('web/console_v2.html').read_text()
checks=[
 ('Opex advanced control is progressive disclosure', 'Hide advanced' in html and '>Advanced' in html),
 ('Opex UI exposes linked expense components', 'Linked expense components' in html and '+ Add linked component' in html),
 ('linked Opex drivers retain narrow revenue choices', all(x in html for x in ['Fee income','Gain on sale','Net servicing fees','Total noninterest income'])),
 ('Opex can link to transaction-stream throughput by stable quantity Series ID', 'fee_stream_quantity::' in html and 'Throughput / notional' in html and 'quantity_series_id' in html),
 ('linked fee throughput is inspection-only and shows latest resolved pull', 'upstream fee-stream throughput; edit the source in Fee Product' in html and 'Latest run · resolved pull' in html),
 ('Opex UI exposes generic recognition timing', 'Recognition timing' in html and 'Same as trajectory' in html and 'recognize in' in html and 'Semiannual' in html and 'Annual' in html),
 ('recognition copy separates economic trajectory from NIE timing', 'Controls when the economic expense trajectory hits Noninterest Expense' in html),
 ('Opex UI exposes generic cash settlement', 'Cash settlement' in html and 'Same as recognition' in html and 'Semiannual' in html and 'Annual' in html),
 ('settlement copy explains prepaid/accrued accounting consequence', 'prepaid assets or accrued operating-expense liabilities' in html),
 ('OCC UI discloses semiannual Dec/Jun base and Mar/Sep settlement', 'Semiannual: Dec/Jun asset base' in html and 'settled Mar/Sep' not in html and 'paid Mar/Sep' in html),
]
p=f=0
for name,ok in checks:
    if ok: p+=1; print('  PASS ',name)
    else: f+=1; print('  FAIL ',name)
print(f'\n{p} passed, {f} failed')
sys.exit(0 if f==0 else 1)
