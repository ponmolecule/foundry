"""r396: labelled Remove feed with confirmation and linked-item list (console only)."""
import subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];H=(ROOT/'web/console_v2.html').read_text()
ok=fail=0
def ck(name,cond):
    global ok,fail
    print(('  PASS  ' if cond else '  FAIL  ')+name);ok+=bool(cond);fail+=not cond
ck('Remove feed is a labelled button in feed settings','onclick="cacnRemoveAsk(true)">Remove feed</button>' in H)
ck('removal asks first and lists linked items','function _cacrmLinks(fn,fd)' in H and 'function cacnRemoveConfirm()' in H)
ck('the unlabelled remove control is retired','#card-cac .cacn-set .cac-feed-head>button.cx{display:none}' in H)
r=subprocess.run(['node',str(ROOT/'web/tests_r396_remove_feed.cjs')],capture_output=True,text=True,cwd=str(ROOT),timeout=280)
ck('browser behaviour (node)',r.returncode==0)
if r.returncode:print(r.stdout[-1500:],r.stderr[-1500:])
print(f"\n{ok} passed, {fail} failed")
raise SystemExit(1 if fail else 0)
