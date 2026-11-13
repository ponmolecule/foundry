// r500: coverage panel and classes, combined from frozen parts, rate shift (basis points, whole horizon, exposure),
// delay (series only), calibration records, and the rate-direction panel in Results. Endpoints mocked with engine output.
const {chromium}=require('playwright'),fs=require('fs'),assert=require('assert'),cp=require('child_process');
const PY=`
import copy, json
from foundry.v2 import stress, stress_report as R
from foundry.v2.tests_r498_stress import BANK, key_for
c = copy.deepcopy(BANK)
k_co = key_for(c, lambda r: r["product_name"] == "Commercial Real Estate" and r["field"] == "charge_off_ann")
k_ch = key_for(c, lambda r: r["kind"] == "series" and r["field"].startswith("cac_feeds.") and r["unit_kind"] == "count")
m = dict(id="m", name="Rates and credit", kind="macro", version=1, funding="inherit", severities=[dict(id="severe", label="Severe", overrides=[
    dict(target=stress.RATE_KEY, op="add", value=-200, start=1, end=None, calibration=dict(rationale="zero bound", source="DFAST 2026", approval="reviewed")),
    dict(target=k_co, op="multiply", value=2.5, start=1, end=None)])])
i = dict(id="i", name="Slow channel", kind="idiosyncratic", version=1, funding="inherit", severities=[dict(id="severe", label="Severe", overrides=[
    dict(target=k_ch, op="delay", value=6, start=1, end=None)])])
c["stress_scenarios"] = [m, i]
rec = stress.run_scenario(c, m)[0]
rec["state"] = "current"
base = {k: v for k, v in c.items() if k not in R.STRESS_KEYS}
print(json.dumps(dict(cfg=c, targets=stress.targets(base), rec=rec, cov=stress.coverage(c), probe=stress.probe_target(c, stress.RATE_KEY),
                      res=stress._engine_run(base), k_ch=k_ch), default=str))
`;
(async()=>{
const F=JSON.parse(cp.execFileSync('python3',['-c',PY],{encoding:'utf8',maxBuffer:1<<28}));
const html=fs.readFileSync('web/console_v2.html','utf8').replace('<head>','<head><script>window.V31=true;window.V3=true;</script>').replace(/renderTabs\(\);\nwhoami\(\)\.then[^\n]+/,'');
const browser=await chromium.launch({executablePath:process.env.FOUNDRY_CHROMIUM_PATH,args:['--no-sandbox','--disable-gpu','--single-process','--no-zygote'],headless:true});
try{const page=await browser.newPage({viewport:{width:1400,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
await page.route('**/*',r=>{const u=r.request().url(),k=u.split('/api/v31/stress/')[1];
 if(k==='targets')return r.fulfill({json:{targets:F.targets}});
 if(k==='runs')return r.fulfill({json:{records:[F.rec]}});
 if(k==='coverage'){const body=JSON.parse(r.request().postData());const kinds=body.cfg.stress_scenarios.map(s=>s.kind);return r.fulfill({json:Object.assign({},F.cov,{complete:['macro','idiosyncratic','combined'].every(x=>kinds.includes(x))})});}
 if(k==='probe')return r.fulfill({json:JSON.parse(r.request().postData()).target===F.probe&&false?{}:(JSON.parse(r.request().postData()).target==='bank:rates:parallel_shift_bp'?F.probe:{ok:true,mode:'level'})});
 if(k==='check')return r.fulfill({json:{ok:true,errors:[],warnings:['calibration record incomplete']}});
 return r.fulfill({json:{}});});
await page.goto('http://foundry.test');await page.setContent(html);
await page.evaluate(d=>{cfg=d.cfg;lastRes=d.res;lastErrs=null;lastRunFailure=null;cfg.scenario_name='r500 test';refresh=()=>{};scheduleAutosave=()=>{};setTab('stress');},{cfg:F.cfg,res:F.res});
await page.waitForFunction(()=>ST.records.length===1&&ST.targets&&ST.targets.length>0&&ST.cov);
const txt=()=>page.evaluate(()=>document.getElementById('content').innerText);
// coverage and grouping
let cov=await page.evaluate(()=>[...document.querySelectorAll('.st-cov')].map(x=>[x.classList.contains('ok'),x.innerText.replace(/\s+/g,' ')]));
assert.deepStrictEqual(cov.map(x=>x[0]),[true,true,false],'macro and idiosyncratic present, combined missing '+JSON.stringify(cov));
let t=await txt();assert(/MACROECONOMIC/.test(t)&&/IDIOSYNCRATIC/.test(t),'scenarios grouped by class');
assert(F.cov.warnings.length&&t.includes(F.cov.warnings[0].slice(0,30)),'coverage warnings shown');
// combined from frozen parts
await page.evaluate(()=>{ST.combOpen=true;renderContent();});
await page.evaluate(()=>stBuildCombined(document.getElementById('stCombM').value,document.getElementById('stCombI').value));
const comb=await page.evaluate(()=>{const s=_stScenarios().find(x=>x.kind==='combined');return {n:s.severities[0].overrides.length,parts:s.parts.map(p=>[p.scenario_id,p.version]),from:s.severities[0].overrides.map(o=>o.from_part)};});
assert(comb.n===3&&JSON.stringify(comb.parts)===JSON.stringify([['m',1],['i',1]])&&comb.from.join()==='m,m,i','combined freezes both parts and tags each change with its part '+JSON.stringify(comb));
await page.evaluate(()=>{const m=_stScenarios().find(x=>x.id==='m');m.version=2;stView('builder');});
t=await txt();assert(/now v2/.test(t)&&/Refreeze parts/.test(t),'a changed part is reported with a refreeze action');
await page.evaluate(()=>stRefreeze());
assert.strictEqual(await page.evaluate(()=>_stScenarios().find(x=>x.kind==='combined').parts[0].version),2,'refreeze picks up the part');
// rate shift row: whole horizon, basis points, only a shift operation, exposure summary
await page.evaluate(()=>{stOpen('m');ST.row=0;renderContent();});await page.waitForTimeout(200);
const rate=await page.evaluate(()=>{const ops=[...document.querySelectorAll('.st-edit select')][1];return {ops:[...ops.options].map(o=>o.value),lab:document.querySelector('.st-edit .st-egrid').innerText.replace(/\s+/g,' '),probe:(document.querySelector('.st-probe')||{}).innerText};});
assert.deepStrictEqual(rate.ops,['add'],'the rate path only shifts');assert(/Value · bp/.test(rate.lab)&&/Whole horizon/.test(rate.lab),'basis points over the whole horizon '+rate.lab);
assert(/products reprice/.test(rate.probe)&&/keep their rate/.test(rate.probe),'exposure summarized, details behind a disclosure '+rate.probe);
// delay row: offered for a series input; From only
await page.evaluate(()=>{stOpen('i');ST.row=0;renderContent();});await page.waitForTimeout(200);
const dl=await page.evaluate(()=>{const ops=[...document.querySelectorAll('.st-edit select')][1];return {ops:[...ops.options].map(o=>o.value),lab:document.querySelector('.st-edit .st-egrid').innerText.replace(/\s+/g,' '),say:document.querySelector('.st-say').innerText};});
assert(dl.ops.includes('delay')&&/Delay · periods/.test(dl.lab)&&/To Horizon/.test(dl.lab),'delay in periods, running to the horizon '+dl.lab);
assert(/past the horizon are dropped and disclosed/.test(dl.say)&&/Committed costs do not move/.test(dl.say),'delay says what happens to shifted volume and costs');
// calibration record
await page.evaluate(()=>{stRowSet('cal.rationale','Partner integration slips');stRowSet('cal.source','Partner contract timeline');stRowSet('cal.approval','approved');});
assert.strictEqual(await page.evaluate(()=>_stScenarios().find(x=>x.id==='i').severities[0].overrides[0].calibration.approval),'approved');
t=await txt();assert(/Approved/.test(t),'calibration status shown on the change');
// a scalar input never offers delay
const sc=await page.evaluate(()=>{stRowAdd();const i=ST.targets.findIndex(t=>t.kind==='scalar'&&t.key);stRowSet('target',ST.targets[i].key);return [...[...document.querySelectorAll('.st-edit select')][1].options].map(o=>o.value);});
assert(!sc.includes('delay'),'single-value inputs cannot be delayed');
// results: rate direction panel
await page.evaluate(id=>{_stScenarios().find(x=>x.id==='m').version=1;ST.resSel[id]=true;stFocus(id);},F.rec.run_id);
t=await txt();const d=F.rec.rate_direction;
assert(/Which rate direction hurts/.test(t)&&t.includes((d.adverse_for_earnings>0?'+':'')+d.adverse_for_earnings+' bp'),'rate direction panel with the adverse direction');
assert.deepStrictEqual(errors,[]);
console.log('PASS r500 scenario design UI: coverage and classes, combined from frozen parts with refreeze, rate shift in bp over the whole horizon with exposure, delay for series only, calibration records, rate-direction panel');
}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
