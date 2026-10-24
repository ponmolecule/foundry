"""r392: product editor section rail for every product family (console only)."""
import subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];H=(ROOT/'web/console_v2.html').read_text()
ok=fail=0
def ck(name,cond):
    global ok,fail
    print(('  PASS  ' if cond else '  FAIL  ')+name);ok+=bool(cond);fail+=not cond
ck('grouping hook hands every decorated family to the rail',"if(typeof lfgDecorate==='function'&&lfgDecorate(card)) { if(typeof lnvDecorate==='function') lnvDecorate(card); return; }" in H)
ck('funded-flow lending also gets the rail',"_loanBalanceMode(p)==='funded_flow_level') { if(typeof lnvDecorate==='function') lnvDecorate(card); return; }" in H)
ck('method labels describe the modeling approach','>Dollar originations · single runoff rate</option>' in H and '>Loan production · separate payment and prepayment rates</option>' in H)
ck('former method labels no longer shown as options','>Existing loan mechanics<' not in H and '>Live production + balance-based repayment<' not in H)
ck('switching back to dollar originations asks first','function lnvMethodConfirm(i)' in H and '_lnvConfirm.set(p,true)' in H)
ck('advanced badges read stored settings','function _lnvAdvanced(fam,p,key)' in H)
r=subprocess.run(['node',str(ROOT/'web/tests_r392_product_rail.cjs')],capture_output=True,text=True,cwd=str(ROOT),timeout=280)
ck('browser behaviour (node)',r.returncode==0)
if r.returncode:print(r.stdout[-2000:],r.stderr[-2000:])
print(f"\n{ok} passed, {fail} failed")
raise SystemExit(1 if fail else 0)
