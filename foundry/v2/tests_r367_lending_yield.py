import copy
import unittest
from .tests_linked_loan_balance import _cfg
from .engine_q_a import run_pf_a
from .lending_rates import prepare_fixed_yields
from .engine_q_a import _prod_rate

class YieldPathTests(unittest.TestCase):
    def test_schedule_and_override(self):
        c=_cfg();a=c['assumptions'];a['periods_per_year']=12;a['n_periods']=60
        p=a['lending_products'][0];p['yield_ann_spec']={'source':'entered','trajectory':'explicit','cadence':'year','values':[.11,.107,.104,.104,.104],'extend':'hold','resolution':'step'}
        p['overrides']={'yield_ann':{'14':.09}};saved=copy.deepcopy(c);r=run_pf_a(c)['products'][0];self.assertEqual(c,saved)
        self.assertEqual(r['rateQ'][:12],[11.]*12);self.assertAlmostEqual(r['rateQ'][12],10.7);self.assertAlmostEqual(r['rateQ'][13],9);self.assertAlmostEqual(r['rateQ'][14],10.7);self.assertAlmostEqual(r['rateQ'][24],10.4)
        self.assertAlmostEqual(r['interest'][12],10000000*.107/12)
        from .run_q import run_v2
        public=run_v2(c)['products'][0];self.assertAlmostEqual(public['rateQ'][12],10.7)

    def test_cadences_growth_and_float_gate(self):
        for ppy in (4,12):
            p={'rate_type':'fixed','yield_ann':.01,'yield_ann_spec':{'source':'entered','trajectory':'explicit','cadence':'year','values':[.11,.107],'extend':'hold'}}
            prepare_fixed_yields([p],5*ppy,ppy);self.assertEqual(len(p['_yield_ann_path']),5*ppy);self.assertAlmostEqual(_prod_rate(p,ppy+1,lambda q:.02),.107)
            p['rate_type']='float';p['index_spread']=.01;self.assertAlmostEqual(_prod_rate(p,1,lambda q:.02),.03)
        p={'rate_type':'fixed','yield_ann_spec':{'source':'entered','trajectory':'growth','base':.1,'growth_spec':{'rate':.1,'period':'year','method':'step','anchor':'model_year'}}}
        prepare_fixed_yields([p],24,12);self.assertAlmostEqual(p['_yield_ann_path'][12],.11)

    def test_profile_b(self):
        import json
        from pathlib import Path
        from .engine_q_b import run_pf_b
        c=json.loads(Path('foundry/fixtures/parity/configs/pf_b_base.json').read_text());a=c['assumptions'];a['n_periods']=12
        p=a['lending_products'][0];p['rate_type']='fixed';p['yield_ann_spec']={'source':'entered','trajectory':'explicit','cadence':'year','values':[.11,.107,.104],'extend':'hold'}
        rows=run_pf_b(c)['products'];r=next(x for x in rows if x['name']==p['name'])
        self.assertAlmostEqual(r['rateQ'][0],11);self.assertAlmostEqual(r['rateQ'][4],10.7);self.assertAlmostEqual(r['rateQ'][8],10.4)

    def test_invalid_rates_and_legacy(self):
        for v in (-.01,.61,float('nan')):
            with self.assertRaises(ValueError):prepare_fixed_yields([{'rate_type':'fixed','yield_ann_spec':{'source':'entered','trajectory':'flat','value':v}}],12,12)
        p={'rate_type':'fixed','yield_ann':.12};before=copy.deepcopy(p);prepare_fixed_yields([p],12,12);self.assertEqual(p,before);self.assertEqual(_prod_rate(p,1,lambda q:0),.12)
