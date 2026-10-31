"""Cross-family quantities, parent-owned costs and staged balance dependencies."""
import copy,unittest
from .tests_r424_deposit_count_links import setup
from .tests_fee_quantity_links import fixture,source,linked,quantities
from .run_q import run_v2
from .fee_links import FeeLinkPlan
from .source_catalog import catalog
from .validate_q import validate_errors_v2


def account(sid,ref,amount=100,period='year'):
 return dict(name=sid,quantity_series_id=sid,basis='account',
  driver=dict(source='fee_stream_quantity',ref=ref,trajectory='derived',params={'multiple':1}),
  rate={'behavior':'flat','params':{'fee_per_period':0}},
  cost={'kind':'per_account','params':{'cost_per_account':amount,'period':period}})

class Tests(unittest.TestCase):
 def test_hys_servicing_owned_by_deposit(self):
  for ppy in (12,4):
   c=setup(ppy);a=c['assumptions'];a['deposit_products'][0]['fee_streams']=[account('servicing','savers')]
   before=copy.deepcopy(c);self.assertEqual(validate_errors_v2(copy.deepcopy(c)),[])
   r=run_v2(c);self.assertEqual(c,before)
   for x,y in zip(quantities(r,'servicing'),quantities(r,'savers')):self.assertAlmostEqual(x,y)
   p=next(x for x in r['products'] if x['family']=='deposit')
   for count,cost in zip(quantities(r,'savers'),p['passCost']):self.assertAlmostEqual(cost,round(count*100/ppy/1000,2))
   # Same economics using the old shared-fee-product placement; ownership alone changes.
   old=copy.deepcopy(c);old['assumptions']['obs_exposures'][0]['fee_streams']+=old['assumptions']['deposit_products'][0].pop('fee_streams')
   self.assertEqual(r['financials'],run_v2(old)['financials'])
 def test_all_directions_and_reorder(self):
  c=fixture();a=c['assumptions'];a['obs_exposures'][0]['fee_streams']=[linked('last','loan-stream',.2)]
  a['deposit_products'][0]['fee_streams']=[linked('deposit-stream','tpv',.5)]
  a['lending_products'][0]['fee_streams']=[linked('loan-stream','deposit-stream',.5)]
  r=run_v2(c)
  for sid,v in [('tpv',100000),('deposit-stream',50000),('loan-stream',25000),('last',5000)]:self.assertAlmostEqual(quantities(r,sid)[0],v)
  for key in ('obs_exposures','deposit_products','lending_products'):
   a[key].reverse()
   for p in a[key]:p['name']='Renamed '+p['name']
  self.assertEqual(r['financials'],run_v2(c)['financials'])
  rows={x['series_id']:x for x in catalog(a) if x.get('driver')=='fee_stream_quantity'}
  for sid in ('tpv','deposit-stream','loan-stream','last'):self.assertIn('fee_quantity',rows[sid]['consumers']);self.assertEqual(rows[sid]['unit'],'money_flow')
 def test_every_source_consumer_family_pair(self):
  families=('obs_exposures','deposit_products','lending_products')
  for src_family in families:
   for dst_family in families:
    with self.subTest(source=src_family,consumer=dst_family):
     c=fixture();a=c['assumptions']
     for family in families:
      for p in a[family]:p['fee_streams']=[]
     if src_family==dst_family and len(a[src_family])<2:a[src_family].append(copy.deepcopy(a[src_family][0]))
     root=a[src_family][0];sink=a[dst_family][1 if src_family==dst_family else 0]
     root['name']='Source owner';sink['name']='Consumer owner'
     root['fee_streams']=[source()];sink['fee_streams']=[linked()]
     self.assertEqual(validate_errors_v2(copy.deepcopy(c)),[])
     r=run_v2(c);self.assertAlmostEqual(quantities(r,'migrated')[0],50000)
     owner=next(p for p in r['products'] if p['name']=='Consumer owner')
     self.assertAlmostEqual(owner['passCost'][0],.5)
 def test_parent_balance_published_under_lending(self):
  c=fixture();a=c['assumptions'];st=linked('loan-stock','tpv',1)
  st.update(basis='balance',rate={'behavior':'flat','params':{'rate_ann':0}},cost={'kind':'none','params':{}})
  st['driver']={'source':'own_balance','measure':'period_begin','trajectory':'flat','params':{}}
  a['lending_products'][0]['fee_streams']=[st]
  child=copy.deepcopy(st);child.update(name='stock consumer',quantity_series_id='stock-consumer');child['driver']={'source':'fee_stream_quantity','ref':'loan-stock','trajectory':'derived','params':{'multiple':1}}
  a['deposit_products'][0]['fee_streams']=[child]
  r=run_v2(c);self.assertEqual(quantities(r,'stock-consumer'),quantities(r,'loan-stock'))
  self.assertGreater(quantities(r,'loan-stock')[0],0)
 def test_pool_owned_count_costs_and_dynamic_export_rejection(self):
  from .tests_deposit_retention import fixture as pool_fixture
  from .tests_fee_quantity_links import product
  c=pool_fixture();a=c['assumptions']
  root=account('accounts','unused');root['driver']={'source':'constant','trajectory':'flat','params':{'base':600}};root['cost']={'kind':'none','params':{}}
  a['obs_exposures']=[product('Population',[root])]
  a['deposit_products'][0]['fee_streams']=[account('service','accounts',10,'month')]
  r=run_v2(c);p=next(x for x in r['products'] if x['name']=='Category A');self.assertEqual(p['passCost'][0],6)
  exported=source('pool-export');exported['driver']={'source':'own_balance','trajectory':'derived','params':{'coefficient':{'kind':'multiple','value':1,'period':'month','trajectory':'flat'}}}
  a['deposit_products'][0]['fee_streams'].append(exported)
  a['obs_exposures'][0]['fee_streams'].append(linked('dependent','pool-export'))
  with self.assertRaisesRegex(ValueError,'retention-pool'):FeeLinkPlan(a)
 def test_rejections(self):
  c=setup();a=c['assumptions'];a['deposit_products'][0]['fee_streams']=[account('servicing','savers')]
  # Genuine cross-family cycle, missing reference, duplicate IDs, and incompatible units.
  bad=copy.deepcopy(a);bad['obs_exposures'][0]['fee_streams'][0]['driver']={'source':'fee_stream_quantity','ref':'servicing','trajectory':'flat','params':{}}
  with self.assertRaisesRegex(ValueError,'cycle'):FeeLinkPlan(bad)
  bad=copy.deepcopy(a);bad['deposit_products'][0]['fee_streams'][0]['driver']['ref']='missing'
  with self.assertRaisesRegex(ValueError,'missing'):FeeLinkPlan(bad)
  bad=copy.deepcopy(a);bad['deposit_products'][0]['fee_streams'][0]['quantity_series_id']='savers'
  with self.assertRaisesRegex(ValueError,'unique'):FeeLinkPlan(bad)
  bad=copy.deepcopy(a);bad['deposit_products'][0]['fee_streams'][0]['basis']='balance'
  with self.assertRaisesRegex(ValueError,'stock'):FeeLinkPlan(bad)
 def test_incremental_evaluation_exactly_once(self):
  a={'obs_exposures':[{'fee_streams':[source()]}],'deposit_products':[{'fee_streams':[linked()]}]}
  plan=FeeLinkPlan(a);qty={};done=set();contexts={(0,1):{'capture_stream_qty':qty}}
  first=plan.evaluate(contexts,1,12,completed=done,require_complete=False)
  self.assertAlmostEqual(first[(0,1)][0],1000)
  contexts[(1,1)]={'capture_stream_qty':qty}
  second=plan.evaluate(contexts,1,12,completed=done)
  self.assertNotIn((0,1),second);self.assertAlmostEqual(second[(1,1)][0],1000)
  self.assertEqual(plan.evaluate(contexts,1,12,completed=done),{})
if __name__=='__main__':unittest.main()
