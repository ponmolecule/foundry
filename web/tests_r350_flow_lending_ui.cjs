// r350: the flow-based lending Setup tab renders through the industrial layout.
// Renders the block against representative states and checks: every handler compiles, nothing
// undefined leaks, the controls a user needs are present, engine figures come from the run, and
// rendering never mutates the configuration.
const assert=require('node:assert/strict'),fs=require('fs'),vm=require('vm');
const html=fs.readFileSync(__dirname+'/console_v2.html','utf8');
for(const s of html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g))new vm.Script(s[1]);
const a=html.indexOf('// ===== r350: flow-based lending'),b=html.indexOf('const _flowReportingOpen = new WeakMap();');
assert(a>0&&b>a,'r350 block present');
const product=()=>({name:'Receivables advance',call_report_line:'loanOther',balance_mode:'funded_flow_level',opening_balance:0,rate_type:'fixed',yield_ann:.12,index_spread:0,charge_off_ann:.015,reserve_rate_pct_bal:.0125,opex_pct_ann:.004,opex_fixed_per_period:15000,measurement:'amortized',term_days:45,day_count:365,reserve_share:0,target_retention_share:.8,interest_balance_measure:'period_average',charge_off_balance_measure:'period_begin',allowance_mode:'reserve_rate',
  funded_flow_driver:{source:'entered',input_stage:'source_activity',start_period:1,ramp_periods:6,take_up_share:.6,flow_path:{unit_kind:'money_flow',trajectory:'flat',period:'month',value:2e6}},
  fee_streams:[{name:'Advance fee',basis:'transaction',quantity_series_id:'q1',driver:{source:'product_funded_flow',trajectory:'flat',params:{}},rate:{behavior:'flat',params:{pricing_basis:'pct_of_throughput',per_unit:.01}},cost:{kind:'none',params:{}}}]});
const ramp=k=>Array.from({length:36},(_,t)=>Math.min(t+1,6)*k);
const res={products:[{name:'Receivables advance',family:'lending',fundedInputVolume:Array(36).fill(2000),fundedVolume:ramp(200),calculatedOutstanding:ramp(295.89),bal:[0,...ramp(236.71)],interest:ramp(2.17),interestBasis:ramp(217),fees:ramp(2),passCost:Array(36).fill(0),rateQ:Array(36).fill(12)}],fee_stream_quantities:{series:{q1:ramp(200000)}}};
const ctx={cfg:{assumptions:{lending_products:[product()],loan_allocation_groups:[],n_periods:36}},lastRes:res,lastErrs:null,window:{},console,
 esc:s=>String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/"/g,'&quot;'),
 numInput:(p,u)=>`<input data-focus="${p}" value="1" onchange="setUnit('${p}','${u||''}',this.value)">`,PLAB:x=>x==='full'?'month':'mo',PPY:()=>12,
 LINE_LABELS_V31:{loanOther:'Loans: Other',loanCommercial:'Loans: Commercial & Industrial'},LOAN_KEYS:['loanOther','loanCommercial'],
 _loanFlowDraft:{},_flowLegacyFeeOpen:new WeakMap(),_loanBalanceMode:p=>p.balance_mode,catalogSources:()=>null,_seriesSourcePeriods:()=>36,
 _explicitSchedulePreviewHtml:()=> '<div class="explicit-preview"></div>',growthSpecInline:p=>`<select onchange="setGrowthField('${p}','rate',this.value)"></select>`,
 _loanRepaymentProfileHtml:()=> '<div class="fld wide">profile</div>',_faSeriesEditor:(p,s,l)=>`<div class="sec-managed-series"><span class="sec-book-label">${l}</span><input onchange="faSeriesValue('${p}','value',this.value,'rate')"></div>`,
 _prdLab:x=>String(x),renderContent(){},refresh(){},requestAnimationFrame(){} ,document:{querySelectorAll:()=>[]}};
vm.createContext(ctx);vm.runInContext(html.slice(a,b),ctx);
const render=()=>ctx._lfxSetupHtml(0,ctx.cfg.assumptions.lending_products[0],'assumptions.lending_products.0');
const check=(out,tag)=>{assert(!/undefined|NaN|\[object Object\]/.test(out),tag+' leaks undefined/NaN');
  for(const m of out.matchAll(/on(?:change|click|input)="([^"]+)"/g))new vm.Script(m[1].replace(/&quot;/g,'"').replace(/&amp;/g,'&'));};
let before=JSON.stringify(ctx.cfg),out=render();
assert.equal(JSON.stringify(ctx.cfg),before,'rendering must not mutate the configuration');check(out,'default');
['Funded volume','Exposure &amp; retention','Credit &amp; allowance','Pricing','Fee streams','Costs &amp; accounting','Reporting'].forEach((t,k)=>assert(out.includes(`<span class="no">0${k+1}</span><span class="tt">${t}</span>`),'section '+t));
assert((out.match(/class="lfx-s c"/g)||[]).length===2,'Costs and Reporting start collapsed');
['Input represents','Volume source','Source activity','Flow period','Trajectory','Starts in','Take-up share','Months to full size','Funded at full size','Repayment model','Exposure term','Day count','Target retained share','Funded volume held aside','Interest accrues on','Shared balance cap','Charge-offs','Charged on','Allowance method','ALLL reserve','Rate type','Yield'].forEach(t=>assert(out.includes('<label>'+t),'missing '+t));
assert(out.includes('>2,000<small>')&&out.includes('>1,200<small>')&&out.includes('>1,420<small>'),'strip shows engine values at the first full-size month');
assert(out.includes('Revenue · M6')&&out.includes('>13.02<small>'),'revenue = engine interest + fees at M6');
assert(out.includes("loanFundedTrajectoryChange(0,'growth')")&&out.includes("loanFundedStageChange(0,'funded_volume')")&&out.includes("loanRepaymentMode(0,'profile')"),'segments call the existing handlers');
assert(out.includes("setUnit('assumptions.lending_products.0.funded_flow_driver.take_up_share','pct',this.value)"),'take-up writes the same field');
assert(/lfx-add" disabled[^>]*>\+ Fee on distributed balance/.test(out),'distributed-balance fee requires a shared cap');
// floating, cap, schedule, retained fee, fair value, all sections open
const p=ctx.cfg.assumptions.lending_products[0];
Object.assign(p,{rate_type:'float',index:'effr',index_spread:.035,allocation_group_id:'cap-1',measurement:'fair_value',fee_yield_ann:.005});
ctx.cfg.assumptions.loan_allocation_groups=[{id:'cap-1',cap_source:'entered'}];p.funded_flow_driver.flow_path.trajectory='growth';
['acct','rep'].forEach(id=>ctx.lfxToggle(0,id));
out=render();check(out,'variant');
assert(out.includes('Spread over EFFR')&&out.includes('Reference index')&&!out.includes('<label>Yield<'),'floating pricing fields');
assert(out.includes('Cap for cap-1')&&!/lfx-add" disabled[^>]*>\+ Fee on distributed/.test(out),'cap enables distributed fee');
assert(out.includes('Retained average balance fee')&&out.includes('DCF discount spread')&&!out.includes('<label>ALLL reserve'),'retained fee row, fair value fields');
assert(out.includes("setGrowthField("),'growth editor reused');
assert((out.match(/class="lfx-s c"/g)||[]).length===0,'toggled sections open');
// stale run: muted
ctx.lastErrs=[{message:'x'}];out=render();assert(out.includes('lfx-rib stale'),'failed run mutes the strip');
// no run yet
ctx.lastRes=null;ctx.lastErrs=null;ctx.window._lfxLast=null;out=render();check(out,'no run');assert(out.includes('Figures appear after the next complete run.'),'no-run caption');
console.log('PASS r350 flow-lending setup: handlers compile, no leaks, engine-sourced strip, state variants, read-only render');
