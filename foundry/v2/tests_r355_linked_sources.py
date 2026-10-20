"""r355: segmented opex sub-tabs, closable capital entry box, linked-source previews everywhere the run publishes the source (console only)."""
import re,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];RAW=(ROOT/'web/console_v2.html').read_text()
# call sites reach the helpers through globalThis so functions evaluated in isolation still render
H=RAW.replace("(globalThis._lsrcLive||(()=>''))(",'_lsrcLive(').replace("(globalThis._lsrcWrap||((k,b)=>b||''))(",'_lsrcWrap(').replace("(globalThis._lsrcCurrentOpt||((k,i,j,v,o)=>o))(",'_lsrcCurrentOpt(')
ok=fail=0
def ck(name,cond):
    global ok,fail
    print(('  PASS  ' if cond else '  FAIL  ')+name);ok+=bool(cond);fail+=not cond
ck('opex sub-tabs are a segmented control with a graphite active tab','.cfg-subtab.on{background:#2C2C2C;color:#FFFFFF;font-weight:600}' in H)
ck('capital entry box starts closed','{preopening:-1,fixedassets:-1}' in H)
ck('picking the open row closes it',"window._capitalInputSelection[kind]=(cur===index?-1:index)" in H)
ck('entry box has a Done button',"done.className='capital-input-done'" in H)
ck('every preview shares one show/hide wrapper','function _lsrcWrap(key,body,noun,attrs)' in H)
for name,pat in [('tiered terms',"_lsrcWrap('tier:'"),('customer acquisition links',"_lsrcWrap('cac:'"),('linked customer counts',"_lsrcWrap('cust:'"),('cost-pool eligible cost',"_lsrcWrap('pool:'")]:
    ck('toggle on '+name,pat in H)
for name,pat in [('stream calculated quantity',"_feeStreamResultPreviewHtml||"),('OBS AUC feed',"_lsrcLive('auc',p.managed_notional_source"),
                 ('deposit linked balance',"h+=_lsrcLive('fqk',_l.series_id"),('deposit derived activity',"_lsrcLive(_l.kind==='lending_funded_flow'?'fund':'fqk'"),('flow-lending upstream flow',"b+=_lsrcLive('fqk',fd.series_id"),
                 ('other income',"h+=_lsrcLive('fqk',line.source_series_id"),('external tax',"_lsrcLive('fqk',x.source_series_id"),('other assets terms',"_lsrcLive('oat',i+'.'+j"),('other liabilities terms',"_lsrcLive('olt',i+'.'+j"),
                 ('fixed-asset driver',"_lsrcLive('wf',link.series_id"),('managed securities target',"_sb+=_lsrcLive('bs',_dep?")]:
    ck('live preview on '+name,pat in H)
ck('previews refresh after every run, after the tab-specific refresh chain',"refreshStreamFigures(); }\n  if(typeof refreshLsrcLive==='function') refreshLsrcLive();   // r355" in H)
ck('helper calls outside the helper block are guarded',"globalThis._lsrcLive||" in RAW and "globalThis._lsrcWrap||" in RAW)
r=subprocess.run(['node',str(ROOT/'web/tests_r355_linked_sources.cjs')],capture_output=True,text=True)
ck('resolver and rendering (node)',r.returncode==0)
if r.returncode:print(r.stdout,r.stderr)
print(f"\n{ok} passed, {fail} failed")
raise SystemExit(1 if fail else 0)
