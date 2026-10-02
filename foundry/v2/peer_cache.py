"""Bounded public-peer response cache with single-flight and finite waits.

No engagement/model inputs are cached. Failed requests are never cached.
"""
import copy,hashlib,os,threading,time
from collections import OrderedDict
from concurrent.futures import Future,TimeoutError
_LOCK=threading.Lock()
_CACHE=OrderedDict()
_PENDING={}
_SLOTS=threading.BoundedSemaphore(3)
TTL=120
MAX_ENTRIES=128


def cached_peer(key,load):
    scope=hashlib.sha256((os.environ.get('CHARTERIQ_DATABASE_URL','')+'|'+os.environ.get('CHARTERIQ_SUBSTRATE_URL','')+'|'+os.environ.get('FOUNDRY_ALLOW_FIXTURE_BANDS','')).encode()).hexdigest()
    key=(scope,key)
    with _LOCK:
        hit=_CACHE.get(key)
        if hit and time.monotonic()-hit[0]<TTL:
            _CACHE.move_to_end(key);return copy.deepcopy(hit[1])
        future=_PENDING.get(key);owner=future is None
        if owner:future=Future();_PENDING[key]=future
    if not owner:return copy.deepcopy(future.result(timeout=20))
    try:
        if not _SLOTS.acquire(timeout=10):raise TimeoutError('Peer retrieval is busy; retry shortly.')
        try:value=load()
        finally:_SLOTS.release()
        with _LOCK:
            _CACHE[key]=(time.monotonic(),copy.deepcopy(value));_CACHE.move_to_end(key)
            while len(_CACHE)>MAX_ENTRIES:_CACHE.popitem(last=False)
        future.set_result(value);return copy.deepcopy(value)
    except BaseException as exc:
        future.set_exception(exc);raise
    finally:
        with _LOCK:_PENDING.pop(key,None)
