const fs=require('fs'),vm=require('vm'),assert=require('assert'),{execFileSync}=require('child_process');
const h=fs.readFileSync('web/console_v2.html','utf8');
const fx=JSON.parse(execFileSync('python3',['-c',`import json
from foundry.v2.count_breakdown_fixture import config
from foundry.v2.run_q import run_v2
c=config();print(json.dumps({'cfg':c,'result':run_v2(c)}))`],{encoding:'utf8',maxBuffer:1<<26}));
const st=fx.cfg.assumptions.obs_exposures[2].fee_streams[5],spec=st.driver.params.count_multiplier_spec;
const ctx={_stOwner:()=>fx.cfg.assumptions.obs_exposures[2],lastRes:fx.result,lastErrs:[],PPY:()=>12,PERLAB:n=>'M'+n,esc:s=>String(s).replaceAll('&','&amp;').replaceAll('"','&quot;').replaceAll('<','&lt;'),_faSeriesEditor:()=>'',renderContent(){},refresh(){}};
vm.createContext(ctx);vm.runInContext(h.slice(h.indexOf('function feeCountBreakdown('),h.indexOf('function _sharedWeightedEditor(')),ctx);
const before=JSON.stringify(fx),html=ctx._feeCountBreakdownHtml(2,5,'assumptions.obs_exposures.2.fee_streams.5',spec);
assert.equal(JSON.stringify(fx),before,'render never mutates run or configuration');assert(!html.includes('<aside'));assert(!html.includes('<svg'));assert(html.includes('Explain calculation'));assert(!/<details class="fcb-explain" open/.test(html));assert(html.includes('Customize ratio label'));
const rec=fx.result.count_breakdowns.find(x=>x.quantity_series_id===st.quantity_series_id);assert(html.includes(ctx._fcbNum(rec.quantity[11],2)));assert(html.includes(ctx._fcbNum(rec.source[11],2)));assert(html.includes(ctx._fcbNum(rec.multiplier[11],6)));
ctx.fcbExplainToggle(2,5,true);assert(ctx._feeCountBreakdownHtml(2,5,'stream',spec).includes('<details class="fcb-explain" open'));assert.equal(JSON.stringify(fx),before,'disclosure state is not saved as financial input');
spec.count_label='Physicians per practice';const labeled=ctx._feeCountBreakdownHtml(2,5,'stream',spec);assert(labeled.includes('<th class="n">Physicians per practice</th>'));assert(labeled.includes('Physicians per practice · weighted'));ctx.lastErrs=['incomplete'];assert(ctx._feeCountBreakdownHtml(2,5,'stream',spec).includes('Last complete run; current inputs are incomplete'));
vm.runInContext(h.slice(h.indexOf('function _feeStreamSummaryStats('),h.indexOf('function _lfxLiveHtml(')),ctx);
const q={values:[10,20,30],financial:false,unit:'count'};assert.equal(ctx._feeStreamSummaryStats(q,{basis:'account'},2,n=>'M'+n).length,3);assert.equal(ctx._feeStreamSummaryStats(q,{basis:'transaction'},2,n=>'M'+n)[3][1],60);assert.equal(ctx._feeStreamSummaryStats({...q,financial:true,unit:'$000s'},{basis:'account'},2,n=>'M'+n)[3][1],60);assert.equal(ctx._feeStreamSummaryStats({...q,values:[10,null,30]},{basis:'transaction'},2,n=>'M'+n)[3][1],null);
assert(h.includes('.count-authoring .fcb{display:block'));assert(h.includes('table-layout:fixed'));assert(h.includes('@container(max-width:620px)'));assert(h.includes('data-label="Share (%)"'));
console.log('PASS r423 full-width table, optional read-only engine explanation, custom labels, no duplicate sidebar/chart, stock-count sums removed and flow/financial sums retained');
