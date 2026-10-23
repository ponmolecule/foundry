import copy,json,os,tempfile,unittest
from unittest.mock import patch
from .tests_r369_lending_contracts import config
from .validate_q import structural_rate_gaps,validate_config_v2,ConfigErrorV2
from .run_q import run_v2
from foundry import store

class WorkingSaveTests(unittest.TestCase):
    def test_partial_draft_roundtrip_and_run_gate(self):
        c=config();p=c['assumptions']['lending_products'][0];p['yield_ann']=None
        before=copy.deepcopy(c)
        self.assertTrue(structural_rate_gaps(c))
        with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,FOUNDRY_DATA_DIR=d):
            with self.assertRaises(store.StructuralGapError):store.save_engagement(c,slug='strict')
            saved=store.save_engagement(c,slug='working',allow_incomplete=True)
            self.assertTrue(saved['input_warnings']);restored=store.load_engagement('working')
            self.assertIsNone(restored['assumptions']['lending_products'][0]['yield_ann'])
            restored.pop('config_schema_version',None);self.assertEqual(restored,c)
        self.assertEqual(c,before)
        with self.assertRaises(ConfigErrorV2):run_v2(c)

    def test_active_fixed_schedule_is_a_complete_rate(self):
        c=config();p=c['assumptions']['lending_products'][0];p['yield_ann']=None
        p['yield_ann_spec']={'source':'entered','trajectory':'explicit','cadence':'year','values':[.075,.072,.069,.069,.069],'extend':'hold'}
        self.assertEqual(structural_rate_gaps(c),[]);validate_config_v2(c)
        v=run_v2(c)['products'][0];self.assertAlmostEqual(v['rateQ'][12],7.2)
        p['yield_ann_spec']['values']=[]
        self.assertTrue(structural_rate_gaps(c))
        with self.assertRaises(ConfigErrorV2):run_v2(c)

    def test_http_working_save_and_load(self):
        from fastapi.testclient import TestClient
        import app as api
        client=TestClient(api.app);api.app.dependency_overrides[api.gate]=lambda:'draft-test'
        try:
            with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,FOUNDRY_DATA_DIR=d):
                c=config();c['assumptions']['lending_products'][0]['yield_ann']=None
                r=client.post('/api/v31/engagement/save-current',json={'config':c,'name':'Working loan','save_protocol':2,'expected_revision':None})
                self.assertEqual(r.status_code,200,r.text);self.assertTrue(r.json()['input_warnings'])
                load=client.get('/api/v31/engagement/'+r.json()['slug']);self.assertEqual(load.status_code,200)
                self.assertIsNone(load.json()['assumptions']['lending_products'][0]['yield_ann'])
        finally:api.app.dependency_overrides.pop(api.gate,None)
