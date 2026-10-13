"""Expected settlement failures are validation errors, never a generic 500."""
import copy,unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
import app as web
from .tests_settlement_cash import model
class Tests(unittest.TestCase):
 def setUp(self):
  self.cfg=model();self.cfg['assumptions']['obs_exposures'][-1]['fee_streams'][0]['revenue_presentation']='contra_revenue'
  web.app.dependency_overrides[web.gate]=lambda:'test'
  self.client=TestClient(web.app)
 def tearDown(self):web.app.dependency_overrides.pop(web.gate,None);self.client.close()
 def test_invalid_sign_preview_and_audit(self):
  for route in ['/api/v2/preview','/api/v2/calculation-audit']:
   before=copy.deepcopy(self.cfg);r=self.client.post(route,json=self.cfg);self.assertEqual(r.status_code,422);j=r.json();self.assertFalse(j['valid']);self.assertIn('Source sign',j['errors'][0]);self.assertIn('month 1',j['errors'][0]);self.assertEqual(self.cfg,before)
 def test_corrected_sign_runs_and_exports(self):
  self.cfg['assumptions']['other_liabilities_model']['components'][0]['settlement']['sign']=-1
  r=self.client.post('/api/v2/preview',json=self.cfg);self.assertEqual(r.status_code,200);j=r.json()
  r=self.client.post('/api/v2/calculation-audit',json={'config':self.cfg,'expected_config_hash':j['config_hash'],'expected_run_hash':j['run_hash']});self.assertEqual(r.status_code,200);self.assertTrue(r.content.startswith(b'PK'))
 def test_unexpected_error_is_not_validation(self):
  with patch('foundry.v2.run_q.run_v2',side_effect=RuntimeError('unexpected defect')):
   with self.assertRaisesRegex(RuntimeError,'unexpected defect'):self.client.post('/api/v2/preview',json=self.cfg)
if __name__=='__main__':unittest.main()
