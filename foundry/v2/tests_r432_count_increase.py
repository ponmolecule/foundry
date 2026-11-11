import copy,unittest
from .income_modules import product_fee_streams_q,_validate_fee_stream_shape
from .account_activity import validate_fee_paths
from .fee_links import FeeLinkPlan

def streams():
 parent=dict(name='Accounts',quantity_series_id='accounts',basis='account',driver=dict(source='constant',trajectory='explicit_schedule',params=dict(level_schedule=dict(period='month',resolution='step',schedule={str(i+1):v for i,v in enumerate([12,10,15,15,8,14])}))),rate=dict(behavior='flat',params=dict(unit_fee=dict(value=0,period='month'))),cost=dict(kind='none',params={}))
 child=dict(name='Onboarding',quantity_series_id='onboard',basis='transaction',driver=dict(source='stream_ref',ref='Accounts',trajectory='flat',params={},quantity_transform='positive_monthly_change',opening_count=10),rate=dict(behavior='flat',params=dict(per_unit=0,pricing_basis='per_unit')),cost=dict(kind='per_unit',params=dict(cost_per_unit=175,multiplier_path=dict(value=1,trajectory='explicit_schedule',period='month',schedule={str(i+1):v for i,v in enumerate([1,2,3,4,5,6])}))))
 return parent,child
class Tests(unittest.TestCase):
 def test_monthly_and_quarterly(self):
  p,c=streams();prod=dict(fee_streams=[p,c]);original=copy.deepcopy(prod)
  # Positive additions: 2,0,5,0,0,6. Monthly inflation is applied before summing.
  expected=[350,0,2625,0,0,6300]
  for ppy,n,w in [(12,6,1),(4,2,3)]:
   got=[product_fee_streams_q(prod,i+1,{},ppy)[1] for i in range(n)]
   self.assertEqual(got,[sum(expected[i:i+w]) for i in range(0,6,w)])
  self.assertEqual(prod,original)
 def test_cross_owner_and_live_change(self):
  p,c=streams();c['driver'].update(source='fee_stream_quantity',ref='accounts');a=dict(obs_exposures=[dict(fee_streams=[p])],deposit_products=[dict(fee_streams=[c])]);validate_fee_paths(a,2,4)
  def run():
   owners={s['quantity_series_id']:product['fee_streams'] for product in a['obs_exposures']+a['deposit_products'] for s in product['fee_streams']}
   contexts={(pi,q):dict(capture_stream_qty={},capture_stream_economics={},activity_stream_owners=owners) for pi in range(2) for q in range(1,3)}
   return FeeLinkPlan(a).evaluate(contexts,2,4)
  self.assertEqual(run()[(1,1)][1],2975)
  p['driver']['params']['level_schedule']['schedule']['3']=16
  self.assertEqual(run()[(1,1)][1],3500)
 def test_full_run_and_cadence(self):
  from .tests_r424_deposit_count_links import setup
  from .run_q import run_v2
  from .validate_q import validate_errors_v2
  results=[]
  for ppy in (12,4):
   cfg=setup(ppy);p,c=streams();c['driver'].update(source='fee_stream_quantity',ref='savers')
   cfg['assumptions']['deposit_products'][0]['fee_streams']=[c]
   from .testing_schedules import fill_schedules_like_r481 as _fill  # r482
   _fill(cfg['assumptions'])   # schedules entered for the whole horizon
   self.assertEqual(validate_errors_v2(copy.deepcopy(cfg)),[])
   before=copy.deepcopy(cfg);r=run_v2(cfg);self.assertEqual(cfg,before)
   self.assertIn('onboard',r['fee_stream_quantities']['series'])
   results.append(sum(r['fee_stream_quantities']['series']['onboard']))
  self.assertAlmostEqual(*results)
 def test_rejections(self):
  p,c=streams()
  for mutate in [lambda x:x['driver'].pop('opening_count'),lambda x:x['driver'].update(opening_count=-1),lambda x:x.update(basis='account'),lambda x:x['driver'].update(trajectory='derived'),lambda x:x['driver'].update(quantity_transform='unknown')]:
   b=copy.deepcopy(c);mutate(b)
   with self.assertRaises(ValueError):_validate_fee_stream_shape(b)
  p['basis']='transaction'
  with self.assertRaisesRegex(ValueError,'Account source'):product_fee_streams_q(dict(fee_streams=[p,c]),1,{},12)
if __name__=='__main__':unittest.main()
