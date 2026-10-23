"""r388: reject stale writers, preserve prior inputs, recover history without overwriting."""
import copy
import json
import os
import tempfile
import unittest
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import get_context
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
import app as api
from foundry import store


def config(value=1):
    return {'scenario_name':'Example · Base','proposed_bank':'Example',
            'assumptions':{'deposit_products':[], 'lending_products':[], 'value':value}}


def concurrent_save(args):
    directory, revision, value = args
    os.environ['FOUNDRY_DATA_DIR'] = directory
    try:
        store.save_engagement(config(value), 'base', user='analyst', expected_revision=revision)
        return 'saved'
    except store.SaveConflictError:
        return 'conflict'


class SaveSafetyTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory()
        self.env=patch.dict(os.environ,FOUNDRY_DATA_DIR=self.directory.name)
        self.env.start()
        api.app.dependency_overrides[api.gate]=lambda:'analyst'
        self.client=TestClient(api.app)

    def tearDown(self):
        api.app.dependency_overrides.pop(api.gate,None)
        self.env.stop();self.directory.cleanup()

    def post(self,c,revision=None,**kwargs):
        return self.client.post('/api/v31/engagement/save-current',json={'config':c,'name':'Example Base','save_protocol':2,'expected_revision':revision,**kwargs})

    def test_http_two_tabs_old_client_and_create_collision(self):
        old=self.client.post('/api/v31/engagement/save-current',json={'config':config(),'name':'Example Base'})
        self.assertEqual(old.status_code,428)
        first=self.post(config());self.assertEqual(first.status_code,200,first.text)
        revision=first.json()['revision'];slug=first.json()['slug']
        loaded=self.client.get('/api/v31/engagement/'+slug)
        self.assertEqual(loaded.headers['etag'],'"'+revision+'"')
        self.assertEqual(loaded.headers['cache-control'],'no-store')
        self.assertEqual(self.client.get('/api/v31/engagement/'+slug+'/revision').json()['revision'],revision)
        newer=self.post(config(2),revision);self.assertEqual(newer.status_code,200,newer.text)
        before=Path(newer.json()['path']).read_bytes();history=store.list_versions(slug,user='analyst')
        for rejected in [self.post(config(0),revision),self.post(config(0)),self.client.post('/api/v31/engagement',json={'cfg':config(0),'slug':slug,'save_protocol':2}),self.client.post('/api/v31/engagement',json={'cfg':config(0),'slug':slug})]:
            self.assertIn(rejected.status_code,(409,428),rejected.text)
            self.assertEqual(Path(newer.json()['path']).read_bytes(),before)
            self.assertEqual(store.list_versions(slug,user='analyst'),history)
        self.assertNotEqual(newer.json()['revision'],revision)

    def test_history_read_is_scoped_and_recovery_creates_new_copy(self):
        good=config();good['assumptions']['deposit_products']=[{'name':'Lower','rate_type':'fixed','rate_paid_ann':.0125,'balance_driver':{'balance_per_customer_spec':{'source':'weighted_sum','components':[1,2,3,4]}}},{'name':'Upper','rate_type':'fixed','rate_paid_ann':.03}]
        good['assumptions']['obs_exposures']=[{'name':'Operating Fees','fee_streams':[{'name':'Checks'},{'name':'Wires'}]}]
        initial=self.post(good);slug=initial.json()['slug'];version=store.list_versions(slug,user='analyst')[0]['id']
        self.post(config(0),initial.json()['revision'])
        response=self.client.get(f'/api/v31/engagement/{slug}/history/{version}')
        self.assertEqual(response.status_code,200);self.assertEqual(len(response.json()['config']['assumptions']['deposit_products']),2)
        restored=response.json()['config'];restored['scenario_name']='Example · Recovery'
        copied=self.client.post('/api/v31/engagement/save-current',json={'name':'Example Recovery','config':restored,'save_protocol':2,'expected_revision':None})
        self.assertEqual(copied.status_code,200,copied.text)
        self.assertEqual(store.load_engagement(slug,user='analyst')['assumptions']['value'],0)
        self.assertEqual(len(store.load_engagement(copied.json()['slug'],user='analyst')['assumptions']['deposit_products']),2)
        api.app.dependency_overrides[api.gate]=lambda:'other-user'
        self.assertEqual(self.client.get(f'/api/v31/engagement/{slug}/history/{version}').status_code,404)
        self.assertEqual(self.client.get(f'/api/v31/engagement/{slug}/revision').status_code,404)
        self.assertEqual(self.client.get(f'/api/v31/engagement/{slug}/history/not-a-version').status_code,404)

    def test_before_write_backup_failure_and_atomic_write_failure(self):
        initial=store.save_engagement(config(),'base',user='analyst',expected_revision=None)
        old=Path(initial['path']).read_bytes()
        with patch.object(store,'_record_version',side_effect=OSError('history unavailable')):
            with self.assertRaises(OSError):store.save_engagement(config(2),'base',user='analyst',expected_revision=initial['revision'])
        self.assertEqual(Path(initial['path']).read_bytes(),old)
        with patch.object(store.os,'replace',side_effect=OSError('replace failed')):
            with self.assertRaises(OSError):store.save_engagement(config(2),'base',user='analyst',expected_revision=initial['revision'])
        self.assertEqual(Path(initial['path']).read_bytes(),old)
        self.assertFalse(list(Path(initial['path']).parent.glob('.save-*.tmp')))
        self.assertEqual(store.load_engagement('base',user='analyst')['assumptions']['value'],1)

    def test_new_history_failure_reports_durable_save_and_keeps_predecessor(self):
        initial=store.save_engagement(config(),'base',user='analyst',expected_revision=None)
        original=store._record_version
        def fail_new(c,*args,**kwargs):
            if c['assumptions']['value']==2:raise OSError('history failed')
            return original(c,*args,**kwargs)
        with patch.object(store,'_record_version',side_effect=fail_new):
            result=store.save_engagement(config(2),'base',user='analyst',expected_revision=initial['revision'])
        self.assertIn('history_warning',result)
        self.assertEqual(store.load_engagement('base',user='analyst')['assumptions']['value'],2)
        self.assertTrue(any(v['config']['assumptions']['value']==1 for v in store.list_versions('base',user='analyst')))

    @unittest.skipUnless(os.name=='posix','Railway uses POSIX file locks')
    def test_concurrent_processes_only_one_writer_can_replace_revision(self):
        initial=store.save_engagement(config(),'base',user='analyst',expected_revision=None)
        with ProcessPoolExecutor(max_workers=2,mp_context=get_context('fork')) as pool:
            result=list(pool.map(concurrent_save,[(self.directory.name,initial['revision'],2),(self.directory.name,initial['revision'],3)]))
        self.assertEqual(sorted(result),['conflict','saved'])
        self.assertEqual(len(store.list_versions('base',user='analyst')),2)

    def test_complete_model_roundtrip_has_identical_financial_results(self):
        from .tests_r386_reuse import setup
        from .engine_q_a import run_pf_a
        c=setup()
        c['assumptions']['deposit_products'][0]['rate_paid_ann_spec']={
            'source':'entered','trajectory':'explicit','cadence':'year',
            'resolution':'step','values':[.0125,.0095,.0065,.0065,.0065],'extend':'hold'}
        expected=run_pf_a(copy.deepcopy(c))
        result=store.save_engagement(c,'complete',user='analyst',expected_revision=None)
        restored, revision=store.load_engagement_with_revision('complete',user='analyst')
        self.assertEqual(revision,result['revision'])
        self.assertEqual(run_pf_a(restored),expected)

    def test_reopen_and_restart_revision_preserves_complete_configuration(self):
        first=self.post(config());loaded=self.client.get('/api/v31/engagement/'+first.json()['slug'])
        fresh_client=TestClient(api.app)
        result=fresh_client.post('/api/v31/engagement/save-current',json={'config':loaded.json(),'name':'Example Base','save_protocol':2,'expected_revision':loaded.headers['etag'].strip('"')})
        self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(result.json()['revision'],first.json()['revision'])
        self.assertEqual(len(store.list_versions(first.json()['slug'],user='analyst')),1)
