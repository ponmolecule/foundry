"""Cross-owner quantity dependency, cadence, identity and posting regressions."""
import copy,json
from .run_q import run_v2
from .fee_links import FeeLinkPlan
from .validate_q import validate_errors_v2
from .deposit_balance import source_catalog

def source(sid='tpv',values=(100000,200000,300000),price=.01):
    return {'name':'TPV','quantity_series_id':sid,'basis':'transaction','driver':{'source':'constant','trajectory':'explicit_schedule','params':{'flow_path':{'unit_kind':'money_flow','period':'month','trajectory':'explicit_schedule','schedule':{str(i+1):v for i,v in enumerate(values)}}}},'rate':{'behavior':'flat','params':{'pricing_basis':'pct_of_throughput','per_unit':price}},'cost':{'kind':'none','params':{}}}
def linked(sid='migrated',ref='tpv',share=.5):
    return {'name':'Migrated','quantity_series_id':sid,'basis':'transaction','driver':{'source':'fee_stream_quantity','ref':ref,'trajectory':'derived','params':{'coefficient':{'kind':'pct','semantics':'share','period':'month','trajectory':'flat','value':share}}},'rate':{'behavior':'flat','params':{'pricing_basis':'pct_of_throughput','per_unit':.02}},'cost':{'kind':'pct_of_throughput_opex','params':{'pct':.01}}}
def product(name,streams):return {'name':name,'call_report_line':'obs','_fee_product':True,'fee_streams':streams}
def fixture(ppy=12):
    c=json.load(open('foundry/fixtures/core_bank_test_base.json'));c['assumptions'].update(periods_per_year=ppy,n_periods=ppy*3,obs_exposures=[product('Consumer',[linked()]),product('Activity',[source()])]);return c

def quantities(r,sid):return r['fee_stream_quantities']['series'][sid]
def near(x,y):assert abs(x-y)<1e-8,(x,y)
def errors(c):
    e=validate_errors_v2(copy.deepcopy(c));return str(e)

def test_quantity_and_posting():
    c=fixture();r=run_v2(c)
    near(quantities(r,'tpv')[0],100000);near(quantities(r,'migrated')[0],50000) # stable quantity series retain native dollars
    p={x['name']:x for x in r['products']}
    near(p['Activity']['fees'][0],1);near(p['Consumer']['fees'][0],1)
    # Cost posts once under the consumer, source income is not copied into it.
    near(p['Consumer']['passCost'][0],.5)
    renamed=copy.deepcopy(c);renamed['assumptions']['obs_exposures'][1]['name']='Renamed owner';renamed['assumptions']['obs_exposures'][1]['fee_streams'][0]['name']='Renamed TPV';renamed['assumptions']['obs_exposures'].reverse()
    rr=run_v2(renamed);assert quantities(rr,'migrated')==quantities(r,'migrated')
    assert rr['financials']==r['financials']
    print('PASS consumer before source, quantity rather than revenue, one cost posting, stable rename/reorder')

def test_dag_and_rejections():
    c=fixture();a=c['assumptions'];root=source();middle=linked('middle','tpv',.5);last=linked('last','middle',.2)
    a['obs_exposures']=[product('A',[last,root]),product('B',[middle])]
    r=run_v2(c);near(quantities(r,'last')[0],10000)
    bad=copy.deepcopy(c);bad['assumptions']['obs_exposures'][0]['fee_streams'][1]['driver']={'source':'fee_stream_quantity','ref':'last','trajectory':'flat','params':{}}
    assert 'cycle' in errors(bad).lower()
    bad=fixture();bad['assumptions']['obs_exposures'][0]['fee_streams'][0]['driver']['ref']='deleted';assert 'missing' in errors(bad).lower()
    bad=fixture();bad['assumptions']['obs_exposures'][1]['fee_streams'][0]['quantity_series_id']='migrated';assert 'unique' in errors(bad).lower()
    bad=fixture();bad['assumptions']['obs_exposures'][0]['fee_streams'][0]['basis']='balance';assert 'stock' in errors(bad).lower()
    # Duplicate display names do not make stable references ambiguous.
    c=fixture();a=c['assumptions'];a['obs_exposures'].append(product('Other',[source('other',(1000,2000,3000))]));r=run_v2(c);near(quantities(r,'migrated')[0],50000)
    print('PASS true stream DAG across owners A → B → A; cycles/missing/duplicate-ID/unit mismatch rejected')

def test_cadence_and_zero():
    c=fixture(4);coef=c['assumptions']['obs_exposures'][0]['fee_streams'][0]['driver']['params']['coefficient'];coef.update(trajectory='explicit_schedule',schedule={'1':.1,'2':.2,'3':.3})
    r=run_v2(c);near(quantities(r,'tpv')[0],600000);near(quantities(r,'migrated')[0],140000)
    c=fixture();c['assumptions']['obs_exposures'][1]['fee_streams'][0]['timing']={'start_period':2,'end_period':2};r=run_v2(c)
    assert quantities(r,'migrated')[:3]==[0.,100000.,0.]
    print('PASS quarterly SUM(monthly TPV × monthly share), inactive sources zero only in their inactive periods')

def test_deposit_and_audit():
    c=fixture();ids={x['series_id'] for x in source_catalog(c['assumptions'])};assert 'migrated' in ids
    from .tests_deposit_retention import fixture as deposit_fixture,flat
    d=deposit_fixture();d['assumptions']['obs_exposures']=c['assumptions']['obs_exposures']
    pool=d['assumptions']['deposit_retention_pools'][0];pool['balance_spec']={'source':'derived','series_id':'deposit-source','owner_module':'deposits','derived':{'kind':'activity_held','activity':{'source':'link','link':{'kind':'fee_quantity','series_id':'migrated'}},'holding_days_spec':flat(3),'share_spec':flat(1),'day_count':365}}
    r=run_v2(d);assert r['deposit_retention_pools']['pool']['sourceBalance'][0]>0
    from .audit_workbook import _fee_quantity_unit_kinds,calculation_audit_workbook
    assert _fee_quantity_unit_kinds(c)['migrated']=='money'
    wb=calculation_audit_workbook(c,run_v2(c));assert wb.sheetnames
    print('PASS cross-product derived quantity remains available to deposits; audit units remain monetary')

if __name__=='__main__':
    for test in [test_quantity_and_posting,test_dag_and_rejections,test_cadence_and_zero,test_deposit_and_audit]:test()
