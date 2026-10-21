import os,tempfile,unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
import app as api

class SessionSafetyTests(unittest.TestCase):
    def test_renew_valid_only_and_preserves_cookie_policy(self):
        with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,FOUNDRY_DATA_DIR=d,FOUNDRY_COOKIE_SECURE='0'):
            c=TestClient(api.app)
            self.assertEqual(c.post('/api/auth/renew').status_code,401)
            c.cookies.set('foundry_session',api.make_session('analyst',-1))
            self.assertEqual(c.post('/api/auth/renew').status_code,401)
            token=api.make_session('analyst',1000)
            c.cookies.clear();c.cookies.set('foundry_session',token)
            r=c.post('/api/auth/renew');self.assertEqual(r.status_code,200)
            self.assertEqual(r.json()['user'],'analyst')
            self.assertIn('HttpOnly',r.headers['set-cookie']);self.assertIn('SameSite=strict',r.headers['set-cookie'])
            self.assertEqual(r.headers['cache-control'],'no-store')
            self.assertNotEqual(r.cookies['foundry_session'],token)
            self.assertEqual(api.verify_session(r.cookies['foundry_session']),'analyst')

    def test_reauth_cannot_switch_account(self):
        with patch('foundry.auth.authenticate',return_value='other'):
            r=TestClient(api.app).post('/api/auth/login',json={'username':'other','password':'secret','expected_user':'original'})
            self.assertEqual(r.status_code,403);self.assertNotIn('set-cookie',r.headers)
        with patch('foundry.auth.authenticate',return_value='original'),tempfile.TemporaryDirectory() as d,patch.dict(os.environ,FOUNDRY_DATA_DIR=d):
            r=TestClient(api.app).post('/api/auth/login',json={'username':'original','password':'secret','expected_user':'original'})
            self.assertEqual(r.status_code,200);self.assertIn('set-cookie',r.headers)

    def test_save_account_guard_precedes_store(self):
        api.app.dependency_overrides[api.gate]=lambda:'other'
        try:
            with patch('foundry.store.save_engagement') as save:
                r=TestClient(api.app).post('/api/v31/engagement/save-current',json={'name':'test','config':{'a':1},'expected_user':'original'})
                self.assertEqual(r.status_code,409);save.assert_not_called()
        finally:api.app.dependency_overrides.clear()
