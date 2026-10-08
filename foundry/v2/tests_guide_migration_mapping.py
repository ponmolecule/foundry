"""Linked migrated flows, missing cadence, and r310 Apply remain safe."""
import copy,json,unittest
from .fee_guide import guide_fee_product,render_guide_plan,materialize_guide_streams,_system_prompt
from .income_modules import fee_stream_q
from .tests_fee_guide import _Resp
DESCRIPTION='I have a TPV source. The platform earns a revenue rate of $0.000004 and a cost rate of $0.000003 per dollar of TPV. I also have a migration schedule that governs the portion of revenu/cost that goes from the platform to the bank. The migration schedule is already available as a linked source, just like the TPV source'
def base():
 return {'status':'plan','product_label':'Platform fees','managed_notional_source':'not_needed','streams':[{'name':'Bank platform fees','basis':'transaction','driver_source':'fee_stream_quantity','driver_reference':'Migrated TPV','driver_trajectory':'flat','transaction_pricing_basis':'pct_of_throughput','rate_behavior':'flat','cost_kind':'pct_of_throughput_opex'}],'questions':[],'unsupported_mechanics':[]}
def upstream(plan):
 def call(req,timeout=0):return _Resp({'content':[{'type':'text','text':json.dumps(plan)}]})
 return call
class Tests(unittest.TestCase):
 def test_exact_description_clarifies_link_meaning(self):
  p=base();p.update(status='needs_clarification',streams=[],questions=['Does the linked migration source contain only migration percentages, or TPV already multiplied by them?'])
  out=guide_fee_product(DESCRIPTION,api_key='test-only',http_open=upstream(p))
  self.assertEqual(out['status'],'needs_clarification');self.assertEqual(out['streams'],[])
  self.assertIn('two independent linked',_system_prompt());self.assertIn('Dollars per dollar',_system_prompt())
 def test_missing_period_asks_instead_of_crashing(self):
  p=base();p['streams'][0].update(driver_trajectory='derived',coefficient_kind='pct',coefficient_semantics='share',coefficient_trajectory='explicit_schedule',coefficient_period='not_applicable')
  calls=[]
  def call(req,timeout=0):calls.append(1);return upstream(p)(req,timeout)
  out=guide_fee_product(DESCRIPTION,api_key='test-only',http_open=call)
  self.assertEqual(len(calls),1);self.assertEqual(out['status'],'needs_clarification');self.assertEqual(out['streams'],[])
  self.assertEqual(out['clarification']['choices'],['Month','Quarter','Year','Not sure'])
  with self.assertRaises(ValueError):materialize_guide_streams(p['streams'])
  p['streams'][0]['coefficient_period']='week'
  with self.assertRaises(ValueError):render_guide_plan(p)
 def test_known_period_preserved(self):
  for period in ('month','quarter','year'):
   p=base();p['streams'][0].update(coefficient_kind='pct',coefficient_semantics='share',coefficient_trajectory='explicit_schedule',coefficient_period=period)
   out=render_guide_plan(p);self.assertEqual(out['streams'][0]['coefficient_period'],period)
 def test_existing_targeted_question_preserved(self):
  p=base();p.update(status='needs_clarification',questions=['Does the linked source contain percentages or migrated TPV?'])
  p['streams'][0].update(coefficient_kind='pct',coefficient_semantics='share',coefficient_trajectory='explicit_schedule')
  self.assertEqual(render_guide_plan(p)['questions'],p['questions'])
 def test_linked_migrated_tpv_apply_and_amounts(self):
  out=guide_fee_product(DESCRIPTION+'\nAnswer: the linked source already contains TPV times migration.',api_key='test-only',http_open=upstream(base()))
  r=materialize_guide_streams(out['streams'],{'0':'migrated-tpv'})['streams'][0]
  self.assertIn('stream',r);s=r['stream'];self.assertNotIn('coefficient',s['driver']['params'])
  s['rate']['params']['per_unit']=.000004;s['cost']['params']['pct']=.000003
  for ppy in (1,4,12):
   revenue,cost=fee_stream_q(s,1,{'linked_stream_qty':{'migrated-tpv':[250000]}},ppy)
   self.assertEqual(revenue,1);self.assertEqual(cost,.75)
 def test_raw_percentage_reports_limit(self):
  p=base();p.update(status='unsupported',streams=[],unsupported_mechanics=['Two independent linked Series cannot be multiplied in the current fee grammar. Use reusable migrated TPV.'])
  out=guide_fee_product(DESCRIPTION+'\nAnswer: it is only a percentage.',api_key='test-only',http_open=upstream(p))
  self.assertEqual(out['status'],'unsupported');self.assertEqual(out['streams'],[])
  p['streams']=base()['streams'];p['streams'][0].update(coefficient_kind='pct',coefficient_semantics='share',coefficient_trajectory='explicit_schedule')
  self.assertEqual(render_guide_plan(p)['status'],'unsupported')
if __name__=='__main__':unittest.main()
