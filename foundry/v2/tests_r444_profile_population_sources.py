"""Repayment funding follows derived acquisition populations through linked account and purchase streams."""
import json,unittest
from pathlib import Path
from .tests_r429_composition import setup
from .tests_repayment_profiles import product
from .repayment_profiles import canonical_flow,monthly_sources
from .cac_feeder import cac_auc_rollforward
from .run_q import run_v2

class Tests(unittest.TestCase):
 def test_population_purchase_chain(self):
  for ppy,n in [(12,60),(4,20)]:
   a=setup();a.update(periods_per_year=ppy,n_periods=n)
   def stream(name,basis,driver):return dict(name=name,quantity_series_id=name,basis=basis,driver=driver,rate={'behavior':'flat','params':{'per_unit':0}},cost={'kind':'none','params':{}})
   people=stream('Physicians','account',dict(source='customer_acquisition_count',ref='people',measure='period_end',trajectory='flat',params={}))
   hys=stream('HYS','account',dict(source='fee_stream_quantity',ref='Physicians',trajectory='derived',params={'multiple':.1}))
   cards=stream('Cards','account',dict(source='fee_stream_quantity',ref='HYS',trajectory='derived',params={'multiple':.08}))
   purchases=stream('Purchases','transaction',dict(source='stream_ref',ref='Cards',trajectory='derived',params={'coefficient':{'kind':'amount_per_source_unit','period':'month','trajectory':'flat','value':5000}}))
   a['obs_exposures']=[{'name':'Accounts','fee_streams':[people,hys]},{'name':'Cards','fee_streams':[cards,purchases]}]
   p=product();p['funded_flow_driver'].update(source='fee_stream_quantity',series_id='Purchases');a['lending_products']=[p]
   out=canonical_flow(p,a,n,ppy)
   r=cac_auc_rollforward(a['cac_feeds']['Practices'],n,ppy,assumptions=a)
   expected=r['population_composition']['population']['customer_end_by_month']
   self.assertEqual(len(out),60)
   for x,y in zip(out,expected):self.assertAlmostEqual(x,y*.1*.08*5000)
   c=json.loads(Path('foundry/fixtures/core_bank_test_base.json').read_text());c['assumptions'].update(a)
   result=run_v2(c);loan=next(x for x in result['products'] if x['name']==p['name'])
   width=12//ppy
   for i,x in enumerate(loan['fundedVolume']):self.assertAlmostEqual(x,round(sum(out[i*width:(i+1)*width])/1000,2))
   self.assertEqual(loan['rateQ'],[0.]*n)
   c['assumptions']['lending_products'][0]['yield_ann']=.04
   priced=next(x for x in run_v2(c)['products'] if x['name']==p['name'])
   self.assertEqual(priced['rateQ'],[4.]*n)
   _,counts=monthly_sources(a,n,ppy)
   for b in r['population_composition']['bands'].values():
    self.assertEqual(counts[b['series_id']]['period_end'],b['customer_end_by_month'])
if __name__=='__main__':unittest.main()
