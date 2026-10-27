import copy
import json
import unittest
from foundry.v2.income_modules import fee_stream_q
from foundry.v2.engine_q_a import run_pf_a
from foundry.v2.run_q import _ftp_view
from foundry.v2.account_activity import monthly_fee


def stream(measure=None):
    driver={'source':'own_balance','trajectory':'flat','params':{}}
    if measure: driver['measure']=measure
    return {'name':'Fraud','basis':'balance','driver':driver,
            'rate':{'behavior':'flat','params':{'rate_ann':0}},
            'cost':{'kind':'pct_of_balance_opex','params':{'pct':.001}},
            'timing':{'start_period':1}}

class ProductBalanceCost(unittest.TestCase):
    def test_end_and_legacy_average(self):
        ctx={'own_balance':500_000,'own_balance_end':1_000_000}
        self.assertAlmostEqual(fee_stream_q(stream('period_end'),1,ctx,12)[1],1000/12)
        self.assertAlmostEqual(fee_stream_q(stream(),1,ctx,12)[1],500/12)
        self.assertAlmostEqual(fee_stream_q(stream('period_end'),1,ctx,4)[1],250)
        with self.assertRaises(ValueError): fee_stream_q(stream('period_end'),1,{'own_balance':1},12)
        s=stream();s['driver']['source']='constant'
        with self.assertRaises(ValueError): fee_stream_q(s,1,ctx,12)

    def test_full_posting_and_product_contribution(self):
        with open('foundry/fixtures/core_bank_test_base.json', encoding='utf-8') as f: cfg=json.load(f)
        a=cfg['assumptions'];a['periods_per_year']=12;a['n_periods']=12
        p=a['deposit_products'][0];p['fee_streams']=[stream('period_end')]
        before=copy.deepcopy(cfg);before['assumptions']['deposit_products'][0]['fee_streams']=[]
        result=run_pf_a(copy.deepcopy(cfg));baseline=run_pf_a(before)
        product=next(x for x in result['products'] if x['name']==p['name'] and x['family']=='deposit')
        base_product=next(x for x in baseline['products'] if x['name']==p['name'] and x['family']=='deposit')
        self.assertAlmostEqual(product['passCost'][0], product['bal'][1]*.001/12)
        self.assertAlmostEqual(result['is']['feeOpex'][0]-baseline['is']['feeOpex'][0],product['passCost'][0])
        view=_ftp_view(result,cfg,12);baseview=_ftp_view(baseline,before,12)
        row=next(x for x in view['rows'] if x['name']==p['name']); brow=next(x for x in baseview['rows'] if x['name']==p['name'])
        self.assertAlmostEqual(row['opex']-brow['opex'],round(sum(product['passCost']),2),delta=.02)
        self.assertTrue(view['reconciliation_ok'])

    def test_profile_monthly_replay_uses_each_month_end(self):
        operands={'own_balance':[50_000,150_000,250_000],
                  'own_balance_end':[100_000,200_000,300_000],
                  'distributed_balance':[0,0,0], 'product_funded_flow':[0,0,0]}
        _, cost=monthly_fee(stream('period_end'),1,{'_profile_monthly_operands':operands},4,fee_stream_q,force=True)
        self.assertAlmostEqual(cost,600_000*.001/12)

if __name__=='__main__':unittest.main()
