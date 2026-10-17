"""Live workforce × independent base productivity × dimensionless multiplier."""
import copy
import math
import json
from .cac_feeder import _channel_monthly, cac_auc_rollforward


def main():
    a={'nie_detail':{'workforce':{'mode':'roles','roles':[{'series_id':'sales','role':'Sales','count':2,'annual_comp':0,'hire_period':1}]}}}
    ch={'method':'fte_productivity','params':{},'avg_auc_per_customer':100,'driver_specs':{
        'ftes':{'source':'link','link':{'kind':'workforce_role_count','series_id':'sales','aggregation':'average'}},
        'per_fte':{'source':'entered','trajectory':'flat','value':2.75,'period':'month'}}}
    before=_channel_monthly(ch,12,assumptions=a)
    assert all(x['new_customers']==5.5 for x in before)
    ch['driver_specs']['productivity_multiplier']={'source':'entered','trajectory':'flat','value':1}
    unity=_channel_monthly(ch,12,assumptions=a)
    assert [r['new_customers'] for r in before]==[r['new_customers'] for r in unity]
    ch['driver_specs']['productivity_multiplier']={'source':'entered','trajectory':'explicit','cadence':'quarter','values':[0,.5,1,1.2]}
    rows=_channel_monthly(ch,12,assumptions=a)
    assert [r['new_customers'] for r in rows]==[0]*3+[2.75]*3+[5.5]*3+[6.6]*3
    # A multiplier is a level, never divided by its authored cadence.
    ch['driver_specs']['productivity_multiplier']={'source':'entered','trajectory':'explicit','cadence':'month','values':[.2,.5,1]*4}
    rows=_channel_monthly(ch,12,assumptions=a)
    a['nie_detail']['workforce']['roles'][0]['count']=4
    doubled=_channel_monthly(ch,12,assumptions=a)
    assert all(math.isclose(y['new_customers'],2*x['new_customers']) for x,y in zip(rows,doubled))
    assert all(r['operands']['per_fte']==2.75 for r in doubled)
    feed={'channels':[ch],'beginning_customers':0,'beginning_auc':0,'attrition_rate':0}
    m=cac_auc_rollforward(feed,12,12,assumptions=a);q=cac_auc_rollforward(feed,4,4,assumptions=a)
    assert m['monthly']==q['monthly']
    assert m['annual']==q['annual']
    ch['driver_specs']['productivity_multiplier']={'source':'entered','trajectory':'growth','base':.5,'growth_spec':{'rate':1,'period':'year','method':'step','anchor':'model_year'}}
    rows=_channel_monthly(ch,24,assumptions=a)
    assert rows[0]['new_customers']==5.5 and rows[12]['new_customers']==11
    # The existing public acquisition output and audit expose the same live equation.
    from .run_q import run_v2
    from .audit_workbook import _cac_monthly_acquisition_rows
    cfg=json.load(open('foundry/fixtures/core_bank_test_base.json'))
    cfg['assumptions']['nie_detail']=copy.deepcopy(a['nie_detail'])
    cfg['assumptions']['cac_feeds']={'Sales':copy.deepcopy(feed)}
    output=run_v2(cfg)
    assert output['customer_acquisition']['Sales']['monthly'][0]['new_cust']==5.5
    audit=_cac_monthly_acquisition_rows(cfg,36,12)
    assert audit[0][-1]==.5 and audit[0][15]==5.5
    for v in [-.1,float('inf'),float('nan')]:
        ch['driver_specs']['productivity_multiplier']={'source':'entered','trajectory':'flat','value':v}
        try:_channel_monthly(ch,12,assumptions=a)
        except ValueError:pass
        else:raise AssertionError('Invalid multiplier accepted')
    print('PASS default identity, live workforce, independent productivity, Flat/Growth/Explicit multiplier, monthly/quarterly equivalence and invalid inputs')


if __name__=='__main__':main()
