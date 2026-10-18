"""Live count-flow dependencies reuse Pool × conversion, independent of channel order."""
import copy,json,math
from .cac_feeder import cac_auc_rollforward
from .validate_q import validate_errors_v2
from .run_q import run_v2
from .audit_workbook import _cac_monthly_acquisition_rows


def linked(sid,ref,rate):
    return {'name':sid,'method':'pool_conversion','derived_series_ids':{'new_customers':sid},'driver_specs':{
        'pool':{'source':'link','link':{'kind':'acquisition_channel_new_customers','series_id':ref,'aggregation':'sum'}},
        'conversion_rate':{'source':'entered','trajectory':'flat','value':rate}}}


def main():
    direct={'name':'Direct','method':'fte_productivity','derived_series_ids':{'new_customers':'direct-new'},'driver_specs':{
        'ftes':{'source':'link','link':{'kind':'workforce_role_count','series_id':'sales'}},
        'per_fte':{'source':'entered','trajectory':'flat','value':2.75,'period':'month'},
        'productivity_multiplier':{'source':'entered','trajectory':'explicit','cadence':'month','values':[0,.5,1]*12}}}
    referral=linked('referral-new','direct-new',.25)
    c=json.load(open('foundry/fixtures/core_bank_test_base.json'));a=c['assumptions']
    a['nie_detail']={'workforce':{'mode':'roles','roles':[{'series_id':'sales','role':'Sales','count':2,'annual_comp':0,'hire_period':1}]}}
    feed={'channels':[referral,direct],'beginning_customers':0,'beginning_auc':0,'attrition_rate':0}
    a['cac_feeds']={'Practices':feed}
    assert not validate_errors_v2(c),validate_errors_v2(c)
    m=cac_auc_rollforward(feed,36,12,assumptions=a);q=cac_auc_rollforward(feed,12,4,assumptions=a)
    for row in m['monthly']:
        emr,src=row['channels']
        assert emr['new_customers']==src['new_customers']*.25
        assert row['new_cust']==src['new_customers']*1.25
    assert m['monthly']==q['monthly'] and m['annual']==q['annual']
    # Stable IDs survive names/order changes, including consumer before its source.
    feed['channels'].reverse();direct['name']='Renamed source';referral['name']='Renamed consumer'
    reordered=cac_auc_rollforward(feed,36,12,assumptions=a)
    assert reordered['customer_end_by_month']==m['customer_end_by_month']
    a['nie_detail']['workforce']['roles'][0]['count']=4
    doubled=cac_auc_rollforward(feed,36,12,assumptions=a)
    assert all(math.isclose(y['new_cust'],2*x['new_cust']) for x,y in zip(m['monthly'],doubled['monthly']))
    # A chain may cross feeds, but still reads monthly count flows, not cumulative counts.
    third=linked('third','referral-new',.4);a['cac_feeds']['Partners']={'channels':[third]}
    external=cac_auc_rollforward(a['cac_feeds']['Partners'],36,12,assumptions=a)
    assert all(math.isclose(x['new_cust'],y['channels'][1]['new_customers']*.4) for x,y in zip(external['monthly'],doubled['monthly']))
    public=run_v2(c)
    assert public['customer_acquisition']['Practices']['monthly'][1]['new_cust']==6.875
    audit=_cac_monthly_acquisition_rows(c,36,12)
    assert any(row[5]=='Renamed consumer' and row[2]==2 and row[7]==5.5 and row[15]==1.375 for row in audit)
    original=copy.deepcopy(a)
    # A -> B -> A; self; missing source; ambiguous identities.
    for case in ['cycle','self','missing','duplicate']:
        bad=copy.deepcopy(original);f=bad['cac_feeds']['Practices'];source,consumer=f['channels']
        if case=='cycle':source.update(method='pool_conversion',driver_specs=linked('x','referral-new',1)['driver_specs'])
        if case=='self':consumer['driver_specs']['pool']['link']['series_id']='referral-new'
        if case=='missing':consumer['driver_specs']['pool']['link']['series_id']='absent'
        if case=='duplicate':f['channels'].append(copy.deepcopy(source))
        try:cac_auc_rollforward(f,36,12,assumptions=bad)
        except ValueError as e:
            assert ('Circular' in str(e) if case in ['cycle','self'] else 'missing or ambiguous' in str(e)),str(e)
        else:raise AssertionError('Expected rejection: '+case)
    print('PASS live channel links, monthly/quarterly equivalence, rename/reorder, multihop/cross-feed dependencies, public audit, missing/ambiguous/self/cyclic source rejection')


if __name__=='__main__':main()
