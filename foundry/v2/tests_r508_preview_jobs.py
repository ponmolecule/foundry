"""Preview isolation, coalescing, bounds, failures, expiry, and full/base parity."""
import copy
import threading
import time
import unittest
from .preview_jobs import PreviewJobs


def wait(jobs, user, jid):
    deadline = time.monotonic()+10
    while time.monotonic()<deadline:
        j=jobs.get(user,jid)
        if j['status'] not in ('running','queued'):
            return j
        time.sleep(.005)
    raise AssertionError('job did not finish')


class JobsTests(unittest.TestCase):
    def test_coalescing_bounds_and_isolation(self):
        entered, release = threading.Event(), threading.Event()
        seen=[];active=0;peak=0
        def run(c, scope):
            nonlocal active,peak
            active+=1;peak=max(peak,active);seen.append(c['v']);entered.set()
            release.wait(3);active-=1
            return {'status':'completed','result':c}
        q=PreviewJobs(run,max_pending=1)
        a=q.submit('u','tab',{'v':1});self.assertTrue(entered.wait(1))
        self.assertEqual(q.submit('u','tab',{'v':1})['job_id'],a['job_id'])
        b=q.submit('u','tab',{'v':2})
        c=q.submit('u','tab',{'v':3})
        self.assertEqual(q.get('u',b['job_id'])['status'],'superseded')
        with self.assertRaises(OverflowError):q.submit('other','tab',{'v':4})
        with self.assertRaises(KeyError):q.get('other',a['job_id'])
        release.set()
        self.assertEqual(wait(q,'u',c['job_id'])['result'],{'v':3})
        self.assertEqual(seen,[1,3]);self.assertEqual(peak,1)
        self.assertEqual(q.submit('u','tab',{'v':3})['job_id'],c['job_id'])

    def test_failures_do_not_stop_worker(self):
        def run(c,scope):
            if c['v']==1:raise ValueError('Missing schedule: named input')
            if c['v']==2:raise RuntimeError('private server detail')
            return dict(status='completed',result=c)
        q=PreviewJobs(run)
        a=wait(q,'u',q.submit('u','t',{'v':1})['job_id'])
        self.assertEqual(a['http_status'],422);self.assertIn('named input',a['errors'][0]['message'])
        a=wait(q,'u',q.submit('u','t',{'v':2})['job_id'])
        self.assertEqual(a['http_status'],500);self.assertNotIn('private',a['message'])
        self.assertEqual(wait(q,'u',q.submit('u','t',{'v':3})['job_id'])['status'],'completed')

    def test_snapshot_scope_and_expiry(self):
        q=PreviewJobs(lambda c,s:dict(status='completed',result={'cfg':c,'scope':s}),ttl=.02)
        c={'nested':[1]};a=q.submit('u','t',c,'full');c['nested'][0]=9
        r=wait(q,'u',a['job_id'])
        self.assertEqual(r['result'],{'cfg':{'nested':[1]},'scope':'full'})
        time.sleep(.03)
        with self.assertRaises(KeyError):q.get('u',a['job_id'])
        with self.assertRaises(ValueError):q.submit('u','t',{},'unknown')
        with self.assertRaises(ValueError):q.submit('u','',{})

    def test_endpoint_ownership_and_submission(self):
        from fastapi.testclient import TestClient
        from unittest.mock import patch
        import app
        q=PreviewJobs(lambda c,s:dict(status='completed',result={'financials':c,'scope':s}))
        app.app.dependency_overrides[app.gate]=lambda:'u'
        try:
            with patch('foundry.v2.preview_jobs.jobs',q):
                cl=TestClient(app.app)
                r=cl.post('/api/v2/preview/jobs',json={'session_id':'t','config':{'v':1}})
                self.assertEqual(r.status_code,202);jid=r.json()['job_id']
                wait(q,'u',jid)
                self.assertEqual(cl.get('/api/v2/preview/jobs/'+jid).json()['result']['scope'],'base')
                app.app.dependency_overrides[app.gate]=lambda:'other'
                self.assertEqual(cl.get('/api/v2/preview/jobs/'+jid).status_code,404)
        finally:app.app.dependency_overrides.clear()

    def test_base_full_financial_parity(self):
        from .tests_r498_stress import BANK
        from .run_q import run_v2
        c=copy.deepcopy(BANK);before=copy.deepcopy(c)
        f=run_v2(c);b=run_v2(c,scope='base')
        for field in ('financials','products','workforce','funding','fee_stream_economics'):
            self.assertEqual(f.get(field),b.get(field),field)
        self.assertEqual(c,before)
        self.assertNotIn('calculation_scope',f)
        self.assertEqual(b['calculation_scope'],'base')
        self.assertEqual(set(b['scenarios']),{'base'})
        self.assertGreater(len(f['scenarios']),1)
        self.assertEqual(f['config_hash'],b['config_hash'])
        self.assertNotEqual(f['run_hash'],b['run_hash'])
        self.assertTrue(all(t['scenario']=='base' for t in b['constraint_tests']))
        with self.assertRaises(ValueError):run_v2(c,scope='invalid')


if __name__=='__main__':unittest.main()
