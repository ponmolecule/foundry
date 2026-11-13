"""Measure preview/full parity and two queued previews on a supplied config.

Run from the repository root: python tools/preview_benchmark.py CONFIG.json
Does not change the configuration or save engagement contents.
"""
import json
import sys
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from foundry.v2.preview_jobs import PreviewJobs
from foundry.v2.run_q import run_v2


def main():
    cfg=json.loads(Path(sys.argv[1]).read_text())
    q=PreviewJobs();start=time.perf_counter()
    ids=[q.submit('benchmark-'+str(i),'benchmark',cfg)['job_id'] for i in range(2)]
    done={};results=[]
    while len(done)<2:
        for i,jid in enumerate(ids):
            if i in done:continue
            job=q.get('benchmark-'+str(i),jid)
            if job['status']=='failed':raise RuntimeError(job.get('errors') or job.get('message'))
            if job['status']=='completed':
                results.append(job['result'])
                done[i]={k:job[k] for k in ('queue_seconds','calculation_seconds')}
                done[i]['wall_seconds']=round(time.perf_counter()-start,3)
        time.sleep(.1)
    start=time.perf_counter();full=run_v2(cfg);elapsed=time.perf_counter()-start
    fields=('financials','products','workforce','funding','fee_stream_economics','fee_stream_quantities','tax_interim')
    for result in results:
        for field in fields:
            if result.get(field)!=full.get(field):raise AssertionError('Parity failed: '+field)
    print(json.dumps(dict(previews=done,full_seconds=round(elapsed,3),parity_fields=fields),indent=2))


if __name__=='__main__':main()
