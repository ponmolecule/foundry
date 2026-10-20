"""Primary stream results come from engine postings, not parent volume or frontend pricing."""
import copy
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from .run_q import run_v2
from .engine_q_a import run_pf_a


def make_stream(name,sid,source='constant',ref=None,price=0,coefficient=None,cost=None):
    driver={'source':source,'trajectory':'derived' if coefficient else 'flat','params':{}}
    if source=='constant':driver['params']['base']=10
    if ref:driver['ref']=ref
    if coefficient:driver['params']['coefficient']=coefficient
    return {'name':name,'quantity_series_id':sid,'basis':'transaction','driver':driver,
            'rate':{'behavior':'flat','params':{'per_unit':price}},'cost':cost or {'kind':'none','params':{}}}


def fixture(ppy=12):
    cfg=json.loads(Path('foundry/fixtures/core_bank_test_base.json').read_text());a=cfg['assumptions']
    a['periods_per_year']=ppy;a['n_periods']=ppy;a['capital_raises']=[]
    st=[make_stream('Source practices','root'),
        make_stream('Participating practices','cards','stream_ref','Source practices',coefficient={'kind':'pct','semantics':'share','value':.6,'period':'month','trajectory':'flat'}),
        make_stream('Purchase activity','purchases','stream_ref','Participating practices',coefficient={'kind':'amount_per_source_unit','value':23000,'period':'month','trajectory':'flat'}),
        make_stream('Gross fee','gross','stream_ref','Purchase activity',price=.022),
        make_stream('Assessment','network','stream_ref','Purchase activity',price=.0014),
        make_stream('Service cost','cost','stream_ref','Participating practices',cost={'kind':'per_unit','params':{'cost_per_unit':10}}),
        make_stream('Fee and cost','both','stream_ref','Purchase activity',price=.01,cost={'kind':'pct_of_throughput_opex','params':{'pct':.002}}),
        make_stream('Timed fee','timed','stream_ref','Purchase activity',price=.005),
        make_stream('Timed count','timed-count','stream_ref','Participating practices')]
    st[0]['basis']='account';st[0]['rate']['params']={'unit_fee':{'value':0,'period':'month','trajectory':'flat'}}
    st[4]['revenue_presentation']='contra_revenue';st[7]['timing']={'start_period':2,'end_period':3};st[8]['timing']={'start_period':2,'end_period':3}
    a['obs_exposures']=[{'name':'Resolved outputs','call_report_line':'obs','_fee_product':True,'fee_streams':st}]
    return cfg


class StreamOutputTests(unittest.TestCase):
    def test_public_postings_reconcile_to_exact_engine(self):
        cfg=fixture();saved=copy.deepcopy(cfg);r=run_v2(cfg);exact=run_pf_a(copy.deepcopy(cfg))
        self.assertEqual(cfg,saved)
        econ=r['fee_stream_economics'];self.assertEqual(econ['monetary_units'],'dollars')
        for sid,rec in econ['series'].items():
            self.assertEqual(rec,exact['fee_stream_economics'][sid])
        s=econ['series'];q=r['fee_stream_quantities']['series']
        self.assertEqual(q['root'][0],10);self.assertEqual(q['cards'][0],6);self.assertEqual(q['purchases'][0],138000)
        self.assertAlmostEqual(s['gross']['reported_fee_income'][0],3036)
        self.assertAlmostEqual(s['network']['reported_fee_income'][0],-193.2)
        self.assertAlmostEqual(s['cost']['fee_product_cost'][0],60)
        self.assertAlmostEqual(s['both']['reported_fee_income'][0]-s['both']['fee_product_cost'][0],1104)
        self.assertEqual(s['timed']['reported_fee_income'][0],0)
        self.assertEqual(q['timed-count'][0],0);self.assertEqual(q['timed-count'][1],6);self.assertEqual(q['timed-count'][3:],[0]*9)
        self.assertEqual(s['timed']['reported_fee_income'][3:], [0]*9)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'actual.json';path.write_text(json.dumps({'cfg':cfg,'res':r}))
            subprocess.run(['node','web/tests_r360_stream_outputs.cjs',str(path)],check=True)
    def test_postings_are_published_for_loan_and_deposit_owners(self):
        cfg=json.loads(Path('foundry/fixtures/universal_template_bank.json').read_text())
        loan=cfg['assumptions']['lending_products'][0]['fee_streams'][0]
        dep=copy.deepcopy(loan);dep['quantity_series_id']='r360-deposit-posting'
        cfg['assumptions']['deposit_products'][0]['fee_streams']=[dep]
        public=run_v2(copy.deepcopy(cfg));raw=run_pf_a(copy.deepcopy(cfg))
        for sid in [loan['quantity_series_id'],dep['quantity_series_id']]:
            self.assertIn(sid,public['fee_stream_economics']['series'])
            self.assertEqual(public['fee_stream_economics']['series'][sid],raw['fee_stream_economics'][sid])

    def test_quarterly_postings_and_renaming(self):
        cfg=fixture(4);r=run_v2(copy.deepcopy(cfg));s=r['fee_stream_economics']['series']
        self.assertAlmostEqual(s['gross']['reported_fee_income'][0],9108)
        self.assertAlmostEqual(s['network']['reported_fee_income'][0],-579.6)
        cfg['assumptions']['obs_exposures'][0]['name']='Changed product label'
        rr=run_v2(cfg)
        self.assertEqual(rr['fee_stream_economics'],r['fee_stream_economics'])

if __name__=='__main__':unittest.main()
