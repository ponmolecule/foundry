"""Exercise real cost renderer: billing and assumption periods remain distinct."""
from pathlib import Path
import subprocess

def main():
    html=Path('web/console_v2.html').read_text()
    a=html.index('      // Axis 6: cost side');b=html.index("      h += '</div>';",a)
    render=html[a:b]
    a=html.index('function _feeEnsureCostFactor(')
    helpers=html[a:html.index('\n',html.index('function _feeClearCostMultiplierSchedule(',a))]
    js=r'''
const assert=require('node:assert/strict');const fs=require('node:fs');
function _pf(v){return Number(v)};function esc(v){return String(v)};function renderContent(){};function refresh(){};
function _explicitSchedulePreviewHtml(){return '<preview>'};function _feeParseExplicitValues(t){return t.split(',').map(Number)};
let st;function _stOwner(){return {fee_streams:[st]}};
function render(kind,params={},basis='account'){
 st={cost:{kind,params}};let h='';const ck=kind,rb='flat',_fi=0,si=0,sb='test';
''' + render + "\nreturn h;}\n" + helpers + r'''
let params={period:'month',cost_per_account:10},before=JSON.stringify(params);
let out=render('per_account',params);
assert(out.includes('Cost ($/account)'));assert(out.includes('value="10"'));assert(out.includes('Account / month'));
assert(out.includes('+ Add multiplier'));assert(!out.includes('Cost multiplier path'));assert(!out.includes('Growth period'));assert(!out.includes('Schedule period'));
assert.equal(JSON.stringify(params),before);
fs.writeFileSync('/tmp/r346-cost-preview.html','<html><style>body{font:16px Arial;max-width:900px;margin:30px;color:#333}.grid{display:grid;grid-template-columns:1fr 1fr;gap:18px}.fld{display:flex;flex-direction:column;gap:7px}.wide{grid-column:1/-1}select,input,button{font:16px Arial;padding:10px;border:1px solid #ccc;border-radius:6px}.memo{font-size:12px}</style><h2>Charge Card Servicing · Costs</h2><div class="grid">'+out+'</div></html>');
_feeEnsureCostMultiplier(0,0);assert.equal(params.multiplier_path.value,1);
out=render('per_account',params);assert(out.includes('Cost multiplier path'));assert(!out.includes('Multiplier growth period'));assert(!out.includes('Multiplier schedule period'));
params.multiplier_path={value:.8,trajectory:'growth',period:'quarter',growth_spec:{rate:.05}};
params.factor_path={value:10,trajectory:'growth',period:'year',growth_spec:{rate:.03}};
before=JSON.stringify(params);out=render('per_account',params);assert(out.includes('Growth period'));assert(out.includes('Multiplier growth period'));assert.equal(JSON.stringify(params),before);
params.factor_path={trajectory:'explicit_schedule',period:'month',schedule:{1:10,2:12}};params.multiplier_path={trajectory:'explicit_schedule',period:'quarter',schedule:{1:.8,2:1}};
out=render('per_account',params);assert(out.includes('Schedule period'));assert(out.includes('Multiplier schedule period'));assert(out.includes('feeCostMultiplierPaste_0_0'));
out=render('periodic_amount_opex',{amount:12000},'flat');assert(out.includes('Amount is per'));assert(out.includes('value="12"'));assert(!out.includes('+ Add multiplier'));
for(const kind of ['per_unit','pct_of_revenue','pct_of_revenue_opex','pct_of_throughput_opex']){out=render(kind,{cost_per_unit:175,pct:.02},'transaction');assert(out.includes('Cost path'));assert(!out.includes('Schedule period'));}
console.log('PASS cost controls: flat/growth/explicit, separate billing, optional/authored multipliers, legacy values, periodic amounts and read-only rendering');
'''
    subprocess.run(['node'],input=js,text=True,check=True)
if __name__=='__main__':main()
