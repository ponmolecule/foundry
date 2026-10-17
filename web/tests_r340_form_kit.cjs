// r340: the Securities & AOCI component editors render through the form kit.
// Renders each editor against a representative configuration and checks: every handler compiles,
// no undefined/NaN leaks into the markup, the controls a user needs are present, and rendering
// never mutates the configuration.
const assert=require('node:assert/strict'),fs=require('fs'),vm=require('vm');
const html=fs.readFileSync(__dirname+'/console_v2.html','utf8');
for(const script of html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g))new vm.Script(script[1]);
const flat=(v,unit)=>({source:'entered',trajectory:'flat',value:v,unit});
const cfg={assumptions:{periods_per_year:12,other_assets:0,other_liabilities:0,
 obs_exposures:[{name:'Services',fee_streams:[{name:'Revenue',quantity_series_id:'source',rate:{behavior:'flat'}}]}],
 balance_components_model:{enabled:true,inputs:[{id:'acct',name:'Customer accounts',unit:'count',spec:flat(10,'count')}],components:[
  {id:'cover',name:'Cash cover',treatment:'cash_allocation',cap_at_available_cash:true,interest_balance_measure:'prior_end',prior_interest_initialization:'zero',terms:[{source_spec:{source:'input_ref',input_id:'acct'},sign:-1,factors:[flat(2,'money_per_unit')]}],yield_spec:{source:'reference_rate',index:'effr',spread_spec:flat(-.005,'rate')}},
  {id:'rest',name:'Remaining cash',treatment:'residual_cash',terms:[],yield_spec:flat(0,'rate')},
  {id:'asset',name:'Fed stock',treatment:'earning_asset',income_method:'entered_amount',income_amount_spec:{source:'entered',trajectory:'flat',value:5,period:'year'},terms:[{source_spec:{source:'entered',trajectory:'explicit',cadence:'month',values:[1,2,3],unit:'money'},factors:[]}],yield_spec:flat(0,'rate'),cost_spec:flat(.01,'rate'),cost_line:'operating_expense'}]},
 other_assets_mode:'formula_level',other_assets_model:{opening_balance:2e6,base_spec:{source:'entered',trajectory:'growth',base:2e6,growth_spec:{rate:.05,period:'year'}},components:[
  {component_id:'rou',name:'ROU asset',terms:[{term_id:'t1',driver_spec:{source:'entered',trajectory:'explicit',cadence:'month',values:[1e6,2e6]},multiplier_spec:flat(1)}]},
  {component_id:'rec',name:'Receivable',terms:[{term_id:'t2',driver_spec:{source:'link',link:{kind:'bank_income_flow',series_id:'fees',aggregation:'sum'}},days_spec:flat(12),year_days:360,multiplier_spec:flat(1)}]}]},
 other_liabilities_mode:'formula_level',other_liabilities_model:{opening_balance:0,base_spec:flat(0),components:[
  {component_id:'settle',kind:'settlement',name:'Settlement',opening_balance:0,settlement:{period:'month',sign:1,weights:[1,.5],opening_history:[-5000],sources:[{series_id:'source',measure:'reported_fee_income'}]}},
  {component_id:'lc',name:'Accrued comp',terms:[{term_id:'t3',driver_spec:flat(1e6),multiplier_spec:flat(1)}]}]}}};
const ctx={cfg,window:{},console,esc:s=>String(s).replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/</g,'&lt;'),fmtComma:x=>String(x),_pf:x=>Number(String(x).replace(/,/g,'')),PLAB:()=> 'mo',PPY:()=>12,
 _numInput:x=>String(x),_nativeFlowPeriod:()=> 'month',_seriesPasteSummary:v=>v.length+' loaded',_faSeriesFmt:v=>String(v),_faSeriesExplicitIsOpen:p=>/other_assets_model\.components\.0/.test(p),
 _sparkHtml:()=> '<svg></svg>',_seriesCadenceOptions:()=>['month','quarter','year'],_seriesResolutionUseful:()=>true,_explicitPreviewHtml:()=> '<div class="explicit-preview"></div>',
 growthSpecInline:(p)=>`<input onchange="setGrowthField('${p}','rate',1,0)">`,sourceCatalogRows:[],_ibFeeQuantityOptions:()=>[],_feeCustomerCountOptions:()=>[],
 _seriesId:()=> 'id',_ensureLinkableSeriesIds(){},_faComponentDisplayName:(c)=>c.name,_FA_BASE_SID:'b',_FA_GROSS_SID:'g',_FA_ACCUM_SID:'a',_FA_NET_SID:'n',
 renderContent(){},refresh(){},appStatus(){},getPath(){},setPath(){}};
vm.createContext(ctx);
const slice=(a,b)=>html.slice(html.indexOf(a),html.indexOf(b));
vm.runInContext(slice('// ===== r340: form kit','\n// r289: named balances'),ctx);
vm.runInContext(slice('function _bcState(create)','// r289: summaries first'),ctx);
vm.runInContext(slice('function _olState(create)','function _oaState(create)'),ctx);
vm.runInContext(slice('function _oaState(create)','window.faAdd=function'),ctx);
const before=JSON.stringify(cfg);
const outs={bc:ctx._bcEditorHtmlFk(),oa:ctx._oaEditorHtmlFk(),ol:ctx._olEditorHtmlFk(cfg.assumptions,cfg.assumptions.other_liabilities_model,'formula_level')};
assert.equal(JSON.stringify(cfg),before,'rendering must not mutate the configuration');
for(const [k,out] of Object.entries(outs)){
 assert(!/undefined|NaN|\[object Object\]/.test(out),k+' leaks undefined/NaN');
 for(const m of out.matchAll(/on(?:change|click|input|toggle)="([^"]+)"/g))new vm.Script(m[1].replace(/&quot;/g,'"').replace(/&amp;/g,'&'));
 assert(out.includes('class="fk-card"')||out.includes('fk-card'),k+' renders component cards');
}
const {bc,oa,ol}=outs;
// Interest-bearing balances
assert(bc.includes('Interest-bearing balances')&&bc.includes('bc-editor'),'panel identity kept for the page layout');
['Accounting treatment','Interest measured on','First prior-end balance','Cap at available bank cash','Floor balance at zero','Income calculation','Income amount','Annual cost rate','Cost posts to','Risk weight','Shared assumptions','Customer accounts','Multiply by','Remaining bank cash'].forEach(t=>assert(bc.includes(t),'bc missing '+t));
assert(bc.includes(">Subtract</button>")&&/class="on"[^>]*>Subtract/.test(bc),'term sign shown as a segmented control with Subtract selected');
assert(bc.includes("Fed Funds (EFFR)")&&bc.includes('Spread'),'reference-rate yield shows index and spread');
assert(bc.includes('Earns on the cash left'),'remaining-cash component explains itself');
// Other assets
assert(oa.includes('<div class="nie-mode">'),'mode toggle stays a direct child for the page header');
['Opening balance','Base asset level','ROU asset','Receivable','Days outstanding','Days per year','Flow to balance','+ Add term','+ Add component','Remove component'].forEach(t=>assert(oa.includes(t),'oa missing '+t));
assert(oa.includes('fk-drawer')&&oa.includes('>Close</button>'),'an open schedule renders a drawer with a native Close');
// Other liabilities
['Opening liability','Source sign','Holding period','Eligible revenue','Services › Revenue','Weight held','Opening revenue','Prior month','+ Add earlier month','Liability level','+ Add liability component','+ Add settlement liability'].forEach(t=>assert(ol.includes(t),'ol missing '+t));
assert(ol.includes('value="-5"'),'opening revenue history shown in $000s');
assert(!ol.includes('fsx-band'),'no legacy band decoration markup');
console.log('PASS form-kit editors: handlers compile, no leaks, controls present, render is read-only');
