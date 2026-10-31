"""Display labels and diagnostic provenance never change financial results."""
import copy, unittest
from .count_breakdown_fixture import config, stream
from .count_breakdown import count_breakdowns
from .run_q import run_v2
class Tests(unittest.TestCase):
 def test_labels_do_not_change_financials(self):
  a=config();b=copy.deepcopy(a);stream(b)['driver']['params']['count_multiplier_spec']['count_label']='People per organization'
  ra=run_v2(a);rb=run_v2(b)
  self.assertEqual(ra['financials'],rb['financials']);self.assertEqual(ra['fee_stream_quantities'],rb['fee_stream_quantities'])
 def test_actual_source_under_participation(self):
  a=config();stream(a)['driver']['params']['share_spec']={'source':'entered','trajectory':'flat','value':.5,'period':'month'}
  r=run_v2(a);rec=r['count_breakdowns'][0]
  source=next(s for s in a['assumptions']['obs_exposures'][2]['fee_streams'] if s['name']=='Enabled accounts')
  actual=r['fee_stream_quantities']['series'][source['quantity_series_id']]
  self.assertEqual(rec['source'],actual)
  for t in range(len(rec['quantity'])):self.assertAlmostEqual(rec['quantity'][t],actual[t]*rec['multiplier'][t]*.5,places=6)
 def test_zero_multiplier_does_not_hide_source(self):
  a=config()
  for c in stream(a)['driver']['params']['count_multiplier_spec']['components']:c['amount_spec']['value']=0
  r=run_v2(a);rec=r['count_breakdowns'][0]
  self.assertTrue(any(x>0 for x in rec['source']));self.assertTrue(all(x==0 for x in rec['quantity']))
 def test_missing_published_source_is_unavailable(self):
  a=config();r=run_v2(a);source=next(s for s in a['assumptions']['obs_exposures'][2]['fee_streams'] if s['name']=='Enabled accounts')
  del r['fee_stream_quantities']['series'][source['quantity_series_id']]
  self.assertTrue(all(x is None for x in count_breakdowns(a,r)[0]['source']))
if __name__=='__main__':unittest.main()
