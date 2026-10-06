"""AUC consumer measures and scheduled annual rate changes, without legacy drift."""
import copy,json,unittest
from .income_modules import fee_stream_q,_fee_rate_q,_validate_fee_stream_shape
from .run_q import run_v2
from .tests_fee_quantity_links import fixture,product,linked

def stream(measure=None):
 s={'name':'Custody','quantity_series_id':'auc-fee','basis':'balance','driver':{'source':'managed_notional','trajectory':'flat','params':{}},'rate':{'behavior':'annual_change','params':{'rate':.0014,'annual_delta':-.02}},'cost':{'kind':'none','params':{}}}
 if measure:s['driver']['measure']=measure
 return s
class Tests(unittest.TestCase):
 def test_measure_numbers(self):
  ctx={'managed_notional':28776100.6*1000,'managed_notional_end':29103314.2*1000}
  self.assertAlmostEqual(fee_stream_q(stream(),1,ctx,12)[0],3357211.7366666667)
  self.assertAlmostEqual(fee_stream_q(stream('period_end'),1,ctx,12)[0],29103314.2*1000*.0014/12)
  with self.assertRaises(ValueError):fee_stream_q(stream('period_end'),1,{},12)
  with self.assertRaises(ValueError):_validate_fee_stream_shape(stream('bad'))
 def test_flat_identity_all_cadences(self):
  a=stream()['rate'];b=copy.deepcopy(a);b['params']['annual_delta_path']={'trajectory':'flat','period':'year','value':-.02}
  for ppy in (1,4,12):
   for q in range(1,7*ppy+1):self.assertAlmostEqual(_fee_rate_q(a,q,1,ppy),_fee_rate_q(b,q,1,ppy),places=16)
 def test_explicit_transitions_and_growth(self):
  a=stream()['rate'];a['params']['annual_delta_path']={'trajectory':'explicit_schedule','period':'year','schedule':{'1':-.02,'2':-.03,'3':.01}}
  expected=[.0014,.001372,.00133084,.0013441484,.001357589884]
  for ppy in (1,4,12):
   for y,v in enumerate(expected):self.assertAlmostEqual(_fee_rate_q(a,y*ppy+1,1,ppy),v,places=14)
  a['params']['annual_delta_path']={'trajectory':'growth','period':'year','value':-.02,'growth_spec':{'rate':.5,'period':'year','method':'step','anchor':'model_year'}}
  self.assertAlmostEqual(_fee_rate_q(a,25,1,12),.0014*.98*.97)
 def test_old_and_new_stock_equivalence(self):
  for params,multiplier in [({},1),({'multiple':2,'pct':.3},2),({'pct':.3},.3),({'multiple':0},0)]:
   old=stream();old['driver'].update(trajectory='derived',params=params)
   new=copy.deepcopy(old);new['driver']['params']['stock_multiplier']={'kind':'pct','trajectory':'flat','value':multiplier,'period':'year'}
   for q in (1,13,25):
    self.assertEqual(fee_stream_q(old,q,{'managed_notional':1000000},12),fee_stream_q(new,q,{'managed_notional':1000000},12))
 def test_rejections(self):
  for path in [{'trajectory':'explicit_schedule','schedule':{}},{'trajectory':'flat','value':float('nan')},{'trajectory':'flat','value':-1.01},{'trajectory':'flat','period':'month'},{'trajectory':'growth'}]:
   s=stream();s['rate']['params']['annual_delta_path']=path
   with self.assertRaises(ValueError):_validate_fee_stream_shape(s)
 def test_engine_and_link_planner(self):
  for ppy in (4,12):
   c=fixture(ppy);a=c['assumptions'];avg=stream();end=stream('period_end');end['name']='Ending';end['quantity_series_id']='auc-end';
   a['obs_exposures']=[product('AUC',[avg,end])];a['obs_exposures'][0]['managed_notional']={'day1':1000000,'target':4000000,'ramp_periods':4,'trajectory':'ramp_to_target'}
   direct=run_v2(c);p=next(x for x in direct['products'] if x['name']=='AUC')
   self.assertGreater(p['managedNotionalEnd'][0],p['managedNotionalAvg'][0])
   quantities=direct['fee_stream_quantities']['series'];self.assertEqual(quantities['auc-end'][0],p['managedNotionalEnd'][0]*1000)
   follower=linked('consumer','auc-end');follower['basis']='balance';follower['rate']={'behavior':'flat','params':{'rate':.001}};follower['cost']={'kind':'none','params':{}}
   follower['driver']['params']={};follower['driver']['trajectory']='flat';a['obs_exposures'].append(product('Consumer',[follower]));r=run_v2(c)
   self.assertEqual(r['fee_stream_quantities']['series']['auc-end'],quantities['auc-end'])
   self.assertEqual(next(x for x in r['products'] if x['name']=='AUC')['fees'],p['fees'])
if __name__=='__main__':unittest.main()
