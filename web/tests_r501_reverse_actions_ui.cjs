// r501: Lab Reverse Stress mode (explore, promote to formal), Lab results become revised plans or stress comparisons
// (no Adopt), management actions before and after, design rows in the comparison grid, breaking points.
const {chromium}=require('playwright'),fs=require('fs'),assert=require('assert'),cp=require('child_process');
const PY=`
import copy, json
from foundry.v2 import stress, reverse_stress as RS, actions as ACT, stress_report as R
from foundry.v2.tests_r498_stress import BANK, key_for
c = copy.deepcopy(BANK)
k_co = key_for(c, lambda r: r["product_name"] == "Commercial Real Estate" and r["field"] == "charge_off_ann")
c["stress_reporting"] = {"policy_minimums": {"leverage": {"value": 22.0, "source": "policy"}}}
s1 = dict(id="s1", name="CRE spike", kind="idiosyncratic", version=1, funding="inherit", severities=[dict(id="severe", label="Severe", overrides=[dict(target=k_co, op="multiply", value=25, start=1, end=None)])])
k_dep = key_for(c, lambda r: r["family"] == "deposit_products" and r["field"] == "rate_paid_ann" and r["product_name"].startswith("Time"))
d = dict(id="d1", name="Cheaper CDs", kind="design", version=1, funding="inherit", severities=[dict(id="design", label="Unstressed", overrides=[dict(target=k_dep, op="replace", value=0.035, start=1, end=None)])])
x = dict(id="x1", name="Cheaper CDs under CRE spike", kind="design_stress", design_of="d1", stress_of=dict(scenario_id="s1", severity_id="severe", version=1), funding="inherit", version=1,
         severities=[dict(id="severe", label="Severe", overrides=d["severities"][0]["overrides"] + s1["severities"][0]["overrides"])])
c["stress_scenarios"] = [s1, d, x]
recs = [stress.run_scenario(c, s, keep_results=True, attribution=(s["id"] == "s1"))[0] for s in (s1, d, x)]
res = recs[0].pop("_results"); [r.pop("_results") for r in recs[1:]]
for r in recs: r["state"] = "current"; r["archive"] = {"stress_cfg": "a", "stress_result": "b"}
act = ACT.run(c, recs[0], res["stress_cfg"], res["stress_res"], [dict(type="capital_injection", amount=5000, period=12)]); act.pop("_results"); act["state"] = "current"
rev = RS.run(c, dict(kind="change", target=k_co, op="multiply", lo=1, hi=60, grid=5))
rrec = RS.record(c, rev); rrec["state"] = "current"
base = {k: v for k, v in c.items() if k not in R.STRESS_KEYS}
print(json.dumps(dict(cfg=c, targets=stress.targets(base), recs=recs, act=act, rev=rev, rrec=rrec, res=stress._engine_run(base), k_co=k_co), default=str))
`;
(async()=>{
const F=JSON.parse(cp.execFileSync('python3',['-c',PY],{encoding:'utf8',maxBuffer:1<<28}));
const html=fs.readFileSync('web/console_v2.html','utf8').replace('<head>','<head><script>window.V31=true;window.V3=true;</script>').replace(/renderTabs\(\);\nwhoami\(\)\.then[^\n]+/,'');
const browser=await chromium.launch({executablePath:process.env.FOUNDRY_CHROMIUM_PATH,args:['--no-sandbox','--disable-gpu','--single-process','--no-zygote'],headless:true});
try{const page=await browser.newPage({viewport:{width:1400,height:1000}}),errors=[],posts={};page.on('pageerror',e=>errors.push(e.message));
await page.route('**/*',r=>{const u=r.request().url(),k=u.split('/api/v31/stress/')[1];if(k)(posts[k]=posts[k]||[]).push(JSON.parse(r.request().postData()||'{}'));
 if(k==='targets')return r.fulfill({json:{targets:F.targets}});
 if(k==='runs')return r.fulfill({json:{records:F.recs.concat([F.act,F.rrec])}});
 if(k==='reverse'){const b=JSON.parse(r.request().postData());return r.fulfill({json:b.formal?{result:F.rev,formal:true,record:F.rrec}:{result:F.rev,formal:false}});}
 if(k==='actions')return r.fulfill({json:{record:F.act}});
 if(k==='report')return r.fulfill({status:404,json:{error:'n/a'}});
 return r.fulfill({json:{}});});
await page.goto('http://foundry.test');await page.setContent(html);
await page.evaluate(d=>{cfg=d.cfg;lastRes=d.res;lastErrs=null;lastRunFailure=null;cfg.scenario_name='r501 test';refresh=()=>{};scheduleAutosave=()=>{};setTab('stress');},{cfg:F.cfg,res:F.res});
await page.waitForFunction(()=>ST.records.length===5&&ST.targets&&ST.targets.length>0);
const txt=()=>page.evaluate(()=>document.getElementById('content').innerText);
// Results: standard runs only as columns; design row; actions; breaking points
await page.evaluate(id=>stFocus(id),F.recs[0].run_id);
const grid=await page.evaluate(()=>({cols:[...document.querySelectorAll('.st-colh')].map(x=>x.innerText.trim()),rows:[...document.querySelectorAll('.st-rowh b')].map(x=>x.innerText)}));
assert.deepStrictEqual(grid.rows,['Base design','Cheaper CDs'],'design alternative is a row');
assert(grid.cols.length===2&&!grid.cols.some(x=>/Cheaper/.test(x)),'design runs are not stress columns '+JSON.stringify(grid.cols));
const cells=await page.evaluate(()=>[...document.querySelectorAll('.st-cell .st-big')].map(x=>x.innerText.split('%')[0]));
const lev=r=>Math.min(...r.stress.series.lev.slice(0,36)).toFixed(2);
assert.deepStrictEqual(cells,[Math.min(...F.recs[0].base.series.lev.slice(0,36)).toFixed(2),lev(F.recs[0]),lev(F.recs[1]),lev(F.recs[2])],'grid cells: base, stress, design, design under stress');
let t=await txt();
assert(/Management actions/.test(t)&&/Before actions/.test(t)&&/After actions/.test(t),'actions shown before and after');
assert(/Facility fees and other costs/.test(t)&&/Interest on drawn balances/.test(t),'action costs shown');
assert(/Breaking points/.test(t)&&t.includes(F.rev.variable),'formal reverse stress listed as a breaking point');
// actions form posts typed actions against the run
await page.evaluate(()=>{ST.acts=[];stActAdd('contingency_line');});
await page.evaluate(id=>stActRun(id),F.recs[0].run_id);await page.waitForTimeout(200);
const ap=posts.actions.slice(-1)[0];assert(ap.run_id===F.recs[0].run_id&&ap.actions[0].type==='contingency_line'&&ap.actions[0].commitment_fee_bp===25,'actions request '+JSON.stringify(ap.actions));
// Runs: type chips; Results/Reporting never offer reverse or design runs as primary
await page.evaluate(()=>stView('runs'));t=await txt();
assert(/Reverse stress/.test(t)&&/With actions/.test(t)&&/Lab design/.test(t),'run types are labelled');
await page.evaluate(()=>stView('reporting'));
const prim=await page.evaluate(()=>[...document.querySelectorAll('#stPrim option')].map(o=>o.textContent));
assert(prim.length===2&&/CRE spike/.test(prim[1]),'only standard stress runs can be the primary case '+JSON.stringify(prim));
// Lab: Reverse Stress mode
await page.evaluate(()=>{setTab('lab');});await page.waitForTimeout(100);
await page.evaluate(()=>setLabMode('reverse'));await page.waitForTimeout(300);
t=await page.evaluate(()=>document.getElementById('content').innerText);
assert(/Reverse Stress/.test(t)&&/One change/.test(t)&&/A whole scenario, scaled/.test(t)&&/Any ratio breaches a selected threshold/.test(t),'reverse stress controls');
await page.evaluate(k=>{_rs.target=k;_rs.op='multiply';_rs.lo=1;_rs.hi=60;_rs.grid=5;},F.k_co);
await page.evaluate(()=>runLabReverse(false));await page.waitForFunction(()=>!_rs.busy&&_rs.res);
t=await page.evaluate(()=>document.getElementById('content').innerText);
assert(/Breaks at/.test(t)&&/Promote to formal/.test(t)&&/nothing is claimed outside these bounds/.test(t),'exploration result with limitations and promote');
assert(posts.reverse.slice(-1)[0].formal===false&&posts.reverse.slice(-1)[0].spec.target===F.k_co,'exploration is not formal');
await page.evaluate(()=>runLabReverse(true));await page.waitForFunction(()=>!_rs.busy&&_rs.formal);
t=await page.evaluate(()=>document.getElementById('content').innerText);
assert(/Formal record stored/.test(t)&&posts.reverse.slice(-1)[0].formal===true,'promote to formal');
// Lab results: no Adopt anywhere
const htmlNow=fs.readFileSync('web/console_v2.html','utf8');
assert(!/Adopt into model/.test(htmlNow)&&/Create revised plan/.test(htmlNow)&&/Compare under stress/.test(htmlNow),'Adopt replaced by revised plan and compare under stress');
assert.deepStrictEqual(errors,[]);
console.log('PASS r501 reverse stress and actions UI: Lab Reverse Stress explore and promote, design row in the grid, standard runs only as columns and primary, actions before and after with costs, breaking points, run types labelled, no Adopt');
}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
