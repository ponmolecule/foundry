const fs=require('fs'),vm=require('vm'),assert=require('assert'),H=fs.readFileSync(__dirname+'/console_v2.html','utf8');
const cfg={assumptions:{obs_exposures:[{name:'Fees',fee_streams:[
 {name:'Count',quantity_series_id:'count',basis:'account',driver:{source:'constant'}},
 {name:'Purchase',quantity_series_id:'purchase',basis:'transaction',driver:{source:'stream_ref',ref:'Count',trajectory:'derived',params:{coefficient:{kind:'amount_per_source_unit',value:23000}}}},
 {name:'Interchange',quantity_series_id:'gross',basis:'transaction',driver:{source:'stream_ref',ref:'Purchase',trajectory:'derived',params:{coefficient:{kind:'pct',semantics:'share',value:1}}}},
 {name:'Network',quantity_series_id:'network',basis:'transaction',driver:{source:'stream_ref',ref:'Purchase',trajectory:'flat',params:{}}}
 ]}],lending_products:[{name:'Loan',fee_streams:[{name:'Loan count',quantity_series_id:'loan-count',basis:'account',driver:{source:'constant'}}]}]}};
const res={fee_stream_quantities:{series:{count:[2.8875,3.5],purchase:[66412.5,80500],gross:[66412.5,80500],network:[66412.5,80500],'loan-count':[2.8875,3.5]}}};
const ctx={cfg,window:{},lastRes:res,PPY:()=>12,esc:String,_numInput:v=>String(v),_lfgArr:f=>cfg.assumptions[f==='obs'?'obs_exposures':f==='lending'?'lending_products':'deposit_products'],_lfgCtx:()=>({res,P:{fees:[1,2]},ref:1}),_lfxCtx:()=>({res,P:{fees:[1,2]},ref:1}),_loanBalanceMode:()=> 'funded_flow_level',_lfxPer:()=> 'month',_lfxQ:i=>'M'+i,_lfxAmt:String,_lfxSparkSvg:a=>'<spark>'+a.join(',')+'</spark>',_ensureWorkforce:()=>({})};
vm.createContext(ctx);
for(const [a,b] of [['function _stOwner(','function _feeStreamsSectionHtml('],['function _feeStreamQuantityKind(','function _feePctSemantics('],['function _feeStreamDisplay(','// r358: a fee stream previews'],['function _lfxLiveHtml(','function refreshLfxLive(']])vm.runInContext(H.slice(H.indexOf(a),H.indexOf(b,H.indexOf(a))),ctx);
const before=JSON.stringify(cfg);
for(const si of [1,2,3]){const out=ctx._lfxLiveHtml('sro',0,si);assert(out.includes('$000s'));assert(out.includes('66.4125'));assert(out.includes('80.5'));assert(!out.includes('66,413'));assert(out.includes('Calculated quantity'));}
const counts=ctx._lfxLiveHtml('sro',0,0);assert(counts.includes('2.8875'));assert(counts.includes('<b>count</b>'));
const mini=ctx._lfxLiveHtml('fqty',0,0);assert(mini.includes('2.8875 count'));assert(!mini.includes('0.0028875'));
const at=H.indexOf('_feeGlobal.feeStreamTrajectoryChange=');vm.runInContext(H.slice(at,H.indexOf('_feeGlobal.feeStreamBasisChange=',at)),Object.assign(ctx,{_feeGlobal:{},renderContent(){},refresh(){},_feeEnsureAccountLevel(){}}));
ctx._feeGlobal.feeStreamTrajectoryChange(0,2,'flat');assert(!cfg.assumptions.obs_exposures[0].fee_streams[2].driver.params.coefficient,'leaving Derived removes active coefficient');
assert(H.includes('Follows source unchanged (100%)'));assert(H.includes('Set the fee rate separately under Pricing.'));
console.log('PASS stream charts and lending chips use own resolved values and shared units; fractional counts retained; Flat identity meaning explicit; leaving Derived removes its coefficient');
