"""r393: customer acquisition feed rail, all-feeds comparison and inline channel editor (console only)."""
import subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];H=(ROOT/'web/console_v2.html').read_text()
ok=fail=0
def ck(name,cond):
    global ok,fail
    print(('  PASS  ' if cond else '  FAIL  ')+name);ok+=bool(cond);fail+=not cond
ck('decorator runs before paint with the other layout hooks',"if(typeof cacnDecorate==='function') cacnDecorate();" in H)
ck('figures come from the engine result, not recomputed',"function _cacnRes(fn)" in H and "r.customer_acquisition?r.customer_acquisition[fn]" in H)
ck('channel edits reuse the existing driver editor',"det2.classList.add('cacn-editor')" in H and "window['_cacChSel_'+fn]=ch" in H)
ck('feed settings re-seat the existing controls',"['.cac-feed-head','details.cac-help','.cac-attr-box']" in H)
ck('results refresh in place after each run',"refreshCacSummaries=function(){const r=o.apply(this,arguments);try{cacnRefresh();}" in H)
ck('selection survives reloads and renames (series id)',"f.series_id===window._cacnSel" in H)
ck('customer counts are not summed across feeds','not additive across feeds' in H)
r=subprocess.run(['node',str(ROOT/'web/tests_r393_acquisition_layout.cjs')],capture_output=True,text=True,cwd=str(ROOT),timeout=280)
ck('browser behaviour (node)',r.returncode==0)
if r.returncode:print(r.stdout[-2000:],r.stderr[-2000:])
print(f"\n{ok} passed, {fail} failed")
raise SystemExit(1 if fail else 0)
