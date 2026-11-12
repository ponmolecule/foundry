// r498: stress workbench. Scenarios list, builder, results (comparison, attribution waterfall, series chart), run record.
// Endpoints are mocked with records the engine actually produced, so the page shows real numbers without a server.
const {chromium}=require('playwright'),fs=require('fs'),assert=require('assert'),cp=require('child_process');
const PY=`
import copy, json
from foundry.v2 import stress
from foundry.v2.tests_r498_stress import BANK, key_for
c = copy.deepcopy(BANK)
k1 = key_for(c, lambda r: r["product_name"] == "Commercial Real Estate" and r["field"] == "charge_off_ann")
s1 = dict(id="s1", name="CRE losses", kind="economic", version=1, funding="inherit",
          severities=[dict(id="moderate", label="Moderate", overrides=[dict(target=k1, op="multiply", value=2, start=1, end=None)])])
s2 = dict(id="s2", name="Broken", kind="economic", version=1, funding="inherit",
          severities=[dict(id="moderate", label="Moderate", overrides=[dict(target="lending_products:nope:charge_off_ann", op="multiply", value=2, start=1, end=None)])])
c["stress_scenarios"] = [s1, s2]
ok = stress.run_scenario(c, s1)[0]
bad = stress.run_scenario(c, s2)[0]
base = {k: v for k, v in c.items() if k != "stress_scenarios"}
print(json.dumps(dict(cfg=c, targets=stress.targets(base), ok=ok, bad=bad, res=stress._engine_run(base)), default=str))
`;
(async()=>{
const F=JSON.parse(cp.execFileSync('python3',['-c',PY],{encoding:'utf8',maxBuffer:1<<28}));
assert.strictEqual(F.ok.status,'completed');assert.strictEqual(F.bad.status,'failed');
const html=fs.readFileSync('web/console_v2.html','utf8').replace('<head>','<head><script>window.V31=true;window.V3=true;</script>').replace(/renderTabs\(\);\nwhoami\(\)\.then[^\n]+/,'');
const browser=await chromium.launch({executablePath:process.env.FOUNDRY_CHROMIUM_PATH,args:['--no-sandbox','--disable-gpu','--single-process','--no-zygote'],headless:true});
try{const page=await browser.newPage({viewport:{width:1400,height:1000}}),errors=[],posts=[];page.on('pageerror',e=>errors.push(e.message));
await page.route('**/*',r=>{const u=r.request().url();
 if(u.endsWith('/api/v31/stress/targets'))return r.fulfill({json:{targets:F.targets}});
 if(u.endsWith('/api/v31/stress/runs'))return r.fulfill({json:{records:[]}});
 if(u.endsWith('/api/v31/stress/probe'))return r.fulfill({json:{ok:true,mode:'level',reason:''}});
 if(u.endsWith('/api/v31/stress/run')){posts.push(JSON.parse(r.request().postData()));return r.fulfill({json:{records:[F.ok,F.bad],stored:true}});}
 return r.fulfill({json:{}});});
await page.goto('http://foundry.test');await page.setContent(html);
await page.evaluate(c=>{cfg=c.cfg;lastRes=c.res;lastErrs=null;lastRunFailure=null;cfg.scenario_name='Stress UI test';refresh=()=>{};scheduleAutosave=()=>{};setTab('stress');},{cfg:F.cfg,res:F.res});
await page.waitForFunction(()=>ST.targets&&ST.targets.length>0);
const txt=()=>page.evaluate(()=>document.getElementById('content').innerText);
// scenarios view
let t=await txt();assert(t.includes('CRE losses')&&t.includes('Broken'),'scenarios listed');
// builder: override row is labelled by product and input, never by raw key
await page.evaluate(()=>stOpen('s1'));t=await txt();
assert(t.includes('Commercial Real Estate'),'builder shows the product name');assert(!/lending_products:sid-/.test(t),'raw target key not shown as the label');
// run both
await page.evaluate(()=>{ST.checked={s1:true,s2:true};return stRunSelected();});
await page.waitForFunction(()=>ST.view==='results'&&!ST.running);
assert.deepStrictEqual(posts[0].runs.map(x=>x.scenario_id).sort(),['s1','s2']);
assert(posts[0].cfg.stress_scenarios.length===2,'scenarios sent with the run request');
const res=await page.evaluate(()=>{const c=document.getElementById('content');const th=[...c.querySelectorAll('.st-cmp thead th')].map(x=>x.innerText.replace(/\s+/g,' '));
 return {th,alert:[...c.querySelectorAll('.st-failed[role=alert]')].map(x=>x.innerText),
  wf:[...c.querySelectorAll('.st-wf:not(.st-wftot) .st-wfv')].map(x=>x.innerText),tot:(c.querySelector('.st-wftot .st-wfv')||{}).innerText,
  svg:c.querySelectorAll('svg.st-chart polyline').length,serCols:c.querySelectorAll('.st-ser thead th').length,
  cum:[...c.querySelectorAll('.st-cmp tbody tr')].map(r=>[...r.cells].map(x=>x.innerText)).find(r=>/^Cumulative net income/.test(r[0]))};});
assert(res.th.some(x=>x.includes('CRE losses')),'completed run is a column');assert(!res.th.some(x=>x.includes('Broken')),'failed run is not a column');
assert(res.alert.length===1&&res.alert[0].includes('Broken')&&res.alert[0].includes('failed'),'failed run shown as an alert '+JSON.stringify(res.alert));
const num=s=>{s=String(s).replace(/,/g,'');return s.startsWith('(')?-parseFloat(s.slice(1)):parseFloat(s);};
const a=F.ok.attribution;assert(Math.abs(num(res.tot)-a.total)<=1,'waterfall total matches the record');
assert(Math.abs(res.wf.map(num).reduce((x,y)=>x+y,0)-a.total)<=res.wf.length,'waterfall parts reconcile to the total');
const n=F.ok.base.series.ni.length,bm=F.ok.base.series.ni.reduce((x,y)=>x+y,0),sm=F.ok.stress.series.ni.reduce((x,y)=>x+y,0);
assert(Math.abs(num(res.cum[1])-bm)<=1&&Math.abs(num(res.cum[2])-sm)<=1&&Math.abs(num(res.cum[3])-(sm-bm))<=1,'cumulative NI row: base, stress, delta '+JSON.stringify(res.cum));
assert(res.svg>=2,'series chart draws base and stress');assert.strictEqual(res.serCols,n+1,'series table has every period');
// run record: current, then stale after an edit to the scenario
await page.evaluate(()=>stView('record'));t=await txt();assert(/Current/.test(t)&&/passed/.test(t),'record current with checks passed');
await page.evaluate(()=>{stOpen('s1');ST.row=0;stRowSet('value',3);stView('record');});t=await txt();assert(/Stale/.test(t),'editing the scenario marks the record stale');
assert(/failed/.test(t),'failed run kept in the record');
assert.deepStrictEqual(errors,[]);
console.log('PASS r498 stress workbench: scenarios, builder labels, run request, results table matches engine records, failed runs as alerts, waterfall reconciles, series chart and table, record stale after edit');
}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
