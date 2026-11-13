// Exercise the actual preview orchestration without a browser/network dependency.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const html=fs.readFileSync('web/console_v2.html','utf8');
const helpers=html.slice(html.indexOf('const _previewSession ='),html.indexOf('async function _previewInner('));
const orchestration=html.slice(html.indexOf('async function _previewInner('),html.indexOf('function productValidationHtml('));
const nodes={status:{textContent:''}};
let mode='ok',submitted=[];
const ctx={console,AbortController,DOMException,setTimeout,clearTimeout,Date,Math,JSON,globalThis:null,
 cfg:{assumptions:{v:1}},seq:0,lastRes:null,lastErrs:null,lastRunFailure:null,_calculatedInputs:null,
 _calculationState:'unknown',V31:true,V3:true,currentTab:'config',ST:{view:'scenarios'},
 normalizeCfg:()=>{},syncModules:()=>{},loadSourceCatalog:async()=>{},updateCalculationStatus:()=>{},
 _cacRunInputs:new WeakMap(),paintChrome:()=>{},refreshConfigPreviews:()=>{},renderContent:()=>{},
 document:{getElementById:id=>nodes[id]||null},
 fetch:async(url,opt)=>{
   if(url.endsWith('/jobs')){
     const p=JSON.parse(opt.body);submitted.push(p);
     if(mode==='network')throw Error('network unavailable');
     if(mode==='validation')return {ok:true,json:async()=>({status:'failed',http_status:422,errors:[{message:'Schedule incomplete'}]})};
     return {ok:true,json:async()=>({status:'completed',result:{financials:{v:p.config.assumptions.v},scope:p.scope,flags:[]}})};
   }
   throw Error('unexpected '+url);
 }};ctx.globalThis=ctx;vm.createContext(ctx);vm.runInContext(helpers+orchestration,ctx);
(async()=>{
 await ctx._previewInner();assert.equal(ctx.lastRes.financials.v,1);assert.equal(submitted[0].scope,'base');
 const previous=ctx.lastRes;ctx.cfg.assumptions.v=2;mode='network';
 await ctx._previewInner();assert.strictEqual(ctx.lastRes,previous);assert.equal(ctx._calculationState,'failed');assert.match(ctx.lastRunFailure.message,/network/);
 mode='validation';await ctx._previewInner();assert.strictEqual(ctx.lastRes,previous);assert.equal(ctx.lastErrs[0].message,'Schedule incomplete');
 mode='ok';await ctx._previewInner();assert.equal(ctx.lastRes.financials.v,2);assert.equal(ctx.lastErrs,null);assert.equal(ctx._calculationState,'complete');
 await ctx._previewInner('full');assert.equal(submitted.at(-1).scope,'full');
 ctx.currentTab='stress';ctx.ST.view='templates';await ctx._previewInner();assert.equal(submitted.at(-1).scope,'full');
 // A job may still be running after 60 seconds; polling must continue to completion.
 let polls=0;
 const oldFetch=ctx.fetch;
 ctx.fetch=async(url,opt)=>({ok:true,json:async()=>url.endsWith('/jobs')?{job_id:'slow',status:'running',elapsed_seconds:75}:{status:'completed',result:{financials:{slow:true}}}});
 const slow=await vm.runInContext("_previewJob(JSON.stringify(cfg),'base',new AbortController().signal,()=>{})",ctx);
 assert.equal(slow.financials.slow,true);ctx.fetch=oldFetch;
 // A late response cannot overwrite a newer edit's result.
 let release;ctx.currentTab='config';ctx.cfg.assumptions.v=3;
 const savedFetch=ctx.fetch;ctx.fetch=async()=>new Promise(resolve=>{release=()=>resolve({ok:true,json:async()=>({status:'completed',result:{financials:{v:3}}})});});
 const old=ctx._previewInner();await Promise.resolve();ctx.cfg.assumptions.v=4;ctx.fetch=savedFetch;
 await ctx._previewInner();release();await old;assert.equal(ctx.lastRes.financials.v,4);
 // Switching engagement clears lastRes elsewhere; failure must not restore the former bank.
 ctx.lastRes=null;mode='network';await ctx._previewInner();assert.equal(ctx.lastRes,null);
 assert(html.includes("snapRes=await _previewJob(cfgText,'full'"));
 // The persistent notice distinguishes stale/failed figures and offers retry.
 nodes.content={before:n=>{nodes[n.id]=n;}};
 ctx.document.createElement=()=>({style:{},children:[],setAttribute(){},appendChild(n){this.children.push(n);}});
 vm.runInContext(html.slice(html.indexOf('function updateCalculationNotice(){'),html.indexOf('function updateCalculationStatus(){')),ctx);
 ctx.preview=()=>{};ctx.lastRes={financials:{v:4}};ctx._calculationState='failed';
 ctx.updateCalculationNotice();assert.match(nodes['calculation-notice'].textContent,/previous results/);assert.equal(nodes['calculation-notice'].children.at(-1).textContent,'Retry update');
 ctx._calculationState='complete';ctx._calculatedInputs=JSON.stringify(ctx.cfg);ctx.updateCalculationNotice();assert.equal(nodes['calculation-notice'].hidden,true);
 console.log('PASS actual preview orchestration: base/full routing, failure retention, validation, recovery, late response isolation, cross-engagement isolation, full audit snapshot');
})().catch(e=>{console.error(e);process.exitCode=1;});
