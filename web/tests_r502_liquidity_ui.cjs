// r502: Stress Testing > Liquidity. Rail item under Understand; Results (what applies, stress day with chart, 30-day run,
// line draw), Setup (books, resources ladder, line, stress day, LCR), LCR detail; runs post the settings and store a record.
const {chromium}=require('playwright'),fs=require('fs'),assert=require('assert'),cp=require('child_process');
const PY=`
import json
from foundry.v2 import stress, liquidity as LQ
from foundry.v2.tests_r502_liquidity import trust_bank, base_of
from foundry.v2.stress_report import deposit_classification
c = trust_bank()
res = stress._engine_run(base_of(c))
out = LQ.run(c, res)
rec = LQ.record(c, out); rec["state"] = "current"
setup = dict(template=LQ.template(c), deposit_products=[dict(key=d["key"], name=d["name"]) for d in deposit_classification(c)],
             charter_type=LQ.charter_type(c), errors=[], applicability=LQ.applicability(c),
             lcr_categories={k: dict(rate=v[0], label=v[1]) for k, v in LQ.LCR_RULE.items()})
print(json.dumps(dict(cfg=c, res=res, out=out, rec=rec, setup=setup), default=str))
`;
(async()=>{
const F=JSON.parse(cp.execFileSync('python3',['-c',PY],{encoding:'utf8',maxBuffer:1<<28}));
const html=fs.readFileSync('web/console_v2.html','utf8').replace('<head>','<head><script>window.V31=true;window.V3=true;</script>').replace(/renderTabs\(\);\nwhoami\(\)\.then[^\n]+/,'');
const browser=await chromium.launch({executablePath:process.env.FOUNDRY_CHROMIUM_PATH,args:['--no-sandbox','--disable-gpu','--single-process','--no-zygote'],headless:true});
try{const page=await browser.newPage({viewport:{width:1400,height:1000}}),errors=[],posts={};page.on('pageerror',e=>errors.push(e.message));
await page.route('**/*',r=>{const u=r.request().url(),k=u.split('/api/v31/stress/')[1];if(k)(posts[k]=posts[k]||[]).push(JSON.parse(r.request().postData()||'{}'));
 if(k==='targets')return r.fulfill({json:{targets:[]}});
 if(k==='runs')return r.fulfill({json:{records:[F.rec]}});
 if(k==='liquidity/setup')return r.fulfill({json:F.setup});
 if(k==='liquidity'){const b=JSON.parse(r.request().postData());return r.fulfill({json:b.store?{result:F.out,stored:true,record:Object.assign({},F.rec,{run_id:'new1',liquidity_version:b.cfg.liquidity_stress.version})}:{result:F.out,stored:false}});}
 return r.fulfill({json:{}});});
await page.goto('http://foundry.test');await page.setContent(html);
await page.evaluate(d=>{cfg=d.cfg;lastRes=d.res;lastErrs=null;lastRunFailure=null;cfg.scenario_name='r502 test';refresh=()=>{};scheduleAutosave=()=>{};_govSlug=()=>'eng';setTab('stress');},{cfg:F.cfg,res:F.res});
await page.waitForFunction(()=>ST.records.length===1);
const txt=()=>page.evaluate(()=>document.getElementById('content').innerText);
let t=await txt();
assert(/3 · Understand/i.test(t)&&/Liquidity/.test(t)&&/Pay out today, through a run, LCR/.test(t),'rail shows Liquidity under Understand');
// Results from the stored record
await page.evaluate(()=>stView('liquidity'));await page.waitForFunction(()=>LQ.meta&&LQ.meta.template);
t=await txt();
for(const s of ['What can leave, how fast','What applies to this engagement','Intraday redemption capacity','30-day survival','Stablecoin reserve adequacy','Not applicable','Management measure','Stress day · '+F.out.month_label,'Lowest intraday cushion','day run','Survives the run','line is drawn','Repaid after 30 days','Due within 30 days','Run liquidity stress'])
  assert(t.includes(s),'results shows '+s);
assert(await page.evaluate(()=>document.querySelectorAll('svg.st-chart').length)===2,'stress-day chart and 30-day chart drawn');
const segs=await page.evaluate(()=>[...document.querySelectorAll('.st-seg button')].map(b=>b.innerText));
assert.deepStrictEqual(segs,['Results','Setup','LCR detail']);
// Setup
await page.evaluate(()=>lqTab('setup'));t=await txt();
for(const s of ['What can leave','Client custody cash','Fund share settlement','Stablecoin','Not in this engagement','Add stablecoin book','What the bank can use, and when','Contingency line','Which day to stress','Lowest cash month','LCR','Show the LCR as a management measure','Calibration'])
  assert(t.includes(s),'setup shows '+s);
assert(await page.evaluate(()=>[...document.querySelectorAll('.lq-res input.st-txt')].map(x=>x.value).includes('Fed account cash')),'resources listed by name');
const deps=await page.evaluate(()=>[...document.querySelectorAll('.lq-deps input')].filter(x=>x.checked).length);
assert(deps===2,'custody book shows its two deposit products ticked');
// edits change the settings, bump the version and mark the result stale
const v0=await page.evaluate(()=>cfg.liquidity_stress.version);
await page.evaluate(()=>lqSet('books.0.severities.severe.day1','30','pct'));
assert(await page.evaluate(()=>cfg.liquidity_stress.books[0].severities.severe.day1)===0.3,'percent input stored as a fraction');
assert(await page.evaluate(()=>cfg.liquidity_stress.version)===v0+1,'edits bump the settings version');
assert(await page.evaluate(()=>_stState(ST.records[0]))==='stale','the stored liquidity record goes stale after an edit');
await page.evaluate(()=>lqAddBook('stablecoin'));
assert(await page.evaluate(()=>cfg.liquidity_stress.books.some(b=>b.type==='stablecoin'&&Array.isArray(b.reserves))),'stablecoin book added prospectively');
await page.evaluate(()=>lqDep(0,0,true));
assert(await page.evaluate(()=>cfg.liquidity_stress.books[0].balance.deposit_keys.length)===3,'deposit product ticked by index');
// base excludes liquidity settings
assert(await page.evaluate(()=>!('liquidity_stress' in _stBase())),'base sent to the engine excludes liquidity settings');
// run posts settings and stores
await page.evaluate(()=>lqRun());await page.waitForFunction(()=>!LQ.busy&&LQ.res);
const lp=posts.liquidity.slice(-1)[0];
assert(lp.store===true&&lp.slug==='eng'&&lp.run_id===null&&lp.cfg.liquidity_stress.books.length===3&&!lp.cfg.stress_scenarios,'run request '+JSON.stringify(Object.keys(lp)));
assert(await page.evaluate(()=>ST.records[0].run_id==='new1'&&_stState(ST.records[0])==='current'),'new record current');
// LCR detail
await page.evaluate(()=>lqTab('lcr'));t=await txt();
for(const s of ['Management measure.','HQLA','Outflows, 30 days','Inflows, capped at 75%','Liquid assets that count','Not HQLA','What leaves in 30 days','Custody cash, operational','Rule','Engagement'])
  assert(t.includes(s),'LCR shows '+s);
assert(t.includes((F.out.lcr.before.lcr*100).toFixed(0)+'%'),'LCR value shown');
// Runs: liquidity type
await page.evaluate(()=>stView('runs'));t=await txt();
assert(/Liquidity/.test(t)&&/Open in Liquidity/.test(t),'runs label liquidity records');
// empty state when nothing set up
await page.evaluate(()=>{delete cfg.liquidity_stress;LQ.res=null;ST.records=[];stView('liquidity');lqTab('results');});await page.waitForTimeout(100);t=await txt();
assert(/Start from a draft/.test(t),'empty state offers a draft');
await page.evaluate(()=>lqStart());
assert(await page.evaluate(()=>cfg.liquidity_stress&&cfg.liquidity_stress.books[0].calibration.status==='draft'&&LQ.tab==='setup'),'draft template applied, Setup opens');
if(process.env.SHOT){await page.evaluate(()=>{LQ.res=null;});}
assert.deepStrictEqual(errors,[]);
console.log('PASS r502 liquidity UI: rail item, Results with what applies, stress-day and 30-day charts, line draw; Setup books, ladder, line, stress day, LCR; edits stale the record; run stores; LCR detail; runs labelled; empty state');
}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
