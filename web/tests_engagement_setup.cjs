const assert=require('node:assert/strict'),fs=require('fs'),vm=require('vm');
const html=fs.readFileSync(__dirname+'/console_v2.html','utf8');
const source=html.slice(html.indexOf('// r318: visible setup;'),html.indexOf('function renderConfigTab(){'));
let responses=[],pending=null,renders=0,refreshes=0,saves=0;
const cfg={proposed_bank:'Example',assumptions:{periods_per_year:12,n_periods:36},charter_profile:{charter_type:'state_nonmember',regulator:'FDIC + state supervisor',state:'Texas',target_opening:'2028-01-01',cblr_election:true},target_state:{initial_capital:30000000},pre_opening:{expenses:[{amount:1000}]}};
const ctx={cfg,window:{},esc:s=>String(s).replace(/[&<>"']/g,x=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[x])),fmtComma:x=>x.toLocaleString('en-US'),REGULATOR_OF:{state_nonmember:'FDIC + state supervisor'},US_STATES:['Texas','New York'],renderContent(){renders++},renderGlobals(){},syncNameChrome(){},refresh(){refreshes++},scheduleAutosave(){saves++},appStatus(){},lastRes:{old:true},lastRunFailure:{old:true},lastErrs:['old'],fetch:async()=>pending?await pending:responses.shift()};
vm.createContext(ctx);vm.runInContext(source,ctx);
function response(body,ok=true){return {ok,json:async()=>body};}
function policy(early=true){return {early,structural_reason:'Deposit inputs protect cadence',extend_reason:'',values:{...ctx.engagementSetupValues()}};}
(async()=>{
 const summary=ctx.engagementSetupHtml();for(const text of ['Charter','Monthly','3 years · 36 months','2028-01-01','FDIC','30,000','CBLR','Texas','Edit setup'])assert(summary.includes(text));
 assert(html.includes('let h = engagementSetupHtml()'));assert(html.includes('.eset-summary{display:grid'));assert(html.includes('width:176px'));assert(html.includes('grid-template-columns:repeat(2,minmax(0,1fr))'));
 // Execute the exact fixed-asset rendering expression: merely viewing it must be read-only.
 const read=html.match(/const _fa=A\.fixed_assets\|\|\{mode:"simple",assets:\[\]\}/);assert(read);
 const a={};vm.runInNewContext(read[0]+'; _fa.assets||[];', {A:a});assert.deepEqual(a,{});
 const original=JSON.stringify(ctx.cfg);responses=[response(policy())];await ctx.engagementSetupOpen();ctx.engagementSetupDraft('years',5);assert.equal(JSON.stringify(ctx.cfg),original);assert(ctx.engagementSetupHtml().includes('5 years × 12 periods/year = 60'));
 ctx.engagementSetupCancel();assert.equal(JSON.stringify(ctx.cfg),original);
 responses=[response(policy())];await ctx.engagementSetupOpen();ctx.engagementSetupDraft('years',5);responses=[response({error:'Missing source data'},false)];await ctx.engagementSetupApply();assert.equal(JSON.stringify(ctx.cfg),original);assert(ctx.engagementSetupHtml().includes('Missing source data'));assert.equal(refreshes,0);
 const next=JSON.parse(original);next.assumptions.n_periods=60;responses=[response({cfg:next})];await ctx.engagementSetupApply();assert.equal(ctx.cfg.assumptions.n_periods,60);assert.equal(ctx.cfg.pre_opening.expenses[0].amount,1000);assert.equal(ctx.lastRes,null);assert.equal(ctx.lastErrs,null);assert.equal(refreshes,1);assert.equal(saves,1);assert.equal(ctx.lastRunFailure,null);
 ctx.lastRes={fresh:true};responses=[response(policy())];await ctx.engagementSetupOpen();responses=[response({cfg:ctx.cfg})];await ctx.engagementSetupApply();assert(ctx.lastRes.fresh);assert.equal(refreshes,1);assert.equal(saves,1);
 responses=[response(policy(false))];await ctx.engagementSetupOpen();const locked=ctx.engagementSetupHtml();assert(locked.includes('Charter type<select disabled'));assert(locked.includes('Cadence<select disabled'));assert(locked.includes('Deposit inputs protect cadence'));assert(locked.includes('Extending the horizon remains available'));assert(locked.includes('3 years</option>'));
 // A response must never overwrite data entered while validation was in flight.
 let release;pending=new Promise(resolve=>release=resolve);const run=ctx.engagementSetupApply();ctx.cfg.pre_opening.expenses.push({amount:2000});release(response({cfg:next}));await run;pending=null;assert.equal(ctx.cfg.pre_opening.expenses.length,2);assert(ctx.engagementSetupHtml().includes('Inputs changed while setup'));assert.equal(refreshes,1);
 ctx.engagementSetupCancel();ctx.window.SNAPSHOT=true;assert(ctx.engagementSetupHtml().includes('disabled'));await ctx.engagementSetupOpen();assert.equal(JSON.stringify(ctx.cfg.pre_opening.expenses),'[{"amount":1000},{"amount":2000}]');
 for(const m of summary.matchAll(/onclick="([^"]+)"/g))new vm.Script(m[1]);
 assert(html.includes("action:'initialize'"));assert(html.includes('_engSetup=null;\n  _stripTransientPasteFlags(c);'));
 console.log('PASS setup summary, compact controls, draft/cancel/apply, backend rejection, lock reasons, horizon extension, stale-response protection, snapshot read-only and baseline creation');
})().catch(e=>{console.error(e);process.exitCode=1});
