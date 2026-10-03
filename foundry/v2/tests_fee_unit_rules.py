"""Shared legacy/planner unit rules, including stale flow metadata."""
from .income_modules import _fee_stream_quantity_kinds,fee_quantity_kind
from .fee_links import FeeLinkPlan

def test_shared_rules():
    cases=[('constant','money_flow',None,'money'),('constant',None,None,'native'),('customer_acquisition_count','money_flow',None,'count'),('unknown','money_flow',None,'native'),('own_balance',None,None,'money'),('managed_notional',None,None,'money'),('cost_pool',None,None,'money'),('customer_acquisition_count',None,'amount_per_source_unit','money')]
    for source,unit,coefficient,expected in cases:
        st={'name':'Root','basis':'transaction','quantity_series_id':'root','driver':{'source':source,'params':{'flow_path':{'unit_kind':unit},'coefficient':{'kind':coefficient}}}}
        consumer={'name':'Linked','basis':'transaction','driver':{'source':'fee_stream_quantity','ref':'root'}}
        plan=FeeLinkPlan({'obs_exposures':[{'fee_streams':[st]},{'fee_streams':[consumer]}]})
        assert _fee_stream_quantity_kinds([st])[0]==plan.kinds[(0,0)]==plan.kinds[(1,0)]==expected
    for basis,expected in [('balance','money'),('account','count'),('flat','native'),('event','native')]:
        assert fee_quantity_kind({'basis':basis})==expected
    count={'name':'Count','basis':'account'}
    local={'name':'Share','basis':'transaction','driver':{'source':'stream_ref','ref':'Count'}}
    assert _fee_stream_quantity_kinds([local,count])=={0:'count',1:'count'}
    print('PASS shared legacy/planner rules, stale nonconstant flow tags, coefficient precedence and named count references')

if __name__=='__main__':test_shared_rules()
