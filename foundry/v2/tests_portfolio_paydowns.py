"""Independent portfolio paydowns, validation, expense timing and public audit."""
import copy
import json
import math
from .tests_repayment_profiles import product
from .loan_balance import normalize_linked_loan_balance
from .repayment_profiles import resolve
from .engine_q_a import run_pf_a
from .run_q import run_v2
from .validate_q import validate_errors_v2
from .audit_workbook import calculation_audit_workbook, _opex_component_detail_rows


def setup():
    c=json.load(open('foundry/fixtures/core_bank_test_base.json'))
    a=c['assumptions'];a.update(periods_per_year=12,n_periods=36)
    p=product();p.update(name='Scheduled portfolio',source_catalog_id='scheduled',reserve_rate_pct_bal=.007)
    p['repayment_profile'].update(repayment_basis='portfolio_scheduled',loss_rate_spec={'source':'entered','trajectory':'flat','value':.04})
    flows=[0,27600,55200,96600,138000,179400]+[179400]*30
    p['funded_flow_driver']['flow_path'].update(trajectory='explicit_schedule',schedule={str(i+1):v for i,v in enumerate(flows)})
    a['lending_products']=[p]
    a['nie_detail']={'enabled':True,'fdic_bp_ann':0,'categories':[{'name':'Balance expense','series_id':'balance-expense','fixed_spec':{'trajectory':'flat','value':0,'period':'month'},'linked_components':[{'driver':'formula_driver','component_id':'balance-rate','accrual_cadence':'monthly','factors':[{'kind':'linked','source':'catalog_quantity','series_id':'lending.scheduled.balance','measure':'period_begin'},{'kind':'entered','op':'multiply','display':'percent','periodized':True,'spec':{'trajectory':'flat','value':.005,'period':'year'}}]}]}]}
    return c,flows


def main():
    c,flows=setup();p=c['assumptions']['lending_products'][0]
    assert not validate_errors_v2(c),validate_errors_v2(c)
    m=resolve(p,c['assumptions'],36,12,normalize_linked_loan_balance(p,c['assumptions']))
    balance=0
    for i,row in enumerate(m['monthly']):
        pay=flows[i-2] if i>=2 else 0
        co=balance*.04/12
        assert math.isclose(row['repayments'],pay,abs_tol=1e-8)
        assert math.isclose(row['charge_offs'],co,abs_tol=1e-8)
        balance+=flows[i]-pay-co
        assert math.isclose(row['ending'],balance,abs_tol=1e-8)
        assert math.isclose(row['allowance'],balance*.007,abs_tol=1e-8)
    assert math.isclose(m['ending_balance'][3],151432.30666666667)
    q=resolve(p,c['assumptions'],12,4,normalize_linked_loan_balance(p,c['assumptions']))
    for i in range(12):
        assert math.isclose(q['ending_balance'][i],m['ending_balance'][3*i+2])
        assert math.isclose(q['repayments'][i],sum(m['repayments'][3*i:3*i+3]))
    # Generic curves and opening schedules are not tied to a particular delay.
    other=copy.deepcopy(p);other['repayment_profile']['repayment_fractions']=[.2,.3,.5]
    other['repayment_profile']['loss_rate_spec']['value']=0
    x=resolve(other,c['assumptions'],36,12,normalize_linked_loan_balance(other,c['assumptions']))
    assert x['repayments'][3]==sum(flows[3-j]*v for j,v in enumerate([.2,.3,.5]))
    opened=copy.deepcopy(other);opened['opening_balance']=500
    opened['repayment_profile']['opening_cohorts']=[{'id':'seasoned','original_principal':1000,'outstanding':500,'repaid_to_date':500,'charged_off_to_date':0,'next_age_month':2}]
    x=resolve(opened,c['assumptions'],36,12,normalize_linked_loan_balance(opened,c['assumptions']))
    assert x['repayments'][0]==500
    # Full public engine and monthly-rate exposure aggregation.
    out=run_pf_a(c);blank=copy.deepcopy(c);blank['assumptions']['nie_detail']['categories'][0]['linked_components']=[]
    base=run_pf_a(blank)
    expenses=[v-b for v,b in zip(out['is']['otherOpex'],base['is']['otherOpex'])]
    assert math.isclose(expenses[2],11.5,abs_tol=1e-7)
    qc=copy.deepcopy(c);qc['assumptions'].update(periods_per_year=4,n_periods=12)
    qo=run_pf_a(qc);qb=copy.deepcopy(qc);qb['assumptions']['nie_detail']['categories'][0]['linked_components']=[];qb=run_pf_a(qb)
    for i,(v,b) in enumerate(zip(qo['is']['otherOpex'],qb['is']['otherOpex'])):
        assert math.isclose(v-b,sum(expenses[3*i:3*i+3]),abs_tol=1e-7)
    # A monthly-varying rate must multiply each month's exposure before summing.
    rate=c['assumptions']['nie_detail']['categories'][0]['linked_components'][0]['factors'][1]
    rate.update(periodized=False,rate_period='year',spec={'source':'entered','trajectory':'explicit','cadence':'month','values':[.001,.002,.003]*12})
    varied=run_pf_a(c);qc=copy.deepcopy(c);qc['assumptions'].update(periods_per_year=4,n_periods=12);vq=run_pf_a(qc)
    for i in range(12):
        assert math.isclose(vq['is']['otherOpex'][i]-qb['is']['otherOpex'][i],sum(varied['is']['otherOpex'][j]-base['is']['otherOpex'][j] for j in range(3*i,3*i+3)),abs_tol=1e-7)
    public=run_v2(qc);wb=calculation_audit_workbook(qc,public)
    assert 'Repayment Monthly' in wb.sheetnames
    assert any('Repayment basis' in row for row in wb['Repayment Monthly'].values)
    assert not any(str(row[-1]).startswith('ERROR:') for row in _opex_component_detail_rows(qc,public,12,4))
    # Live upstream accounts -> monetary activity -> portfolio funding, no pasted balances.
    from .tests_account_activity import feed,adoption,stream
    linked,_=setup();la=linked['assumptions'];lp=la['lending_products'][0]
    f=feed();f['channels'][0]['params']['new_customers_by_year']=[120]*3
    la['cac_feeds']={'Acquisition':f};la['account_adoption']=[adoption()]
    active=stream('Active','account','active')
    purchases={'name':'Purchases','quantity_series_id':'purchases','basis':'transaction','driver':{'source':'stream_ref','ref':'Active','trajectory':'derived','params':{'coefficient':{'kind':'amount_per_source_unit','value':23000,'period':'month','trajectory':'flat'}}},'rate':{'behavior':'flat','params':{'per_unit':.022,'pricing_basis':'pct_of_throughput'}},'cost':{'kind':'pct_of_throughput_opex','params':{'pct':.0039}}}
    la['obs_exposures']=[{'name':'Activity','call_report_line':'obs','fee_streams':[active,purchases]}]
    lp['funded_flow_driver']={'source':'fee_stream_quantity','series_id':'purchases','input_stage':'funded_volume','start_period':1,'ramp_periods':1,'take_up_share':1}
    assert not validate_errors_v2(linked),validate_errors_v2(linked)
    live=run_pf_a(linked)['repayment_profiles'][0]['profile']
    assert live['monthly_funded_volume'][0]==606*23000
    changed=copy.deepcopy(linked);changed['assumptions']['account_adoption'][0]['target_share']['value']=.3
    changed=run_pf_a(changed)['repayment_profiles'][0]['profile']
    assert changed['monthly_funded_volume'][0]==303*23000
    assert math.isclose(changed['ending_balance'][3],live['ending_balance'][3]/2)
    # Impossible runoff is rejected, never turned into negative assets or clipped payments.
    bad=copy.deepcopy(p);bad['funded_flow_driver']['flow_path']['schedule']={str(i+1):(1000 if i==0 else 0) for i in range(36)}
    try:resolve(bad,{},36,12,normalize_linked_loan_balance(bad,{}))
    except ValueError as e:assert 'exceed available principal' in str(e)
    else:raise AssertionError('Expected impossible portfolio rejection')
    for field,value in [('allocation_group_id','cap'),('target_retention_share',.8),('allowance_mode','profile_expected_loss')]:
        bad=copy.deepcopy(p);bad[field]=value
        try:normalize_linked_loan_balance(bad,{})
        except ValueError:pass
        else:raise AssertionError('Expected incompatible option rejection: '+field)
    print('PASS source recurrence, generic curves, opening schedule, monthly/quarterly accrual, varying rates, public audit, impossible balances and incompatible settings')


if __name__=='__main__':main()
