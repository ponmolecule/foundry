"""Integration regressions: deposits, sweep fees, capacity, links, audit and legacy.
Run: python -m foundry.v2.tests_deposit_retention
"""
import copy
import json
import subprocess
from io import BytesIO
from openpyxl import load_workbook
from .engine_q_a import run_pf_a
from .deposit_balance import operand, prepare
from .validate_q import validate_errors_v2
from .parity import run_parity
from .run_q import run_v2
from .audit_workbook import calculation_audit_workbook, _product_rows


def flat(v): return {'source':'entered','trajectory':'flat','value':v}
def near(a,b): assert abs(a-b) < 1e-6, (a,b)

def fixture():
    c=json.load(open('foundry/fixtures/core_bank_test_base.json'))
    a=c['assumptions'];a.update(periods_per_year=12,n_periods=36)
    base=copy.deepcopy(a['deposit_products'][0]);base.update(opening_balance=0,growth_per_period=0,runoff_per_period=0,new_deposits_per_period=0,avg_maturity_m=0,fee_yield_ann=0,opex_pct_ann=0,opex_fixed_per_period=0,rate_type='fixed',rate_paid_ann=.12,fee_streams=[])
    for key in ('growth_q','runoff_q','new_deposits_q','overrides'):base.pop(key,None)
    a['deposit_products']=[dict(base,name='Category A',balance_mode='pool',retention_pool_id='pool',pool_share_spec=flat(.25),interest_balance_measure='period_end'),dict(base,name='Category B',balance_mode='pool',retention_pool_id='pool',pool_share_spec=flat(.75),interest_balance_measure='period_end')]
    a['deposit_retention_pools']=[{'id':'pool','balance_spec':flat(1_200_000),'retention_share_spec':flat(.5),'capacity_source':'entered','capacity_spec':flat(400_000),'sweep_fee_rate_spec':flat(.12),'sweep_fee_balance_measure':'period_end'}]
    return c


def main():
    # Exact legacy comparison executes the unmodified engine at the release parent.
    c=json.load(open('foundry/fixtures/core_bank_test_base.json'))
    old=subprocess.check_output(['git','show','1c3e67d:foundry/v2/engine_q_a.py'],text=True)
    ns={'__name__':'foundry.v2.engine_q_a','__package__':'foundry.v2'}
    exec(compile(old,'legacy_engine_q_a.py','exec'),ns)
    current=run_pf_a(copy.deepcopy(c));legacy=ns['run_pf_a'](copy.deepcopy(c))
    # r231b: compare the full output with nothing removed (r231 stripped an added 'index' field here,
    # which hid a change to every run fingerprint).
    assert current==legacy
    print('PASS exact legacy engine equivalence (full output, nothing removed)')
    c=fixture();assert not validate_errors_v2(c),validate_errors_v2(c)
    out=run_pf_a(copy.deepcopy(c));g=out['deposit_retention_pools']['pool']
    assert g['retainedBalance']==[400_000]*36 and g['sweptBalance']==[800_000]*36
    assert g['bindingLimit']==[2]*36 and g['sweepFee']==[8_000]*36
    deps=[p for p in out['products'] if p['family']=='deposit']
    assert [p['bal'][1] for p in deps]==[100_000,300_000]
    near(sum(p['fees'][0] for p in deps),8_000);near(sum(p['intExp'][0] for p in deps),4_000)
    assert out['bs']['deposits'][1]==400_000
    for q in range(36):near(sum(p['sweptBalance'][q] for p in deps)+out['bs']['deposits'][q+1],1_200_000)
    print('PASS shared allocation, on-book liabilities, fees charged once, interest basis')
    # Share limit / no sweep / zero cap / excess deductions.
    for cap,share,expected,binding in [(2_000_000,.5,600_000,1),(2_000_000,1,1_200_000,0),(0,.5,0,2)]:
        x=copy.deepcopy(c);x['assumptions']['deposit_retention_pools'][0].update(capacity_spec=flat(cap),retention_share_spec=flat(share))
        go=run_pf_a(x)['deposit_retention_pools']['pool'];near(go['retainedBalance'][0],expected);assert go['bindingLimit'][0]==binding
    x=copy.deepcopy(c);x['assumptions']['deposit_retention_pools'][0]['adjustments']=[{'direction':'deduct','balance_spec':flat(2_000_000)}]
    go=run_pf_a(x)['deposit_retention_pools']['pool'];assert go['availableBalance']==go['retainedBalance']==go['sweptBalance']==[0]*36
    # Independent budgets remain distinct.
    x=copy.deepcopy(c);a=x['assumptions'];a['deposit_products'][1]['retention_pool_id']='other';a['deposit_products'][0]['pool_share_spec']=flat(1);a['deposit_products'][1]['pool_share_spec']=flat(1)
    a['deposit_retention_pools'].append(dict(a['deposit_retention_pools'][0],id='other',capacity_spec=flat(200_000)))
    o=run_pf_a(x);assert o['deposit_retention_pools']['pool']['retainedBalance'][0]==400_000 and o['deposit_retention_pools']['other']['retainedBalance'][0]==200_000
    # Legacy unnamed fee streams on pool members do not make ordinary loans cyclic.
    x=fixture();x['assumptions']['deposit_products'][0]['fee_streams']=[{'name':'Service fee','basis':'flat','driver':{'source':'constant','trajectory':'flat','params':{}},'rate':{'behavior':'flat','params':{'amount':10}},'cost':{'kind':'none','params':{}}}]
    assert not validate_errors_v2(x),validate_errors_v2(x)
    run_pf_a(x)
    print('PASS binding limits, zero boundaries, independent pools')
    # Bank-state budget uses prior state and subtracts positive commitments.
    x=copy.deepcopy(c);x['assumptions']['deposit_retention_pools'][0].update(capacity_source='beginning_equity_budget',equity_budget={'target_leverage_spec':flat(.13),'liquidity_buffer_spec':flat(5_000_000),'operating_float_months_spec':flat(2),'capital_deduction_spec':flat(100_000)})
    o=run_pf_a(copy.deepcopy(x));go=o['deposit_retention_pools']['pool']
    near(go['beginningCapital'][0],max(0,o['bs']['equity'][0]-100_000))
    for q in range(1,36):near(go['beginningCapital'][q],max(0,o['bs']['equity'][q]-100_000))
    assert all(v>=5_000_000 for v in go['committedAssets'])
    print('PASS beginning-state equity budget, lagged commitments')
    # Derived activity + live migration schedule; no new copy of that share path.
    a=c['assumptions'];up=copy.deepcopy(a['obs_exposures'][0]);up['fee_streams']=[{'name':'Activity','quantity_series_id':'activity','basis':'transaction','driver':{'source':'constant','trajectory':'flat','params':{'flow_path':{'unit_kind':'money_flow','trajectory':'flat','period':'month','value':10_000_000}}},'rate':{'behavior':'flat','params':{'per_unit':0}},'cost':{'kind':'none','params':{}}},{'name':'Migration','quantity_series_id':'migration','basis':'transaction','driver':{'source':'stream_ref','ref':'Activity','trajectory':'derived','params':{'coefficient':{'kind':'pct','semantics':'share','trajectory':'explicit_schedule','period':'year','schedule':{'1':.25,'2':.5,'3':.75}}}},'rate':{'behavior':'flat','params':{'per_unit':0}},'cost':{'kind':'none','params':{}}}];a['obs_exposures']=[up]
    derived={'source':'derived','owner_module':'deposits','series_id':'balance','derived':{'kind':'activity_held','activity':{'source':'link','link':{'kind':'fee_quantity','series_id':'activity'}},'holding_days_spec':flat(3),'share_spec':{'source':'link','link':{'kind':'fee_share','series_id':'migration'}},'day_count':365}}
    a['deposit_retention_pools'][0]['balance_spec']=derived
    assert not validate_errors_v2(c),validate_errors_v2(c)
    o=run_pf_a(copy.deepcopy(c));go=o['deposit_retention_pools']['pool']
    for q,share in [(0,.25),(12,.5),(24,.75)]:near(go['sourceBalance'][q],10_000_000*12*3/365*share)
    renamed=copy.deepcopy(c);renamed['assumptions']['obs_exposures'][0]['name']='Renamed source';renamed['assumptions']['deposit_products'].reverse()
    assert run_pf_a(renamed)['deposit_retention_pools']==o['deposit_retention_pools']
    print('PASS linked activity / migration, annual boundary, stable identity on rename and reorder')
    # Direct levels do not roll forward or compound again.
    x=fixture();a=x['assumptions'];a.pop('deposit_retention_pools');a['deposit_products']=a['deposit_products'][:1];p=a['deposit_products'][0];p.update(balance_mode='level',ending_balance_spec={'source':'entered','trajectory':'explicit','cadence':'month','values':[0]*12+[100_000]*24,'extend':'error'})
    o=run_pf_a(x);d=next(p for p in o['products'] if p['family']=='deposit');assert d['bal'][1:13]==[0]*12 and d['bal'][13:]==[100_000]*24;near(d['intExp'][12],1_000)
    # Audit exposes pool math in native and public units; final workbook survives serialization.
    c=fixture();pub,raw=run_parity(c,include_exact=True)
    near(pub['deposit_retention_pools']['pool']['sweepFee'][0],8)
    assert pub['deposit_retention_pools']['pool']['bindingLimit'][0]==2
    rows=_product_rows(pub,36,exact=raw)
    assert any(r[2]=='sweepFee' and r[4][0]==8 for r in rows)
    result=run_v2(c);buf=BytesIO();calculation_audit_workbook(c,result).save(buf);buf.seek(0);wb=load_workbook(buf,data_only=True)
    assert 'All Series' in wb and 'Product Calculations' in wb
    assert any('deposit_retention_pools.pool.sweepFee' in str(cell.value) for row in wb['All Series'] for cell in row)
    # A linked lending flow can displace float without using its retained balance.
    x=fixture();a=x['assumptions'];loan=a['lending_products'][0]
    loan.update(balance_mode='funded_flow_level',balance_series_id='facility-flow',structure='revolving',mortgage_banking=None,funded_flow_driver={'source':'entered','flow_path':{'unit_kind':'money_flow','trajectory':'flat','period':'month','value':1_000_000}},term_days=12,day_count=365,reserve_share=0,target_retention_share=.5,interest_balance_measure='period_end')
    adjustment={'source':'derived','owner_module':'deposits','series_id':'float-adjustment','derived':{'kind':'activity_held','activity':{'source':'link','link':{'kind':'lending_funded_flow','series_id':'facility-flow'}},'holding_days_spec':flat(3),'day_count':365}}
    a['deposit_retention_pools'][0]['adjustments']=[{'direction':'deduct','balance_spec':adjustment}]
    assert not validate_errors_v2(x),validate_errors_v2(x)
    go=run_pf_a(x)['deposit_retention_pools']['pool'];near(go['availableBalance'][0],1_200_000-1_000_000*12*3/365)
    # Constant economics are cadence-equivalent; no multiplication by three twice.
    x=fixture();x['assumptions'].update(periods_per_year=4,n_periods=12)
    go=run_pf_a(x)['deposit_retention_pools']['pool'];near(go['sweepFee'][0],24_000)
    print('PASS linked lending displacement and monthly / quarterly fee periodization')
    print('PASS explicit timing, public conversion, exported audit reconciliation')
    for mutate in [lambda a:a['deposit_products'][0].update(pool_share_spec=flat(.5)),lambda a:a['deposit_retention_pools'][0].update(capacity_spec=flat(-1)),lambda a:a['deposit_retention_pools'][0].update(retention_share_spec=flat(float('nan'))),lambda a:a['deposit_retention_pools'].append(copy.deepcopy(a['deposit_retention_pools'][0])),lambda a:a['deposit_products'][0].update(growth_per_period=.1)]:
        x=fixture();mutate(x['assumptions']);assert validate_errors_v2(x)
    x=fixture();x['assumptions']['deposit_retention_pools'][0].update(capacity_source='beginning_equity_budget',equity_budget={'target_leverage_spec':flat(.13)});x['assumptions']['loan_allocation_groups']=[{'id':'cycle','cap_source':'deposit_book_end','cap_ratio':1}];assert any('cycle' in str(e) for e in validate_errors_v2(x))
    print('PASS fail-closed shares, negative / nonfinite operands, duplicate IDs, conflicting methods and cycles')

    # r231b: swept-balance fee basis. A growing swept balance distinguishes the bases (a constant one cannot).
    from foundry.v2.deposit_balance import allocate_period
    keys=('sourceBalance','balanceAdjustments','availableBalance','shareLimit','capacity','retainedBalance','sweptBalance','sweepFee','beginningSweptBalance','sweepFeeBasis','beginningCapital','committedAssets','bindingLimit')
    def pool(measure):
        return dict(source=[1000.,2000.,3000.],adjustments=[0.]*3,share=[.5]*3,capacity=None,budget=None,fee_rate=[.12]*3,
                    weights={0:[1.]*3},members=[0],fee_measure=measure,audit={k:[] for k in keys})
    for measure,expected in (('period_end',[5.,10.,15.]),('period_average',[2.5,7.5,12.5])):
        g=pool(measure);fees=[allocate_period(g,q,12)[0][2] for q in (1,2,3)]
        assert all(abs(a-b)<1e-9 for a,b in zip(fees,expected)),(measure,fees)
    x=fixture();x['assumptions']['deposit_retention_pools'][0]['sweep_fee_balance_measure']='period_begin';assert validate_errors_v2(x)
    print('PASS swept-balance fee on average from zero opening or period-end balance; invalid measure rejected')


if __name__=='__main__':main()
