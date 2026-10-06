"""Guide startup and annual-change mapping through a mocked upstream response."""
import copy,json,unittest
from .fee_guide import fee_guide_manifest,_guide_output_schema,guide_fee_product,validate_guide_plan,_dummy_stream
from .tests_fee_guide import _Resp
class Tests(unittest.TestCase):
 def test_manifest_and_schema_scope(self):
  ids={x['id'] for x in fee_guide_manifest()['driver_sources']}
  self.assertIn('fee_stream_quantity',ids)
  self.assertNotIn('distributed_balance',ids);self.assertNotIn('product_funded_flow',ids)
  self.assertEqual(ids,set(_guide_output_schema()['properties']['streams']['items']['properties']['driver_source']['enum']))
 def test_user_annual_change(self):
  plan={'status':'plan','product_label':'Custody','managed_notional_source':'customer_acquisition_feed','streams':[{'name':'Custody','basis':'balance','driver_source':'managed_notional','driver_trajectory':'flat','rate_behavior':'annual_change','pricing_trajectory':'flat','cost_kind':'none'}],'questions':[],'unsupported_mechanics':[]}
  def upstream(req,timeout=0):
   payload=json.loads(req.data.decode());self.assertIn('annual_change',payload['system']);return _Resp({'content':[{'type':'text','text':json.dumps(plan)}]})
  out=guide_fee_product('We earn a 0.14% custody fee on AUC and a -2% annual fee rate change. Use the Customer-Acquisition feed as AUC source; use annual_change on the Balance-basis rate.',api_key='test-only',http_open=upstream)
  text=' '.join(out['stream_guides'][0]['steps']);self.assertIn('Annual rate change',text);self.assertNotIn('Set Rate behavior to “Series rate path”',text);self.assertIn('Year 1',text)
 def test_annual_paths_use_real_behavior(self):
  for trajectory in ('flat','growth','explicit_schedule'):
   plan={'status':'plan','product_label':'Custody','managed_notional_source':'customer_acquisition_feed','streams':[{'name':'Custody','basis':'balance','driver_source':'managed_notional','driver_trajectory':'flat','rate_behavior':'annual_change','pricing_trajectory':trajectory,'pricing_period':'year','pricing_resolution':'step','cost_kind':'none'}],'questions':[],'unsupported_mechanics':[]}
   validated=validate_guide_plan(plan)
   dummy=_dummy_stream(validated['streams'][0])
   self.assertEqual(dummy['rate']['behavior'],'annual_change')
   self.assertEqual(dummy['rate']['params']['annual_delta_path']['trajectory'],trajectory)
   plan['streams'][0]['pricing_period']='month'
   with self.assertRaises(ValueError):validate_guide_plan(plan)
if __name__=='__main__':unittest.main()
