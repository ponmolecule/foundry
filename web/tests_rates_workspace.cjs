const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),cp=require('node:child_process');
const src=fs.readFileSync('web/rates_workspace.js','utf8'),html=fs.readFileSync('web/console_v2.html','utf8');
// Compile all inline scripts; external assets must have deployed routes.
for(const m of html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g))new vm.Script(m[1]);
const values={};let autosaves=0,runs=0,release=null;
const c=JSON.parse(cp.execFileSync('python3',['-c','import json;from foundry.v2.tests_rates_workspace import config;print(json.dumps(config()))'],{encoding:'utf8'}));
const ctx={cfg:c,console,Date,JSON,Number,Object,Math,Error,CURVE_ORDER:['effr','sofr','prime'],CURVE_LABEL:{effr:'EFFR',sofr:'SOFR',prime:'Prime'},CURVE_OFFSET_DEFAULT:{effr:0,sofr:.0005,prime:.03},HALF_BAND_DEFAULT:.00125,
 esc:x=>String(x??'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/"/g,'&quot;'),_isoUTC:d=>d.toISOString().slice(0,10),_openingModelStart:()=>new Date('2028-01-01T00:00:00Z'),
 document:{getElementById:id=>values[id]||null},scheduleAutosave:()=>autosaves++,renderGlobals:()=>{},refresh:()=>runs++,setTab:()=>{},cfgSelectModule:()=>{}};
ctx.fetch=async(url,opt)=>{
 if(url==='/api/curves/refresh')return {ok:true,json:async()=>({ok:true,snapshot:{current_policy:{mid:.035,top:.03625,observation_date:'2027-12-01'},fomc:{anchors:{'2028-12-31':.032},lr:.03},retrieved_at:'2026-10-16'}})};
 const input=JSON.parse(opt.body),r=cp.spawnSync('python3',['-c','import json,sys;from foundry.v2.rates_workspace import preview;print(json.dumps(preview(json.load(sys.stdin)["config"])))'],{input:JSON.stringify(input),encoding:'utf8'});
 return {ok:r.status===0,json:async()=>r.status===0?JSON.parse(r.stdout):{detail:r.stderr}};
};vm.createContext(ctx);vm.runInContext(src,ctx);
const go=s=>vm.runInContext(s,ctx);
(async()=>{
 const original=JSON.stringify(c);let rendered=go('ratesWorkspaceHtml()');assert.equal(JSON.stringify(c),original);assert(rendered.includes('Published Fed projections'));assert(rendered.includes('Saved curve · preserve'));
 assert.throws(()=>go("rwsParse('3.4','auto','2028-01-01','monthly','effr')"),/Choose/);
 assert.equal(go("rwsParse('3.4 3.1','percent','2028-01-01','annual','effr')[1].date"),'2029-01-01');
 assert.equal(go("rwsParse('Date EFFR SOFR Prime\\n2028-01-01 3.4 3.5 6.5','percent','','monthly','sofr')[0].rate"),.035);
 assert.equal(go("rwsParse('0.034','decimal','2028-01-01','monthly','effr')[0].rate"),.034);
 for(const [str,re] of [['2028-02-31 3.4',/Invalid date/],['2028-01-01 3.4\n2028-01-01 3.1',/unique/],['x',/number/]])assert.throws(()=>ctx.rwsParse(str,'percent','2028-01-01','monthly','effr'),re);
 go("rwsDraft.indices.effr={source:'schedule',schedule:{points:[{date:'2028-01-01',rate:.034},{date:'2029-01-01',rate:.031}],label:'Synthetic evidence',units:'percent',interpolation:'step',extension:'hold'}}");
 await ctx.rwsPreview();assert.equal(go('rwsResult.monthly[12].effr.rate'),.031);assert.equal(JSON.stringify(c),original,'preview must be isolated');
 ctx.rwsApply();assert.equal(autosaves,1);assert.equal(runs,1);const saved=JSON.stringify(c);
 go("rwsDraft.anchor_overrides['2028-12-31']=.04");ctx.rwsApply();assert.equal(JSON.stringify(c),saved,'stale preview cannot apply');
 ctx.rwsCancel();assert.equal(go("rwsDraft.anchor_overrides['2028-12-31']"),undefined);
 await ctx.rwsFetch();assert.equal(JSON.stringify(c),saved,'refresh must remain staged');assert.equal(go('rwsDraft.indices.effr.schedule.points[0].rate'),.034,'refresh erased schedule');
 await ctx.rwsPreview();ctx.rwsApply();assert.equal(go('cfg.assumptions.rates_workspace.published.fomc.anchors["2028-12-31"]'),.032);
 // A pending response cannot cross engagements, nor overwrite a changed draft.
 ctx.fetch=()=>new Promise(r=>release=r);const pending=ctx.rwsPreview();ctx.cfg=JSON.parse(original);release({ok:true,json:async()=>({monthly:[],native:[]})});await pending;assert.equal(JSON.stringify(ctx.cfg),original);
 const app=fs.readFileSync('app.py','utf8');assert(app.includes('async def rates_preview(request: Request, _=Depends(gate))'));for(const asset of ['rates_workspace.js','rates_workspace.css'])assert(app.includes('@app.get("/web/'+asset+'")'));
 assert(html.includes("_CFG_MODS=['rates'"));assert(html.includes('id="rwsWorkspace"'));
 console.log('Rates UI: isolated preview/apply, stale responses, refresh preservation, units, paste parsing and deployed assets pass.');
})().catch(e=>{console.error(e);process.exitCode=1});
