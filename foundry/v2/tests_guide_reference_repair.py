"""Contradictory AI source references must be corrected, never silently erased."""
import copy,json,unittest
from .fee_guide import guide_fee_product,validate_guide_plan,_dummy_stream
from .income_modules import fee_stream_q
from .tests_fee_guide import _Resp
DESCRIPTION='''I have a second stream of revenue. Use the Customer-Acquisition feed as the AUC source. Settlement turns multiplied by Average AUC per annum. Use Settlement Turns as the flow coefficient trajectory, with an annual Explicit schedule: Y1=8x, Y2=10x, Y3=12x, Y4=10x, Y5=10x, Y6=10x, Y7=9x. Add a flat settlement rate of 0.03%. The 0.03% settlement rate belongs to the Settlement Turns stream.\nClarification: Do you want % of throughput? Answer: Yes, % of throughput.'''
def plan():
 return {'status':'plan','product_label':'Settlement','managed_notional_source':'customer_acquisition_feed','streams':[{'name':'Settlement Turns','basis':'transaction','driver_source':'managed_notional','driver_reference':'not_applicable','driver_trajectory':'derived','coefficient_kind':'multiple','coefficient_period':'year','coefficient_trajectory':'explicit_schedule','transaction_pricing_basis':'pct_of_throughput','rate_behavior':'flat','cost_kind':'none'}],'questions':[],'unsupported_mechanics':[]}
class Tests(unittest.TestCase):
 def test_invalid_reference_corrected_with_history(self):
  bad=plan();bad['streams'][0]['driver_reference']='Settlement Turns';calls=[]
  with self.assertRaises(ValueError):validate_guide_plan(bad)
  def upstream(req,timeout=0):
   payload=json.loads(req.data);calls.append(payload)
   return _Resp({'content':[{'type':'text','text':json.dumps(bad if len(calls)==1 else plan())}]})
  out=guide_fee_product(DESCRIPTION,api_key='test-only',http_open=upstream)
  self.assertEqual(len(calls),2);self.assertEqual(calls[1]['messages'][0]['content'],DESCRIPTION)
  self.assertIn('driver_reference',calls[1]['messages'][-1]['content'])
  self.assertEqual(len(out['streams']),1);self.assertIsNone(out['streams'][0]['driver_reference'])
  steps=' '.join(out['stream_guides'][0]['steps']);self.assertIn('Turns schedule by year',steps);self.assertIn('% of throughput',steps);self.assertNotIn('Reference stream',steps)
 def test_still_invalid_fails_closed(self):
  bad=plan();bad['streams'][0]['driver_reference']='Settlement Turns';calls=[]
  def upstream(req,timeout=0):
   calls.append(1);return _Resp({'content':[{'type':'text','text':json.dumps(bad)}]})
  with self.assertRaisesRegex(RuntimeError,'after one automatic correction'):guide_fee_product(DESCRIPTION,api_key='test-only',http_open=upstream)
  self.assertEqual(len(calls),2)
 def test_valid_first_answer_needs_no_retry(self):
  calls=[]
  def upstream(req,timeout=0):
   calls.append(1);return _Resp({'content':[{'type':'text','text':json.dumps(plan())}]})
  guide_fee_product(DESCRIPTION,api_key='test-only',http_open=upstream);self.assertEqual(len(calls),1)
 def test_cross_product_reference_supported(self):
  p=plan();p['streams'][0]['driver_source']='fee_stream_quantity';p['streams'][0]['driver_reference']='Source quantity'
  validate_guide_plan(p)
  p['streams'][0]['driver_reference']='not_applicable'
  with self.assertRaises(ValueError):validate_guide_plan(p)
 def test_seven_year_economics(self):
  s=_dummy_stream(validate_guide_plan(plan())['streams'][0]);s['rate']['params']['per_unit']=.0003
  s['driver']['params']['coefficient']['schedule']={str(y+1):v for y,v in enumerate([8,10,12,10,10,10,9])}
  for ppy in (1,4,12):
   for y,turns in enumerate([8,10,12,10,10,10,9]):
    self.assertAlmostEqual(fee_stream_q(s,y*ppy+1,{'managed_notional':1000000},ppy)[0],1000000*turns*.0003/ppy)
if __name__=='__main__':unittest.main()
