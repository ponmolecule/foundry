"""r353: industrial layout extended to every product family (console only)."""
import subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];H=(ROOT/'web/console_v2.html').read_text()
ok=fail=0
def ck(name,cond):
    global ok,fail
    print(('  PASS  ' if cond else '  FAIL  ')+name);ok+=bool(cond);fail+=not cond
ck('grouping hook hands loans, deposits and off-balance-sheet products to the decorator',"if(typeof lfgDecorate==='function'&&lfgDecorate(card)) {" in H)   # r392: the rail decorator follows
ck('decorator re-seats existing controls rather than re-rendering them',"grid.appendChild(el)" in H and "ctl.dispatchEvent(new Event('change',{bubbles:true}))" in H)
ck('funded-flow loans keep their own renderer',"if(fam==='lending'&&_loanBalanceMode(p)==='funded_flow_level')return false;" in H)
ck('engine figures refresh in place after each run',"if(typeof refreshLfgLive==='function') refreshLfgLive();   // r353" in H)
ck('fee-streams layout applies to every family that has streams',"(+_fi>=1000?(fam==='lending'||fam==='deposit'):!!(p&&(p._fee_product||p.managed_notional)))" in H)
ck('collapsed sections hide their body','.lfx-b[hidden]{display:none!important}' in H)
r=subprocess.run(['node',str(ROOT/'web/tests_r353_product_layout.cjs')],capture_output=True,text=True)
ck('strip and readout test (node)',r.returncode==0)
if r.returncode:print(r.stdout,r.stderr)
print(f"\n{ok} passed, {fail} failed")
raise SystemExit(1 if fail else 0)
