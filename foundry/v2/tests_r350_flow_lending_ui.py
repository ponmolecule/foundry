"""r350: flow-based lending Setup and Fee streams tabs render through the industrial layout (console only)."""
import os,re,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];H=(ROOT/'web/console_v2.html').read_text()
ok=fail=0
def ck(name,cond):
    global ok,fail
    print(('  PASS  ' if cond else '  FAIL  ')+name);ok+=bool(cond);fail+=not cond
ck('flow card routes Setup through the industrial renderer',"if(_flowCard){   // r350" in H and "_lfxSetupHtml(i,p,base)" in H)
ck('flow card keeps the shared fee-stream editor and overrides grid',"'<div class=\"pp-sec\" data-pp=\"streams\">'+_feeStreamsSectionHtml(fam,p,base,1000+i)" in H and "ovGridHtml(fam,i)" in H)
ck('fee streams tab switches layout only for flow-based lending',"const _lfx=+_fi>=1000&&fam==='lending'" in H and "_loanBalanceMode(p)==='funded_flow_level';   // r350" in H)
ck('stream detail keeps st-tab/st-body hooks for stTabSet',"class=\"st-tab lfx-step" in H and '<div class="st-body" data-st-tab="${tab}">' in H)
ck('non-flow products keep the original stream layout',"h += '<div class=\"fld wide\" style=\"margin-top:8px\"><label style=\"color:#D4A65C\">Add a fee stream</label></div>';" in H)
ck('engine figures refresh in place after each run',"if(typeof refreshLfxLive==='function') refreshLfxLive();   // r350" in H)
ck('strip reads engine product series, not client arithmetic',all(k in H for k in ('P.fundedVolume','P.calculatedOutstanding','P.interestBasis','P.rateQ')))
ck('sections: open graphite, collapsed light',".lfx-s.c .lfx-h{background:#F7F7F6" in H and ".lfx-h{display:flex" in H)
ck('styles are scoped to the flow-lending layout',not re.search(r'\n\.(?:fld|st-body|prd-card)\s*\{',H.split('/* ===== r350')[1].split('</style>')[0]))
ck('r351: layout uses the full stage width (1180px cap lifted for flow lending)','#content .prd-card:has(.lfx) .fields' in H and 'max-width:none!important' in H)
ck('r351: wide screens add an engine readout column instead of stretching fields','@container (min-width:1320px)' in H and "_lfxLiveHtml('sro'" in H and 'const _LFX_RO=' in H)
ck('r352: framed canvas, content capped at 1880px and centred','max-width:1880px;margin-left:auto!important' in H and 'clamp(40px,5.5vw,180px)' in H)
ck('r352: boxes keep natural widths; extra width becomes gutter',".lfx-grid{grid-template-columns:repeat(4,minmax(0,196px));column-gap:28px;justify-content:start}" in H)
ck('r352: Browse / search sits at the edge of the capped selector','.lfx-f.s4:has(> .lfx-sel)>label{max-width:600px}' in H or '.lfx-f.s4:has(> .lfx-sel)>label' in H)
ck('r352: one equation per line in the formula rail','<span class="eq">outstanding = Σ cohorts × curve</span>' in H and '<span class="eq">retained = outstanding × share</span>' in H)
ck('r352: results chart carries a value scale','class="ro-yl"' in H and 'class="ro-k"' in H)
ck('build stamp',(ROOT/'BUILD_STAMP').read_text().strip().startswith('foundry-r3'))
r=subprocess.run(['node',str(ROOT/'web/tests_r350_flow_lending_ui.cjs')],capture_output=True,text=True)
ck('renderer test (node)',r.returncode==0)
if r.returncode:print(r.stdout,r.stderr)
print(f"\n{ok} passed, {fail} failed")
raise SystemExit(1 if fail else 0)
