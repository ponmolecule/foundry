"""Entered deposit pricing paths reuse Series; existing overrides remain last."""
import copy
import json
import unittest
from pathlib import Path
from .tests_r380_customer_deposits import config
from .lending_rates import prepare_fixed_deposit_rates
from .engine_q_a import run_pf_a, _deposit_rate
from .engine_q_b import run_pf_b
from .validate_q import validate_errors_v2

class DepositRateTests(unittest.TestCase):
    def test_schedule_overrides_and_interest(self):
        c=config();p=c['assumptions']['deposit_products'][0]
        p['rate_type']='fixed';p.pop('rate_paid_ann',None)
        p['rate_paid_ann_spec']={'source':'entered','trajectory':'explicit','cadence':'year','values':[.0125,.0095,.0065],'extend':'hold','resolution':'step'}
        p['overrides']={'rate_paid_ann':{'14':.01}}
        self.assertEqual(validate_errors_v2(c),[])
        r=next(x for x in run_pf_a(c)['products'] if x['family']=='deposit')
        self.assertEqual(r['rateQ'][:12],[1.25]*12)
        self.assertAlmostEqual(r['rateQ'][12],.95);self.assertAlmostEqual(r['rateQ'][13],1)
        self.assertAlmostEqual(r['rateQ'][14],.95);self.assertAlmostEqual(r['rateQ'][-1],.65)
        self.assertAlmostEqual(r['intExp'][12],(r['bal'][12]+r['bal'][13])/2*.0095/12)
        self.assertNotIn('_rate_paid_ann_path',p)

    def test_legacy_float_invalid_growth(self):
        legacy={'rate_type':'fixed','rate_paid_ann':.02,'overrides':{'rate_paid_ann':{'2':.01}}}
        saved=copy.deepcopy(legacy);prepare_fixed_deposit_rates([legacy],60,12)
        self.assertEqual(legacy,saved);self.assertEqual(_deposit_rate(legacy,1,lambda t:.03),.02);self.assertEqual(_deposit_rate(legacy,2,lambda t:.03),.01)
        p={'rate_type':'float','index_spread':.01,'rate_paid_ann_spec':{'source':'entered','trajectory':'explicit','values':[]}}
        prepare_fixed_deposit_rates([p],60,12);self.assertEqual(_deposit_rate(p,1,lambda t:.03),.04)
        for spec in [{'source':'entered','trajectory':'flat','value':-.01},{'source':'entered','trajectory':'flat','value':.31},{'source':'entered','trajectory':'flat','value':float('nan')},{'source':'entered','trajectory':'explicit','values':[]}]:
            with self.assertRaises(ValueError):prepare_fixed_deposit_rates([{'rate_type':'fixed','rate_paid_ann_spec':spec}],60,12)
            c=config();c['assumptions']['deposit_products'][0].update(rate_type='fixed',rate_paid_ann_spec=spec)
            self.assertTrue(any('deposit' in str(e) for e in validate_errors_v2(c)))
        p={'rate_type':'fixed','rate_paid_ann_spec':{'source':'entered','trajectory':'growth','base':.02,'growth_spec':{'rate':.1,'period':'year','method':'step','anchor':'model_year'}}}
        prepare_fixed_deposit_rates([p],24,12);self.assertAlmostEqual(_deposit_rate(p,13,lambda t:0),.022)

    def test_quarterly_both_profiles(self):
        for profile in ('a','b'):
            c=config(4) if profile=='a' else json.loads(Path('foundry/fixtures/parity/configs/pf_b_base.json').read_text())
            p=c['assumptions']['deposit_products'][0]
            p.update(rate_type='fixed',rate_paid_ann_spec={'source':'entered','trajectory':'explicit','cadence':'year','values':[.03,.02,.01],'extend':'hold','resolution':'step'})
            rows=(run_pf_a(c) if profile=='a' else run_pf_b(c))['products']
            r=next(x for x in rows if x['name']==p['name'])
            self.assertAlmostEqual(r['rateQ'][0],3);self.assertAlmostEqual(r['rateQ'][4],2);self.assertAlmostEqual(r['rateQ'][8],1)
