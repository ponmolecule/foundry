// r499: stress tab shell (purpose-labelled rail), Runs, Reporting (primary case, capital tiers, Tables X and Y,
// classification), Executive Summary block. Endpoints are mocked with records and reports the engine produced.
const {chromium}=require('playwright'),fs=require('fs'),assert=require('assert'),cp=require('child_process');
const PY=`
import copy, json
from foundry.v2 import stress, stress_report as R
from foundry.v2.tests_r498_stress import BANK, key_for
c = copy.deepcopy(BANK)
k1 = key_for(c, lambda r: r["product_name"] == "Commercial Real Estate" and r["field"] == "charge_off_ann")
s1 = dict(id="s1", name="CRE losses", kind="economic", version=1, funding="inherit",
          severities=[dict(id="severe", label="Severe", overrides=[dict(target=k1, op="multiply", value=3, start=1, end=None)])])
c["stress_scenarios"] = [s1]
rec = stress.run_scenario(c, s1, keep_results=True)[0]
res = rec.pop("_results")
rep = R.report(res["base_cfg"], res["base_res"], res["stress_cfg"], res["stress_res"], settings_cfg=c)
rec["archive"] = {"baseline": "b", "base_result": "r", "stress_cfg": "s", "stress_result": "t"}
rec["state"] = "current"
base = {k: v for k, v in c.items() if k not in R.STRESS_KEYS}
print(json.dumps(dict(cfg=c, targets=stress.targets(base), rec=rec, rep=rep, res=stress._engine_run(base)), default=str))
`;
(async()=>{
const F=JSON.parse(cp.execFileSync('python3',['-c',PY],{encoding:'utf8',maxBuffer:1<<28}));
const html=fs.readFileSync('web/console_v2.html','utf8').replace('<head>','<head><script>window.V31=true;window.V3=true;</script>').replace(/renderTabs\(\);\nwhoami\(\)\.then[^\n]+/,'');
const browser=await chromium.launch({executablePath:process.env.FOUNDRY_CHROMIUM_PATH,args:['--no-sandbox','--disable-gpu','--single-process','--no-zygote'],headless:true});
try{const page=await browser.newPage({viewport:{width:1400,height:1000}}),errors=[],posts={};page.on('pageerror',e=>errors.push(e.message));
await page.route('**/*',r=>{const u=r.request().url(),k=u.split('/api/v31/stress/')[1];
 if(k){(posts[k]=posts[k]||[]).push(JSON.parse(r.request().postData()||'{}'));}
 if(k==='targets')return r.fulfill({json:{targets:F.targets}});
 if(k==='runs')return r.fulfill({json:{records:[F.rec]}});
 if(k==='report')return r.fulfill({json:{report:F.rep,state:'current'}});
 if(k==='probe')return r.fulfill({json:{ok:true,mode:'level'}});
 if(k==='export')return r.fulfill({status:200,contentType:'application/octet-stream',body:'x'});
 return r.fulfill({json:{}});});
await page.goto('http://foundry.test');await page.setContent(html);
await page.evaluate(d=>{cfg=d.cfg;lastRes=d.res;lastErrs=null;lastRunFailure=null;cfg.scenario_name='Stress UI test';refresh=()=>{};scheduleAutosave=()=>{};setTab('stress');},{cfg:F.cfg,res:F.res});
await page.waitForFunction(()=>ST.records.length===1&&ST.targets&&ST.targets.length>0);
const q=s=>page.evaluate(s=>[...document.querySelectorAll(s)].map(x=>x.innerText.replace(/\s+/g,' ').trim()),s);
// rail: four steps, purpose lines, current view marked
const rail=await q('.st-rail .st-ri');
assert.deepStrictEqual(rail.map(x=>x.split(' ')[0]),['Scenarios','Builder','Runs','Results','Reporting']);
assert(rail[2].includes('Every run you have made')&&rail[4].includes('Primary case'),'each place says what it is for');
assert.deepStrictEqual(await q('.st-rs'),['1 · MAKE A CHANGE','2 · RUN','3 · UNDERSTAND','4 · SUBMIT'].map(x=>x),'step labels');
assert.strictEqual((await q('.st-ri[aria-current="page"]')).length,1);
assert.strictEqual(await page.evaluate(()=>!!document.querySelector('.pg-band-new')),false,'no duplicate dark page band');
// Runs: grouped, actions per row, details on demand
await page.evaluate(()=>stView('runs'));
let t=await page.evaluate(()=>document.getElementById('content').innerText);
assert(/Current/.test(t)&&/CRE losses · Severe/.test(t)&&/Open in Results/.test(t)&&/Make primary/.test(t),'run row with its actions');
assert(!/run [0-9a-f]{12} · base/.test(t),'record details stay closed until asked');
// make primary -> Reporting
await page.evaluate(id=>{stSetPrimary(id);stView('reporting');},F.rec.run_id);
await page.waitForFunction(()=>document.querySelectorAll('.st-tile').length===4);
assert.strictEqual(await page.evaluate(()=>cfg.stress_reporting.primary_run_id),F.rec.run_id,'primary saved with the engagement');
const tiles=await page.evaluate(()=>[...document.querySelectorAll('.st-tile')].map(x=>({t:x.querySelector('.st-tt').innerText,tiers:[...x.querySelectorAll('.st-tier')].map(y=>y.innerText.replace(/\s+/g,' '))})));
assert(tiles.every(x=>x.tiers.length===3),'each ratio shows regulatory, commitment and policy tiers');
assert(/Commitment 9.0%/.test(tiles[0].tiers[1])&&/Bank policy not set/.test(tiles[0].tiers[2]),'commitment shown; policy blank until entered '+JSON.stringify(tiles[0]));
const lev=F.rep.capital.stress.ratios.leverage;
assert(tiles[0].t.startsWith('Tier 1 leverage')&&(await q('.st-tile .st-big'))[0].startsWith(lev.min.toFixed(2)+'%'),'lowest leverage matches the report');
// Table X
const rows=await page.evaluate(()=>[...document.querySelectorAll('.st-annual tbody tr')].map(r=>[...r.cells].map(c=>c.innerText.trim())));
const X=F.rep.X.filter(r=>r.kind!=='group'),ta=X.find(r=>r.key==='total_assets');
const taRow=rows.find(r=>r[0]==='Total Assets');const num=s=>{s=String(s).replace(/[,$%]/g,'');return s.startsWith('(')?-parseFloat(s.slice(1)):parseFloat(s);};
assert(Math.abs(num(taRow[3])-ta.stress[2])<=1&&Math.abs(num(taRow[7])-ta.delta[2])<=1,'Total Assets Year 3 stressed value and change match the report '+JSON.stringify(taRow));
assert(rows.find(r=>r[0]==='Noninterest-Bearing Deposits')[1]==='not separately available','unclassified deposit split says so instead of a number');
assert(/Classify 6 products/.test(await page.evaluate(()=>document.getElementById('content').innerText)),'callout offers the classification');
// classify deposits (explicit), policy minimum, window
const before=(posts.report||[]).length;
await page.evaluate(()=>{_stDepList().forEach(d=>stDepClass(d.key,d.name==='Retail Demand'?'nib':'ib'));stPolicy('leverage','value','10');stPolicy('leverage','source','Board capital policy 2026');});
await page.waitForTimeout(300);
const sr=await page.evaluate(()=>cfg.stress_reporting);
assert(Object.values(sr.deposit_classes).filter(v=>v==='nib').length===1&&Object.keys(sr.deposit_classes).length===6,'classes saved per product');
assert(sr.policy_minimums.leverage.value===10&&sr.policy_minimums.leverage.source==='Board capital policy 2026','policy minimum with its source');
assert((posts.report||[]).length>before&&posts.report.slice(-1)[0].cfg.stress_reporting.policy_minimums.leverage.value===10,'report reloads with the new settings, from the archive');
assert(!('stress_reporting' in await page.evaluate(()=>_stBase())),'reporting settings are never part of the base');
// Table Y
await page.evaluate(()=>stStab('Y'));
const yRows=await page.evaluate(()=>[...document.querySelectorAll('.st-annual tbody tr')].map(r=>r.cells[0].innerText.trim()));
assert(['Net Interest Income','Pre-Tax Net Income','Net Income','ROAA','ROAE','Efficiency Ratio'].every(x=>yRows.includes(x)),'Table Y rows');
// export submission tables
await page.evaluate(()=>stExport(true));await page.waitForTimeout(200);
assert.strictEqual(posts.export.slice(-1)[0].report_run_id,F.rec.run_id,'submission export names the primary run');
// Executive Summary block
const es=await page.evaluate(()=>stressExecBlockHtml());
assert(/Stress testing/.test(es)&&/(stays above every threshold|falls below)/.test(es)&&(es.match(/<tr>/g)||[]).length>=4,'Executive Summary block with verdict and four ratios');
// stale primary: an edit to the scenario
await page.evaluate(()=>{stOpen('s1');ST.row=0;stRowSet('value',4);stView('reporting');});
t=await page.evaluate(()=>document.getElementById('content').innerText);
assert(/The primary case is stale/.test(t),'stale primary is flagged, not replaced');
assert.strictEqual(await page.evaluate(()=>cfg.stress_reporting.primary_run_id),F.rec.run_id,'primary is not switched automatically');
assert(/Stale/.test(await page.evaluate(()=>stressExecBlockHtml())),'Executive Summary says the primary case is stale');
assert.deepStrictEqual(errors,[]);
console.log('PASS r499 stress reporting UI: rail with purposes, Runs actions, primary case, three capital tiers, Tables X and Y match the report, explicit deposit classes, policy source, submission export, Executive Summary block, stale primary flagged');
}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
