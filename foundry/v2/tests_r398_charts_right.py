"""r398: results charts stay on the right of the inputs (console layout only)."""
import subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];H=(ROOT/'web/console_v2.html').read_text()
ok=fail=0
def ck(name,cond,detail=''):
    global ok,fail
    print(('  PASS  ' if cond else '  FAIL  ')+name+('' if cond or not detail else '\n        '+str(detail)[:400]));ok+=bool(cond);fail+=not cond
ck('product steps keep the chart beside the inputs on narrower panes','@container lncpane (max-width:940px){.lfx.lnv .lnv-pane>section.lfx-s>.lfx-b.has-ro{grid-template-columns:minmax(0,1fr) clamp(240px,34%,340px)!important}' in H)
ck('only cramped steps (<560px) and phones stack','@container lncpane (max-width:559px)' in H and '@media (max-width:700px){.lfx.lnv .lnv-pane' in H)
ck('the r392 laptop rule no longer stacks charts','.lnv-ri{min-width:180px}.lnv-ps{flex-wrap:wrap}' in H)
ck('customer acquisition keeps its results column on the right','.cacn-pane{grid-template-columns:minmax(0,1fr) clamp(240px,30%,320px)}' in H)
r=subprocess.run(['node',str(ROOT/'web/tests_r398_charts_right.cjs')],capture_output=True,text=True,cwd=str(ROOT),timeout=480)
ck('browser behaviour (node)',r.returncode==0,(r.stdout[-1500:]+r.stderr[-1500:]) if r.returncode else '')
print(f"\n{ok} passed, {fail} failed")
raise SystemExit(1 if fail else 0)
