const fs=require('fs'),vm=require('vm'),assert=require('assert');
const html=fs.readFileSync(__dirname+'/console_v2.html','utf8');
for(const m of html.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script>/gi))if(!/\bsrc=/.test(m[1]))new vm.Script(m[2]);
const cfg={assumptions:{obs_exposures:[{fee_streams:[
 {name:'Practice Count',basis:'account',quantity_series_id:'practice',driver:{source:'customer_acquisition_count',ref:'customers'}},
 {name:'Card base',basis:'transaction',quantity_series_id:'card',driver:{source:'stream_ref',ref:'Practice Count',params:{coefficient:{kind:'pct',semantics:'share',value:.6}}}},
 {name:'Purchases',basis:'transaction',quantity_series_id:'purchase',driver:{source:'stream_ref',ref:'Card base',params:{coefficient:{kind:'amount_per_source_unit',value:23000}}}},
 {name:'Cross-family source',basis:'transaction',quantity_series_id:'cross',driver:{source:'fee_stream_quantity',ref:'funded'}}
 ]}],lending_products:[{fee_streams:[{basis:'transaction',quantity_series_id:'funded',driver:{source:'product_funded_flow'}}]}],deposit_products:[]}};
const practice=Array.from({length:60},(_,i)=>(i+1)*4.8125),card=practice.map(x=>x*.6),purchase=card.map(x=>x*23000);
const ctx={cfg,window:{},PPY:()=>12,esc:s=>String(s).replaceAll('&','&amp;').replaceAll('"','&quot;'),lastRes:{fee_stream_quantities:{series:{practice,card,purchase,cross:purchase}}},document:{querySelectorAll:()=>[]}};
vm.createContext(ctx);
for(const name of ['_numInput'])vm.runInContext(html.split('\n').find(l=>l.startsWith('function '+name+'(')),ctx);
vm.runInContext(html.slice(html.indexOf('function _stOwner('),html.indexOf('function _feeStreamsSectionHtml(')),ctx);
vm.runInContext(html.slice(html.indexOf('function _feeStreamQuantityKind('),html.indexOf('function _feePctSemantics(')),ctx);
vm.runInContext(html.slice(html.indexOf('function _explicitPreviewHtml('),html.indexOf('function _explicitSchedulePreviewHtml(')),ctx);
vm.runInContext(html.slice(html.indexOf('// r358: a fee stream previews'),html.indexOf('_feeGlobal.addFeeCostPool=',html.indexOf('// r358: a fee stream previews'))),ctx);
const before=JSON.stringify(cfg);let h=ctx._feeStreamResultPreviewHtml(0,1);
assert(h.includes('2.8875'),'M1 after 60%');assert(!h.includes('4.8125'),'must not repeat upstream M1');
assert(h.includes('Calculated count'));assert(h.includes('60 periods'));assert(h.includes('View all'));assert(!h.includes('Show source'));assert(!h.includes('Hide source'));
assert(h.includes('eps-c'));assert(h.includes('M60'));assert(h.includes('173.25'));
assert(ctx._feeStreamResultBody('purchase').includes('$000s'));assert(ctx._feeStreamResultBody('purchase').includes('66.4125'));
assert(ctx._feeStreamResultBody('cross').includes('$000s'),'cross-family monetary semantics');
ctx.lastRes.fee_stream_quantities.series.card[0]=0;assert(ctx._feeStreamResultBody('card').includes('M1 0'));
ctx.lastRes.fee_stream_quantities.series.card[0]=9.125;assert(ctx._feeStreamResultBody('card').includes('9.125'),'reads engine result, never calculates source times .6 itself');
assert.equal(JSON.stringify(cfg),before,'rendering does not change inputs');
cfg.assumptions.obs_exposures[0].fee_streams.reverse();const reordered=JSON.stringify(cfg);assert(ctx._feeStreamResultBody('card').includes('9.125'),'stable ID after reorder');
let openState=false;
const el={innerHTML:'old',getAttribute:()=> 'card',querySelector:()=>({get open(){return true},set open(v){openState=v;}})};
ctx.document.querySelectorAll=()=>[el];ctx.refreshFeeStreamResultPreviews();assert(el.innerHTML.includes('9.125'));assert(openState,'expanded schedule retained across output refresh');
ctx.PPY=()=>4;assert(ctx._feeStreamResultBody('card').includes('Q1'));
ctx.lastRes=null;assert(ctx._feeStreamResultBody('card').includes('Run the model successfully'));
assert(ctx._feeStreamResultBody('missing').includes('unavailable'));
const editor=html.slice(html.indexOf('function _feeStreamsSectionHtml('),html.indexOf('function ',html.indexOf('function _feeStreamsSectionHtml(')+10));
assert(editor.includes('_feeStreamResultPreviewHtml||')); 
assert(!editor.includes('_lsrcLive'));assert(!editor.includes('data-fee-customer-count-preview'));assert(!editor.includes('data-fee-activity-preview'));
assert.equal(JSON.stringify(cfg),reordered,'refresh does not change inputs');
console.log('PASS own stream quantities after share, fractional counts, native monetary scaling, compact/full preview, stable IDs, refresh/no-run, no duplicate source blocks and full script syntax');
