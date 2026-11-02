"""Causal cumulative acquisition levels: monthly-first, before attrition."""
import copy,json,unittest
from pathlib import Path
from .tests_account_activity import feed,stream
from .account_activity import resolve,catalog,cumulative_gross_id
from .income_modules import product_fee_streams_q
from .run_q import run_v2

class Tests(unittest.TestCase):
    def case(self):
        f=feed();f['driver_specs']={'attrition_rate':{'source':'entered','trajectory':'flat','value':.1,'period':'month'}}
        sid=cumulative_gross_id(f)
        st=stream('Activation marketing','account',sid,cost={'kind':'per_account','params':{'cost_per_account':45,'period':'year'}})
        a={'cac_feeds':{'Lines':f},'obs_exposures':[{'name':'Costs','fee_streams':[st]}]}
        return a,sid,st
    def test_discovery_and_live_total_before_attrition(self):
        a,sid,st=self.case();m,_=resolve(a,12,12)
        self.assertEqual(m[sid]['values'],[10.*i for i in range(1,13)])
        self.assertEqual(m[sid]['opening'],0,'opening customers are not forecast acquisitions')
        self.assertEqual(m['chnew']['values'],[10.]*12)
        self.assertTrue(any(x['series_id']==sid and x['temporal']=='level' for x in catalog(a)))
        a['cac_feeds']['Lines']['channels'][0]['params']['new_customers_by_year']=[240]
        updated,_=resolve(a,12,12);self.assertEqual(updated[sid]['values'][-1],240)
        a['cac_feeds']['Renamed']=a['cac_feeds'].pop('Lines')
        self.assertEqual(cumulative_gross_id(a['cac_feeds']['Renamed']),sid)
        self.assertTrue(any(x['series_id']==sid and 'Renamed' in x['label'] for x in catalog(a)))
    def test_monthly_cost_and_quarterly_aggregation(self):
        a,sid,st=self.case();m,_=resolve(a,12,12);q,_=resolve(a,4,4)
        self.assertEqual(q[sid]['values'],[30,60,90,120])
        self.assertEqual(q[sid]['average_values'],[20,50,80,110])
        prod={'fee_streams':[st]}
        monthly=[product_fee_streams_q(prod,i+1,{'account_activity':m},12)[1] for i in range(12)]
        quarterly=[product_fee_streams_q(prod,i+1,{'account_activity':q},4)[1] for i in range(4)]
        self.assertEqual(monthly,[45/12*10*i for i in range(1,13)])
        for i in range(4):self.assertAlmostEqual(quarterly[i],sum(monthly[3*i:3*i+3]))
    def test_legacy_unchanged_and_straight_line_unavailable(self):
        a,sid,st=self.case();a['obs_exposures']=[]
        r,_=resolve(a,12,12);self.assertNotIn(sid,r,'new result only emitted for an explicit reference')
        a['cac_feeds']['Lines']['intra_period_path']='straight_line'
        self.assertFalse(any(x['series_id']==sid for x in catalog(a)))
    def test_full_engine_and_save_replay(self):
        a,sid,st=self.case();c=json.loads(Path('foundry/fixtures/universal_template_bank.json').read_text())
        c['assumptions']['cac_feeds'].update(a['cac_feeds']);c['assumptions']['obs_exposures'][0]['fee_streams']=[st];c['assumptions']['obs_exposures'][0]['fee_yield_ann']=0;c['assumptions']['obs_exposures'][0].get('overrides',{}).pop('fee_yield_ann',None)
        before=copy.deepcopy(c);r=run_v2(c)
        self.assertEqual(c,before);self.assertEqual(run_v2(json.loads(json.dumps(c)))['run_hash'],r['run_hash'])
        self.assertTrue(r['reporting']['ok'])
        prod=next(x for x in r['products'] if x['family']=='obs')
        self.assertAlmostEqual(prod['detailExact']['passCost'][0],37.5/1000)
        self.assertEqual(prod['detailExact']['fees'],[0]*len(prod['detailExact']['fees']))

if __name__=='__main__':unittest.main()
