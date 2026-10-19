// r353: every product family renders through the industrial layout. Checks the engine strip and
// readouts for loans, deposits, commitments and fee products against a fixed run, with no leaks.
const assert=require('node:assert/strict'),fs=require('fs'),vm=require('vm');
const html=fs.readFileSync(__dirname+'/console_v2.html','utf8');
for(const s of html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g))new vm.Script(s[1]);
const a=html.indexOf('// ===== r350: flow-based lending'),b=html.indexOf('const _flowReportingOpen = new WeakMap();');
assert(a>0&&b>a&&html.slice(a,b).includes('// ===== r353: industrial layout for every product family'),'r353 block present');
const ser=(f)=>Array.from({length:36},(_,t)=>f(t));
const prod=(name,family,o)=>Object.assign({name,family,bal:[1000,...ser(t=>1000+50*(t+1))],rateQ:ser(()=>6),interest:ser(t=>5+t),fees:ser(()=>2),opex:ser(()=>1),passCost:ser(()=>0),co:ser(()=>0.5),alll:ser(t=>10+t),origq:ser(()=>80),gos:ser(()=>0)},o||{});
const res={products:[prod('Loan','lending'),prod('Dep','deposit',{interest:ser(()=>-3)}),prod('Commit','obs'),prod('Fees','obs',{bal:Array(37).fill(0)})]};
const ctx={cfg:{assumptions:{n_periods:36,lending_products:[{name:'Loan',rate_type:'fixed',runoff_per_period:.01,balance_mode:'rollforward'}],deposit_products:[{name:'Dep',rate_type:'fixed'}],obs_exposures:[{name:'Commit',fee_yield_ann:.0075,notional:2e7,growth_per_period:.03},{name:'Fees',_fee_product:true,managed_notional:{},fee_streams:[{},{}]}]}},
  lastRes:res,lastErrs:null,window:{},console,esc:s=>String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/"/g,'&quot;'),PLAB:x=>x==='full'?'month':'mo',PPY:()=>12,
  _prdGrpSummary:()=> 'summary',_prdPct:v=>(Number(v||0)*100).toFixed(2)+'%',_prdK:v=>'$'+Math.round(Number(v||0)/1000)+'k',_loanBalanceMode:p=>p.balance_mode||'rollforward',_loanFlowDraft:{},_flowLegacyFeeOpen:new WeakMap(),document:{querySelectorAll:()=>[]}};
vm.createContext(ctx);vm.runInContext(html.slice(a,b),ctx);
const clean=(h,t)=>{assert(!/undefined|NaN|\[object Object\]/.test(h),t+' leaks');for(const m of h.matchAll(/onclick="([^"]+)"/g))new vm.Script(m[1]);};
const L=ctx._lfgStripHtml('lending',0);clean(L,'loan strip');
assert(L.includes('Opening balance')&&L.includes('>1,000<')&&L.includes('Balance · M12')&&L.includes('>1,600<'),'loan strip reads the run');
assert(L.includes('Revenue · M12')&&L.includes('>18.00<'),'loan revenue = interest 16 + fees 2 at M12');
const D=ctx._lfgStripHtml('deposit',0);clean(D,'deposit strip');
assert(D.includes('Net cost · M12')&&D.includes('>2.00<'),'deposit net cost uses interest expense magnitude: 3 + 1 - 2');
const C=ctx._lfgStripHtml('obs',0);clean(C,'commitment strip');assert(C.includes('Notional · M12')&&C.includes('Net fee income · M12')&&C.includes('>1.00<'),'commitment strip');
const F=ctx._lfgStripHtml('obs',1);clean(F,'fee strip');assert(F.includes('Fee streams')&&!F.includes('AUC · M12'),'fee product without AUC series shows fees, not zero AUC');
for(const [fam,i,g] of [['lending',0,'balance'],['lending',0,'pricing'],['lending',0,'credit'],['lending',0,'costs'],['deposit',0,'pricing'],['obs',0,'balance'],['obs',1,'balance']]){const h=ctx._lfgRoHtml(fam,i,g);clean(h,fam+' '+g);assert(h.includes('ro-k')||h.includes('ro-empty'),fam+' '+g+' readout');}
assert(ctx._lfgRoHtml('obs',1,'balance').includes('Fee income'),'fee product readout charts fees');
ctx.lastRes=null;ctx.window._lfxLast=null;assert(ctx._lfgStripHtml('lending',0).includes('Figures appear after the next complete run.'),'no-run caption');
console.log('PASS r353 product layout: strips and readouts for loans, deposits, commitments and fee products');
