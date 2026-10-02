"""Regression checks for bounded retrieval and snapshot-only exports."""
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
import threading,time
from io import BytesIO
from openpyxl import load_workbook
from foundry.v2.peer_export import peer_comparison_workbook
from foundry.v2.peer_cache import cached_peer
from foundry.v2.peer_bands import _db_bands

def test_latest_extrema():
    calls=[]
    def run(self,sql,params):
        calls.append(sql)
        return [(1,9,8)] if 'MIN(value)' in sql else [(2026,2,2,3,4,5,6,8)]
    with patch('foundry.charteriq_client.CharterIQClient.configured',return_value=True),patch('foundry.charteriq_client.CharterIQClient._run',run):
        b=_db_bands('roa','broad',True)['bands'][0]
    assert b['min']==1 and b['max']==9
    assert 'LIMIT 1' in calls[0] and 'DISTINCT ON' not in calls[0]
    assert 'COUNT(DISTINCT cert)' in calls[1]
    def mismatch(self,sql,params):return [(1,9,7)] if 'MIN(value)' in sql else [(2026,2,2,3,4,5,6,8)]
    with patch('foundry.charteriq_client.CharterIQClient.configured',return_value=True),patch('foundry.charteriq_client.CharterIQClient._run',mismatch):
        assert 'min' not in _db_bands('roa','broad',True)['bands'][0]

def test_cache():
    count=[0];lock=threading.Lock()
    def load():
        with lock:count[0]+=1
        time.sleep(.04);return {'n':[1]}
    key=('workspace-test',time.monotonic())
    with ThreadPoolExecutor(max_workers=8) as pool:values=list(pool.map(lambda _:cached_peer(key,load),range(8)))
    assert count[0]==1
    values[0]['n'][0]=9
    assert cached_peer(key,load)['n']==[1]
    failkey=('failure-test',time.monotonic())
    try:cached_peer(failkey,lambda:1/0)
    except ZeroDivisionError:pass
    assert cached_peer(failkey,lambda:2)==2

def test_workbook():
    snapshot={'rows':[{'metric':'roa','label':'=HYPERLINK("x")','modeled':0,'band':{'quarter':'2026Q2','min':-1,'max':2,'n':3}}], 'vintage':{'corridor':{'roa':{'ages':[{'age_q':1,'min':0,'p50':1,'max':2,'n':1}]}},'observations':[{'cert':1,'name':'=malicious','year':2026,'quarter':1,'age_q':1,'metric':'roa','value':0}]},'modeled':{'roa':[0]}}
    with patch('foundry.charteriq_client.CharterIQClient._run',side_effect=AssertionError('Export must not fetch peers')):
        wb=peer_comparison_workbook(snapshot)
    out=BytesIO();wb.save(out);out.seek(0);wb=load_workbook(out)
    assert wb['Comparison']['A7'].data_type=='s'
    assert wb['Comparison']['C7'].value==0 and wb['Comparison']['F7'].value is None
    assert wb['Comparison']['L7'].number_format=='0'
    assert wb['Curated calculations']['B2'].data_type=='s'
    assert wb['Curated calculations']['C3'].data_type=='f'
    assert len(wb['Vintage comparison']._charts)==1
    assert wb['Vintage comparison']._charts[0].display_blanks=='gap'

def test_export_endpoint():
    from fastapi.testclient import TestClient
    import app
    app.app.dependency_overrides[app.gate]=lambda:'test'
    try:
        with TestClient(app.app) as client,patch('foundry.charteriq_client.CharterIQClient._run',side_effect=AssertionError('No peer query during export')):
            response=client.post('/api/v31/peer-comparison/export',json={'rows':[{'metric':'roa','band':{'min':0,'max':2,'n':300},'modeled':1}]})
            assert response.status_code==200 and response.content[:2]==b'PK'
            assert client.post('/api/v31/peer-comparison/export',json={'rows':[{'band':'invalid'}]}).status_code==422
    finally:app.app.dependency_overrides.clear()

if __name__=='__main__':
    for test in [test_latest_extrema,test_cache,test_workbook,test_export_endpoint]:test();print('PASS',test.__name__)
