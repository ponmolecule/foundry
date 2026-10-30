"""Weighted count ratios reuse shared assumption math without periodization."""
import copy, unittest
from .income_modules import fee_stream_q, _validate_fee_stream_shape

def entered(v,unit):return dict(source='entered',trajectory='flat',value=v,unit=unit)
def stream():
 return dict(name='People',basis='account',driver=dict(source='stream_ref',ref='Practices',trajectory='derived',params=dict(count_multiplier_spec=dict(source='weighted_sum',unit='scalar',components=[dict(id=str(i),name='Band '+str(i),amount_spec=entered(a,'scalar'),weight_spec=entered(w,'share')) for i,(a,w) in enumerate(zip([7.5,17.5,37,75],[.735415,.192687,.048006,.023892]))]))),rate=dict(behavior='flat',params=dict(rate=0)),cost=dict(kind='none',params={}))
class Tests(unittest.TestCase):
 def test_ratio_all_periods(self):
  s=stream();original=copy.deepcopy(s)
  for ppy in (4,12):
   for q in range(1,5*ppy+1):
    ctx={'stream_qty':{'Practices':100+q}}
    fee_stream_q(s,q,ctx,ppy)
    self.assertAlmostEqual(ctx['stream_qty']['People'],(100+q)*12.455757,places=9)
  self.assertEqual(s,original)
 def test_validation(self):
  for mutate in [lambda s:s.update(basis='transaction'),lambda s:s['driver'].update(source='constant'),lambda s:s['driver']['params'].update(multiple=2),lambda s:s['driver']['params']['count_multiplier_spec']['components'][0]['weight_spec'].update(value=.1),lambda s:s['driver']['params']['count_multiplier_spec']['components'][0]['amount_spec'].update(value=-1),lambda s:s['driver']['params']['count_multiplier_spec'].update(components=[])]:
   s=stream();mutate(s)
   with self.assertRaises(ValueError):fee_stream_q(s,1,{"stream_qty":{"Practices":100}},12)
 def test_time_varying_ratio_is_level_not_flow(self):
  s=stream();c=s['driver']['params']['count_multiplier_spec']['components'];c[:]=[dict(id='a',name='All',amount_spec=dict(source='entered',trajectory='explicit',cadence='year',values=[2,3],unit='scalar'),weight_spec=entered(1,'share'))]
  for ppy in (4,12):
   for q,want in [(1,200),(ppy+1,300)]:
    ctx={'stream_qty':{'Practices':100}};fee_stream_q(s,q,ctx,ppy);self.assertEqual(ctx['stream_qty']['People'],want)
 def test_legacy_identity(self):
  s=stream();s['driver']['params']={'multiple':12.455757};ctx={'stream_qty':{'Practices':100}};fee_stream_q(s,1,ctx,12);self.assertAlmostEqual(ctx['stream_qty']['People'],1245.5757)
if __name__=='__main__':unittest.main()
