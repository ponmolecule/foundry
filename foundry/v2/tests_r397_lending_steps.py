"""r397: one lending step list, product type in the header, reporting category in step 06 (console) and an
engine check that the display-only product_type field changes nothing."""
import copy, json, subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];H=(ROOT/'web/console_v2.html').read_text()
ok=fail=0
def ck(name,cond,detail=''):
    global ok,fail
    print(('  PASS  ' if cond else '  FAIL  ')+name+('' if cond or not detail else '\n        '+str(detail)[:500]));ok+=bool(cond);fail+=not cond
ck('six fixed lending steps',"const LNC_STEPS=[['Balance',['balance','vol']],['Structure & timing',['timing','exp']],['Pricing',['pricing','price']],['Credit & allowance',['credit','cred']],['Costs & accounting',['costs','acct']],['Additional settings',['other','rep']]];" in H)
ck('the decorator canonicalises lending before the rail is built',"if(fam==='lending')lncCanon(card);const r=orig.apply(this,arguments);" in H)
ck('header names the product type for lending',"x.fam==='lending'&&!fee&&typeof lncTypeLine==='function'?esc(lncTypeLine(p))" in H)
ck('Add product records the choice',"obj.product_type=LNC_TYPE_OF_ADD[s.name]" in H and "btn._added.product_type='flow'" in H)
ck('reporting category offered for every lending product and deposits','aria-label="Loan reporting category"' in H and 'aria-label="Deposit reporting category"' in H)
ck('the engine never reads product_type','product_type' not in ''.join(p.read_text() for p in (ROOT/'foundry/v2').glob('*.py') if not p.name.startswith('tests_')))
from foundry.v2.run_q import run_v2
base=json.loads((ROOT/'foundry/fixtures/universal_template_bank.json').read_text())
typed=copy.deepcopy(base)
for p,k in zip(typed['assumptions']['lending_products'],['cre','ci','consumer','credit_card','mortgage','ci']):p['product_type']=k
a,b=run_v2(base),run_v2(typed)
def strip(r):
    r=copy.deepcopy(r);r.pop('run_hash',None);r.pop('config_hash',None);(r.get('engagement_echo') or {}).pop('config_hash',None)
    return json.dumps(r,sort_keys=True,default=str)
ck('every result is identical with and without product_type (only the configuration fingerprints differ)',strip(a)==strip(b))
r=subprocess.run(['node',str(ROOT/'web/tests_r397_lending_steps.cjs')],capture_output=True,text=True,cwd=str(ROOT),timeout=280)
ck('browser behaviour (node)',r.returncode==0,(r.stdout[-1500:]+r.stderr[-1500:]) if r.returncode else '')
print(f"\n{ok} passed, {fail} failed")
raise SystemExit(1 if fail else 0)
