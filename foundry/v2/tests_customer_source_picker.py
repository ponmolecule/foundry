"""Unified customer source picker uses existing stable links without losing authored paths."""
from pathlib import Path
import subprocess

def main():
    html=Path('web/console_v2.html').read_text()
    handlers=html[html.index('_feeGlobal.feeCustomerCountMeasureChange='):html.index('_feeGlobal.feeCostPoolAddComponent=')]
    renderer=html[html.index('      // Axis 2: driver source'):html.index("      if(basis==='account'){",html.index('      // Axis 2: driver source'))]
    js=r'''
const assert=require('node:assert/strict');const _feeGlobal=globalThis;
const opts=[{series_id:'one',feed:'Direct practices'},{series_id:'two',feed:'Other practices'}];
const st={basis:'account',driver:{source:'constant',trajectory:'explicit_schedule',params:{level_schedule:{schedule:{1:7,2:8}}}},rate:{behavior:'flat',params:{}}};
function _stOwner(){return {fee_streams:[st]}};function _feeCustomerCountOptions(){return opts};
let renders=0,refreshes=0;function renderContent(){renders++};function refresh(){refreshes++};
function esc(x){return String(x).replaceAll('&','&amp;').replaceAll('"','&quot;')};
function _feeCustomerCountPreviewHtml(ref,measure){return ref+':'+measure};
function render(){let h='';const basis='account',src=st.driver.source,_fi=0,si=0,sb='test',streamNames=[];
''' + renderer + "\nreturn h;}\n" + handlers + r'''
const original=JSON.stringify(st.driver.params);
feeStreamDriverSourceChange(0,0,'cac_count:one');
assert.equal(st.driver.ref,'one');assert.equal(st.driver.measure,'period_end');assert.equal(refreshes,1);
let out=render();assert(out.includes('Customer acquisition › Direct practices › Customers'));assert(out.includes('Customer acquisition › Other practices › Customers'));
assert(!out.includes('Ending bank customers source'));assert.equal((out.match(/<select/g)||[]).length,2);
assert(out.includes('value="cac_count:one" selected'));assert(out.includes('Count measure'));
feeCustomerCountMeasureChange(0,0,'annual_count');feeStreamDriverSourceChange(0,0,'cac_count:two');
assert.equal(st.driver.ref,'two');assert.equal(st.driver.measure,'annual_count');
feeStreamDriverSourceChange(0,0,'constant');assert.equal(st.driver.trajectory,'explicit_schedule');assert.equal(JSON.stringify(st.driver.params),original);
feeStreamDriverSourceChange(0,0,'customer_acquisition_count');assert.equal(st.driver.ref,'two');assert.equal(st.driver.measure,'annual_count');
opts.pop();out=render();assert(out.includes('Missing customer source: two'));assert(out.includes('value="cac_count:two" selected'));
feeStreamDriverSourceChange(0,0,'cac_count:missing');assert.equal(st.driver.ref,'two');
assert.equal(JSON.stringify(st.driver.params),original);
console.log('Unified source picker: rendering, multiple feeds, legacy links, measures, missing references and schedule restoration pass.');
'''
    subprocess.run(['node'],input=js,text=True,check=True)
if __name__=='__main__':main()
