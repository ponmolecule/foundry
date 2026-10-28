import copy
import unittest
from fastapi.testclient import TestClient
import app as web
from .tests_r408_product_formulas import config

class TransferHTTP(unittest.TestCase):
    def setUp(self):
        web.app.dependency_overrides[web.gate]=lambda:'test'
        self.client=TestClient(web.app)
    def tearDown(self):
        web.app.dependency_overrides.pop(web.gate,None);self.client.close()
    def body(self):
        c=config();return {'config':c,'collection':'obs_exposures','product_index':len(c['assumptions']['obs_exposures'])-1,'category_id':'agreement','component_id':'fraud'}
    def test_valid_and_rejected_moves(self):
        b=self.body();saved=copy.deepcopy(b)
        r=self.client.post('/api/v2/product-cost-transfer',json=b)
        self.assertEqual(r.status_code,200,r.text);self.assertEqual(b,saved)
        draft=r.json()['config'];self.assertEqual(len(draft['assumptions']['obs_exposures'][-1]['fee_streams']),1)
        b['category_id']='missing'
        r=self.client.post('/api/v2/product-cost-transfer',json=b)
        self.assertEqual(r.status_code,422);self.assertIn('missing',r.json()['error'])

if __name__=='__main__':unittest.main()
