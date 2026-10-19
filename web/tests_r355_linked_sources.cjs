// r355: every published linked source previews through one resolver and one show/hide grammar.
const assert=require('node:assert/strict'),fs=require('fs'),vm=require('vm');
const html=fs.readFileSync(__dirname+'/console_v2.html','utf8');
for(const s of html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g))new vm.Script(s[1]);
const a=html.indexOf('// ===== r355: live linked-source previews'),b=html.indexOf('function _opexLinkedSourcePreview(lc){');
assert(a>0&&b>a,'r355 helper block present');
const ctx={cfg:{assumptions:{n_periods:3,nie_detail:{workforce:{total_count_series_id:'wf-total'}},lending_products:[{name:'Card',balance_series_id:'bal-card'}]}},window:{},console,
  esc:s=>String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/"/g,'&quot;'),fmtComma:v=>String(v),_numInput:v=>String(v),_opexPeriodTag:()=>'M',_pwNoRunNote:()=>'Run the model.',document:{querySelectorAll:()=>[]},
  lastRes:{fee_stream_quantities:{series:{q1:[16600,43570,98356]}},customer_acquisition:{Feed:{aucEndByMonth:[1,2,3]}},financials:{bs:{equity:[100,101,102,103]}},
    workforce:{series_ids:['r1','r2'],counts:[[1,2,3],[10,10,10]]},products:[{family:'lending',name:'Card',fundedVolume:[5,6,7]}],
    other_liabilities:{components:[{terms:[{driver:[9,8,7],driver_name:'Premises & fixed assets · net',driver_unit:'money'}]}]}}};
vm.createContext(ctx);vm.runInContext(html.slice(a,b),ctx);
const V=(k,x)=>Array.from(ctx._lsrcVals(k,x));
assert.deepEqual(V('fqk','q1'),[16.6,43.57,98.356],'monetary quantities in $000s');
assert.deepEqual(V('auc','Feed'),[1,2,3]);assert.deepEqual(V('bs','equity'),[100,101,102,103]);
assert.deepEqual(V('wf','wf-total'),[11,12,13],'total workforce sums roles');assert.deepEqual(V('wf','r1'),[1,2,3]);
assert.deepEqual(V('fund','bal-card'),[5,6,7],'lending funded flow by balance series id');
assert.deepEqual(V('olt','0.0'),[9,8,7]);
let h=ctx._lsrcLive('olt','0.0','Linked series','driver','money');
assert(h.includes('data-lsrc-live')&&h.includes('Premises &amp; fixed assets · net')&&h.includes('Hide source'),'live preview titled from the run');
assert(ctx._lsrcLive('bs','equity','Bank','x','money').includes('Open 100'),'balance-sheet stock starts with the opening value');
ctx.window._lsrcHidden={'bs:equity':true};assert(ctx._lsrcLive('bs','equity','Bank','x','money').includes('Linked source hidden'),'hidden state remembered per source');
ctx.lastRes=null;assert(ctx._lsrcLive('fq','q1','Q','x','native').includes('Run the model.'),'no-run note');
assert.equal(ctx._lsrcLive('fq','','Q','x','native'),'','no source, no preview');
const o=ctx._lsrcCurrentOpt('olt',0,0,'fixed_asset_level::net',[['workforce_role_count::wf','Workforce']]);assert.equal(o[0][0],'fixed_asset_level::net','unlisted current source is shown, not replaced by the first option');
console.log('PASS r355 linked-source previews: resolver, units, titles, hide state, current-source option');
