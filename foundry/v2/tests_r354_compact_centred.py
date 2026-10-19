"""r354: compact sections, vertical centring, one-row figures (console only)."""
import subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];H=(ROOT/'web/console_v2.html').read_text()
ok=fail=0
def ck(name,cond):
    global ok,fail
    print(('  PASS  ' if cond else '  FAIL  ')+name);ok+=bool(cond);fail+=not cond
ck('sections whose inputs fit on one row are marked compact',"if(ro&&fl.length&&span<=4&&!lg.length)b.classList.add('compact');" in H)
ck('sections with leftover legacy blocks never go compact','!lg.length' in H)
ck('rail, inputs and chart column centre vertically','.lfx-b.has-ro>.lfx-ro{display:flex;flex-direction:column;justify-content:center}' in H)
ck('figures sit in one row of four','.lfx-ro .ro-k{grid-template-columns:repeat(4,minmax(0,1fr))}' in H)
ck('figure labels wrap rather than truncate','.lfx-ro .ro-k span{white-space:normal;line-height:1.3}' in H)
r=subprocess.run(['node',str(ROOT/'web/tests_r354_compact_centred.cjs')],capture_output=True,text=True)
ck('compact rule and layout styles (node)',r.returncode==0)
if r.returncode:print(r.stdout,r.stderr)
print(f"\n{ok} passed, {fail} failed")
raise SystemExit(1 if fail else 0)
