"""Surplus routing is authored policy; legacy inputs retain their economics."""
import copy,json,io
from pathlib import Path
from .engine_q_a import run_pf_a
from .engine_q_b import run_pf_b
from .fiw import build_fiw,diff_import
from .validate_q import validate_errors_v2

def main():
    base=json.loads(Path('foundry/fixtures/universal_template_bank.json').read_text())
    c=copy.deepcopy(base);c['target_state']['initial_capital']=30_000_000
    a=c['assumptions']
    for key in ('lending_products','deposit_products','obs_exposures','securities_afs','securities_htm','managed_securities_portfolios','capital_raises','scheduled_borrowings'):a[key]=[]
    for key in ('premises_equipment','intangibles','other_assets','other_liabilities','cash_yield','securities_yield','overhead_per_period','cash_target_pct_deposits'):a[key]=0
    for key in ('nie_detail','interest_balance_model','fixed_assets','other_liabilities_model','cost_pools','cac_feeds','fee_modules'):a.pop(key,None)
    c['pre_opening']={'expenses':[]}
    a['surplus_allocation_policy']='cash';r=run_pf_a(copy.deepcopy(c))
    assert r['bs']['cash'][0]==30_000_000 and r['bs']['sec'][0]==0
    assert all(v==0 for v in r['bs']['sec'])
    a['surplus_allocation_policy']='residual_securities';r=run_pf_a(copy.deepcopy(c))
    assert r['bs']['cash'][0]==0 and r['bs']['sec'][0]==30_000_000
    a.pop('surplus_allocation_policy');legacy=run_pf_a(copy.deepcopy(c))
    assert legacy==r
    # Authored securities are deducted first even in cash mode.
    a['surplus_allocation_policy']='cash';a['securities_afs']=[{'name':'Authored','opening':5_000_000,'yield_ann':0,'growth_per_period':0,'maturity_runoff_per_period':0}]
    r=run_pf_a(copy.deepcopy(c));assert r['bs']['afsBook'][0]==5_000_000
    assert r['bs']['cash'][0]==25_000_000 and r['bs']['sec'][0]==0
    # A funding deficit still borrows to cover explicit assets.
    a['securities_afs'][0]['opening']=35_000_000
    r=run_pf_a(copy.deepcopy(c));assert r['bs']['cash'][0]==0 and r['bs']['borrow'][0]==5_000_000
    # Explicit policy overrides module presence; authored portfolio remains intact.
    from .tests_managed_securities import _cfg
    managed=_cfg();managed['assumptions']['surplus_allocation_policy']='cash'
    rr=run_pf_a(copy.deepcopy(managed));assert all(v==0 for v in rr['bs']['sec'])
    managed['assumptions']['surplus_allocation_policy']='residual_securities'
    rr=run_pf_a(copy.deepcopy(managed));assert any(v>0 for v in rr['bs']['sec'])
    # FIW has an editable, round-trippable policy rather than an undocumented field.
    from openpyxl import load_workbook
    data,_=build_fiw(c);wb=load_workbook(io.BytesIO(data));sheet=wb['CONTROL']
    for row in sheet:
        if row[0].value=='Surplus allocation policy':row[1].value='residual_securities'
    buf=io.BytesIO();wb.save(buf)
    merged,_=diff_import(buf.getvalue(),c)
    assert merged['assumptions']['surplus_allocation_policy']=='residual_securities'
    bad=copy.deepcopy(base);bad['assumptions']['surplus_allocation_policy']='typo'
    assert any('surplus_allocation_policy' in str(e) for e in validate_errors_v2(bad))
    b=json.loads(Path('foundry/fixtures/parity/configs/pf_b_base.json').read_text())
    old=run_pf_b(copy.deepcopy(b));b['assumptions']['surplus_allocation_policy']='legacy_split'
    assert run_pf_b(copy.deepcopy(b))==old
    b['assumptions']['surplus_allocation_policy']='cash'
    assert any(v>0 for v in run_pf_b(copy.deepcopy(b))['bs']['cash'])
    b['assumptions']['surplus_allocation_policy']='residual_securities'
    assert all(v==0 for v in run_pf_b(copy.deepcopy(b))['bs']['cash'])
    print('PASS $30M cash/securities routing, legacy parity, explicit assets, shortfall borrowing, managed policy independence, FIW, validation')
if __name__=='__main__':main()
