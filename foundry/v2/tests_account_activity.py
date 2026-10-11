"""Population identities, cadence invariance, live links and unchanged legacy results."""
import copy,json,math
from .account_activity import resolve,catalog,monthly_fee
from .income_modules import product_fee_streams_q,fee_stream_q
from .run_q import run_v2
from .validate_q import validate_errors_v2

def feed():
    return {'series_id':'auc','customer_count_series_id':'customers','beginning_customers':1000,'beginning_auc':0,'attrition_rate':0,
            'activity_series_ids':{'new_customers':'new','lost_customers':'lost'},
            'channels':[{'name':'Acquisition','method':'explicit','params':{'new_customers_by_year':[120]},'avg_auc_per_customer':0,'opening_customers':1000,'activity_series_ids':{'new_customers':'chnew','lost_customers':'chlost'}}]}
def adoption(mode='target_share'):
    x={'id':'sub','name':'Subscribers','customer_source_id':'customers','opening_subscribers':600,'mode':mode,'exit_assumption':'proportional_customer_attrition','series_ids':{'count':'active','additions':'adds','cancellations':'closes','exits':'exits'}}
    if mode=='target_share':x['target_share']={'trajectory':'flat','value':.6,'period':'month'}
    else:
        for k,v in [('new_customer_adoption',.6),('existing_customer_adoption',.1),('closure_probability',.12)]:x[k]={'trajectory':'flat','value':v,'period':'year' if k=='closure_probability' else 'month'}
    return x

def stream(name,basis,ref,price=0,cost=None):
    return {'name':name,'quantity_series_id':name,'basis':basis,'driver':{'source':'account_activity','ref':ref,'trajectory':'flat','params':{}},'rate':{'behavior':'flat','params':{'unit_fee':{'value':price,'period':'month'}} if basis=='account' else {'per_unit':price,'pricing_basis':'per_unit'}},'cost':cost or {'kind':'none','params':{}}}

def main():
    checks=0
    def ck(label,condition):
        nonlocal checks
        assert condition,label;checks+=1;print('PASS',label)
    def reject(label,fn):
        try:fn()
        except (ValueError,TypeError):ck(label,True);return
        raise AssertionError(label)
    a={'cac_feeds':{'Feed':feed()},'account_adoption':[adoption()]}
    m,am=resolve(a,12,12);q,aq=resolve(a,4,4)
    ck('gross customer adds are live monthly flows',m['new']['values']==[10.]*12)
    ck('channel new / lost attribution',m['chnew']['values']==[10.]*12 and m['chlost']['values']==[0.]*12)
    ck('quarterly sums flows, preserves EOP counts',q['new']['values']==[30.]*4 and q['active']['values'][0]==618)
    ck('target additions reconcile existing book',m['adds']['values'][0]==6 and am['sub']['monthly'][0]['ending']==606)
    b=copy.deepcopy(a);b['account_adoption'][0]['target_share']={'trajectory':'explicit','cadence':'month','values':[.6,.5]+[.5]*10}
    r,ar=resolve(b,12,12);ck('falling share publishes cancellations',r['closes']['values'][1]==96 and r['adds']['values'][1]==0)
    b=copy.deepcopy(a);b['account_adoption'][0]=adoption('gross_flows');b['cac_feeds']['Feed']['channels']=[]
    b['account_adoption'][0]['existing_customer_adoption']['value']=0
    r,ar=resolve(b,12,12);ck('annual 12% closes 12% over a year',abs(r['active']['values'][-1]-528)<1e-8)
    b['account_adoption'][0]['existing_customer_adoption']['value']=1
    r,ar=resolve(b,12,12);row=ar['sub']['monthly'][0]
    ck('closed subscribers cannot reopen in same month',abs(row['additions']-400)<1e-8 and row['ending']<1000)
    b=copy.deepcopy(a);b['cac_feeds']['Feed']['driver_specs']={'attrition_rate':{'mode':'flat','value':.1,'period':'month'}}
    r,ar=resolve(b,12,12);ck('customer exits precede adoption',ar['sub']['monthly'][0]['customer_exits']==60 and ar['sub']['monthly'][0]['additions']==6)
    b=copy.deepcopy(a);b['account_adoption'][0]['opening_subscribers']=1001
    reject('reject impossible opening subscribers',lambda:resolve(b,12,12))
    b=copy.deepcopy(a);b['account_adoption'][0]['target_share']['value']=float('nan')
    reject('reject nonfinite adoption',lambda:resolve(b,12,12))
    b=copy.deepcopy(a);b['account_adoption'][0]['target_share'].pop('period')
    reject('require explicit adoption path period',lambda:resolve(b,12,12))
    b=copy.deepcopy(a);b['cac_feeds']['Feed']['intra_period_path']='straight_line'
    reject('reject implied losses masquerading as gross',lambda:resolve(b,12,12))
    servicing=stream('servicing','account','active',cost={'kind':'per_account','params':{'cost_per_account':10,'period':'month'}})
    product={'fee_streams':[servicing,stream('origination','transaction','adds',cost={'kind':'per_unit','params':{'cost_per_unit':175}})]}
    monthly=[product_fee_streams_q(product,i+1,{'account_activity':m},12) for i in range(12)]
    quarterly=[product_fee_streams_q(product,i+1,{'account_activity':q},4) for i in range(4)]
    ck('account servicing and acquisition costs are cadence invariant',abs(sum(x[1] for x in monthly)-sum(x[1] for x in quarterly))<1e-8)
    ck('month1 servicing plus origination posts once',monthly[0][1]==6060+1050)
    constant={'fee_streams':[dict(servicing,driver={'source':'constant','trajectory':'flat','params':{'base':600}})]}
    ck('600 accounts at $10/month is $72000 at both cadences',sum(product_fee_streams_q(constant,i+1,{},12)[1] for i in range(12))==72000 and sum(product_fee_streams_q(constant,i+1,{},4)[1] for i in range(4))==72000)
    # A linked flow chain: population -> spend -> percent interchange.
    active=stream('activeSource','account','active');spend={'name':'spend','quantity_series_id':'spend','basis':'transaction','driver':{'source':'stream_ref','ref':'activeSource','trajectory':'derived','params':{'coefficient':{'kind':'amount_per_source_unit','value':23000,'period':'month','trajectory':'flat'}}},'rate':{'behavior':'flat','params':{'pricing_basis':'pct_of_throughput','per_unit':.022}},'cost':{'kind':'none','params':{}}}
    p={'fee_streams':[active,spend]}
    rm=[product_fee_streams_q(p,i+1,{'account_activity':m},12)[0] for i in range(12)]
    rq=[product_fee_streams_q(p,i+1,{'account_activity':q},4)[0] for i in range(4)]
    ck('linked spend and interchange sum monthly products',abs(sum(rm)-sum(rq))<1e-7)
    ck('month1 interchange hand check',abs(rm[0]-606*23000*.022)<1e-8)
    # Cross-product parent local names must resolve in the parent's owner, not the consumer's.
    from .fee_links import FeeLinkPlan
    active=stream('Source','account','active');spend['driver']['ref']='Source'
    child=copy.deepcopy(spend);child.update(name='child',quantity_series_id='child');child['driver']={'source':'fee_stream_quantity','ref':'spend','trajectory':'flat','params':{}}
    child['rate']['params']['per_unit']=.01
    products=[{'fee_streams':[active,spend]},{'fee_streams':[stream('Source','account','active'),child]}]
    owners={st['quantity_series_id']:p['fee_streams'] for p in products for st in p['fee_streams']}
    # Give the unrelated duplicate display name its own ID.
    products[1]['fee_streams'][0]['quantity_series_id']='otherSource'
    owners={st['quantity_series_id']:p['fee_streams'] for p in products for st in p['fee_streams']}
    linked_a=dict(a,obs_exposures=products)
    contexts={(pi,i+1):{'account_activity':q,'capture_stream_qty':{},'capture_stream_economics':{},'activity_stream_owners':owners} for pi in range(2) for i in range(4)}
    shared={}
    for c in contexts.values():c['capture_stream_qty']=shared
    totals=FeeLinkPlan(linked_a).evaluate(contexts,4,4)
    ck('cross-product monthly replay respects parent ownership',abs(totals[(1,1)][0]-sum(m['active']['values'][:3])*23000*.01)<1e-7)
    from .source_catalog import catalog as source_catalog
    ck('purchase volume offered to funded-flow lending',any(x['series_id']=='spend' and 'lending_funded_flow' in x['consumers'] for x in source_catalog(linked_a)))
    from .account_activity import expense_cycle
    cyclic=copy.deepcopy(linked_a)
    cyclic['cac_feeds']['Feed']['channels'][0]['driver_specs']={'spend':{'source':'link','link':{'kind':'operating_expense_category','series_id':'acquisition-cost'}}}
    ck('expense cycle detected through cross-product activity descendants',expense_cycle(cyclic,{'series_id':'acquisition-cost'},'child') and not expense_cycle(cyclic,{'series_id':'other-cost'},'child'))
    # Servicing cost and an independently scheduled revenue price both use monthly products.
    varying=copy.deepcopy(servicing);varying['cost']['params']['factor_path']={'trajectory':'explicit_schedule','period':'month','schedule':{str(i+1):10+i for i in range(12)}}
    mm=[product_fee_streams_q({'fee_streams':[varying]},i+1,{'account_activity':m},12)[1] for i in range(12)]
    qq=[product_fee_streams_q({'fee_streams':[varying]},i+1,{'account_activity':q},4)[1] for i in range(4)]
    ck('varying monthly account costs aggregate products, not averages multiplied',abs(sum(mm)-sum(qq))<1e-8)
    avg=copy.deepcopy(servicing);avg['driver']['measure']='period_average'
    ck('account average measure includes explicit opening stock',product_fee_streams_q({'fee_streams':[avg]},1,{'account_activity':m},12)[1]==6030)
    share=copy.deepcopy(servicing);share['driver']={'source':'constant','trajectory':'flat','params':{'base':1000,'share_spec':{'trajectory':'flat','value':.6,'period':'month'}}}
    ck('Account participation share with monthly servicing',product_fee_streams_q({'fee_streams':[share]},1,{},4)[1]==18000)
    cap={};econ={};product_fee_streams_q({'fee_streams':[servicing]},1,{'account_activity':q,'capture_stream_qty':cap,'capture_stream_economics':econ},4)
    ck('audit cost factor reconciles quarter expense',abs(econ['servicing']['quantity'][0]*econ['servicing']['effective_cost_factor'][0]-econ['servicing']['fee_product_cost'][0])<1e-8)
    revenue_cost=copy.deepcopy(servicing);revenue_cost['rate']={'behavior':'flat','params':{'unit_fee':{'value':10,'period':'month'}}};revenue_cost['cost']={'kind':'pct_of_revenue_opex','params':{'pct':.1}}
    econ={};inc,cost=product_fee_streams_q({'fee_streams':[revenue_cost]},1,{'account_activity':q,'capture_stream_economics':econ},4)
    ck('quarterly percent-of-revenue cost factor retains percentage units',abs(econ['servicing']['effective_cost_factor'][0]-.1)<1e-9 and abs(cost-inc*.1)<1e-9)
    from .opex_extensions import resolve_linked_components, linked_component_amount
    cat={'linked_components':[{'driver':'formula_driver','factors':[{'kind':'linked','source':'account_activity','series_id':'adds'},{'kind':'entered','spec':{'trajectory':'flat','value':175}}]}]}
    comp=resolve_linked_components(cat,4,4,assumptions=a)[0]
    ck('Opex consumes live additions as event counts',linked_component_amount(comp,0,{'account_activity':q})==3150)
    invalid=copy.deepcopy(a);invalid['account_adoption'][0]['new_customer_adoption']={'value':.1}
    reject('methods cannot be combined silently',lambda:resolve(invalid,12,12))
    invalid=copy.deepcopy(a);invalid['account_adoption'][0]['series_ids']['count']='adds'
    reject('duplicate source IDs rejected',lambda:resolve(invalid,12,12))
    b=copy.deepcopy(a);b['cac_feeds']['Feed']['channels'][0]['params']['new_customers_by_year']=[240]
    updated,_=resolve(b,12,12);ck('customer assumptions propagate into acquisition costs',product_fee_streams_q(product,1,{'account_activity':updated},12)[1]==6120+2100)
    cfg=json.load(open('foundry/fixtures/core_bank_test_base.json'));cfg['assumptions'].update(a);cfg['assumptions']['obs_exposures'][0]['fee_streams']=product['fee_streams']
    errs=validate_errors_v2(cfg);ck('public configuration validates',not errs)
    cycle_cfg=copy.deepcopy(cfg)
    cycle_cfg['assumptions']['cac_feeds']['Feed']['channels'][0]['driver_specs']={'spend':{'source':'link','link':{'kind':'operating_expense_category','series_id':'acquisition-cost'}}}
    cycle_cfg['assumptions'].setdefault('nie_detail',{})['categories']=[{'name':'Acquisition cost','series_id':'acquisition-cost','linked_components':[{'driver':'formula_driver','factors':[{'kind':'linked','source':'fee_stream_quantity','series_id':'origination'},{'kind':'entered','spec':{'trajectory':'flat','value':175}}]}]}]
    ck('public validation rejects indirect activity expense cycles',any('circular account activity' in str(x) for x in validate_errors_v2(cycle_cfg)))
    res=run_v2(cfg);ck('public output publishes stable-ID count audit',bool(res['account_activity']['series']['active']['values']))
    from .audit_workbook import calculation_audit_workbook
    import io,openpyxl
    wb=calculation_audit_workbook(cfg,res)
    ck('audit has Account Activity and named source', 'Account Activity' in wb.sheetnames and any('Active subscribers' in str(row[1].value) for row in wb['Account Activity'].iter_rows()))
    print(checks,'checks passed')
if __name__=='__main__':main()
