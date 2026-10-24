"""r395: Loan production vs balance authoring, and the fee-product AUC ramp unit (console fixes)."""
import copy, json, subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];H=(ROOT/'web/console_v2.html').read_text()
ok=fail=0
def ck(name,cond,detail=''):
    global ok,fail
    print(('  PASS  ' if cond else '  FAIL  ')+name+('' if cond or not detail else '\n        '+str(detail)[:500]));ok+=bool(cond);fail+=not cond
ck('leaving Loan roll-forward with Loan production asks first',"if(to!=='rollforward'&&from==='rollforward'&&p.loan_rollforward){_lbmPending.set(p,to);" in H)
ck('saved products in the rejected state are flagged with a fix','function loanContractClearStale(i)' in H and 'This product cannot run as saved.' in H)
ck('AUC ramp is labelled in the model period','F("Ramp to target ("+PLAB(\'full\')+"s)", mnb+".ramp_periods", "n")' in H and 'Ramp to target (quarters)' not in H)
# The engine side these guards protect: Loan production is rejected outside Loan roll-forward, and accepted without it.
from foundry.v2.run_q import run_v2
base=json.loads((ROOT/'foundry/fixtures/universal_template_bank.json').read_text())
lp=base['assumptions']['lending_products']
i=next(k for k,p in enumerate(lp) if (p.get('balance_mode') or 'rollforward')=='rollforward' and not p.get('repayment_profile') and not p.get('mortgage_banking') and not p.get('allocation_group_id'))
c=copy.deepcopy(base);p=c['assumptions']['lending_products'][i]
p['balance_mode']='explicit_level';p['ending_balance_spec']={'source':'entered','trajectory':'flat','value':0};p['structure']='revolving'
p['loan_rollforward']={'source':'entered_count','count_spec':{'source':'entered','trajectory':'flat','value':0}}
try:
    run_v2(c);ck('engine rejects Loan production outside Loan roll-forward (the state the console now prevents)',False,'ran')
except Exception as ex:
    ck('engine rejects Loan production outside Loan roll-forward (the state the console now prevents)','requires Loan roll-forward' in str(ex),ex)
del p['loan_rollforward']
try:
    run_v2(c);ck('the same product runs once Loan production is removed',True)
except Exception as ex:
    ck('the same product runs once Loan production is removed',False,ex)
r=subprocess.run(['node',str(ROOT/'web/tests_r395_switch_guards.cjs')],capture_output=True,text=True,cwd=str(ROOT),timeout=280)
ck('browser behaviour (node)',r.returncode==0,(r.stdout[-1500:]+r.stderr[-1500:]) if r.returncode else '')
print(f"\n{ok} passed, {fail} failed")
raise SystemExit(1 if fail else 0)
