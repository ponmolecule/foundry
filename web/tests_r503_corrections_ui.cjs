// r503: corrective UI checks. Builder delay states the input's class and the fill (choosable); Lab reverse stress
// says "inconclusive" or "search failed" instead of "no breach"; Liquidity labels an unavailable line's draw as
// hypothetical and shows the LCR method note; an after-day-30 rate appears for runs longer than 30 days; an entered
// resource says where it sits; Reporting flags settings changed since the run.
const {chromium}=require('playwright'),fs=require('fs'),assert=require('assert'),cp=require('child_process');
const PY=`
import copy, json
from foundry.v2 import stress, liquidity as LQ
from foundry.v2.tests_r498_stress import BANK, key_for
from foundry.v2.tests_r502_liquidity import trust_bank, base_of
from foundry.v2.stress_report import deposit_classification
c = trust_bank()
k_new = key_for(c, lambda r: r["kind"] == "series" and r["field"].endswith("new_customers"))
k_oth = key_for(c, lambda r: r["kind"] == "series" and r["field"].endswith("driver.params.coefficient"))
c["stress_scenarios"] = [dict(id="d", name="Late growth", kind="idiosyncratic", version=1, funding="inherit",
    severities=[dict(id="x", label="X", overrides=[dict(target=k_new, op="delay", value=3, start=1), dict(target=k_oth, op="delay", value=2, start=1)])])]
c["liquidity_stress"]["line"]["available_from"] = 30
c["liquidity_stress"]["stress_day"]["month"] = 1
res = stress._engine_run(base_of(c))
out = LQ.run(c, res)
setup = dict(template=LQ.template(c), deposit_products=[dict(key=d["key"], name=d["name"]) for d in deposit_classification(c)],
             charter_type=LQ.charter_type(c), errors=[], applicability=LQ.applicability(c),
             lcr_categories={k: dict(rate=v[0], label=v[1]) for k, v in LQ.LCR_RULE.items()})
print(json.dumps(dict(cfg=c, res=res, out=out, setup=setup, targets=stress.targets(base_of(c)), k_new=k_new, k_oth=k_oth), default=str))
`;
(async()=>{
const F=JSON.parse(cp.execFileSync('python3',['-c',PY],{encoding:'utf8',maxBuffer:1<<28}));
const html=fs.readFileSync('web/console_v2.html','utf8').replace('<head>','<head><script>window.V31=true;window.V3=true;</script>').replace(/renderTabs\(\);\nwhoami\(\)\.then[^\n]+/,'');
const browser=await chromium.launch({executablePath:process.env.FOUNDRY_CHROMIUM_PATH,args:['--no-sandbox','--disable-gpu','--single-process','--no-zygote'],headless:true});
try{const page=await browser.newPage({viewport:{width:1400,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
await page.route('**/*',r=>{const u=r.request().url(),k=u.split('/api/v31/stress/')[1];
 if(k==='targets')return r.fulfill({json:{targets:F.targets}});
 if(k==='runs')return r.fulfill({json:{records:[]}});
 if(k==='probe')return r.fulfill({json:{ok:true,mode:'level'}});
 if(k==='liquidity/setup')return r.fulfill({json:F.setup});
 if(k==='liquidity')return r.fulfill({json:{result:F.out,stored:false}});
 if(k==='report')return r.fulfill({json:{report:null,state:'current',settings_changed_since_run:true,current_settings_fingerprint:'abcd1234abcd1234'}});
 return r.fulfill({json:{}});});
await page.goto('http://foundry.test');await page.setContent(html);
await page.evaluate(d=>{cfg=d.cfg;lastRes=d.res;lastErrs=null;lastRunFailure=null;cfg.scenario_name='r503 test';refresh=()=>{};scheduleAutosave=()=>{};_govSlug=()=>'';setTab('stress');},{cfg:F.cfg,res:F.res});
await page.waitForFunction(()=>ST.targets&&ST.targets.length>0);
// Builder: a flow delays with nothing happening; an unclassed driver must choose
await page.evaluate(()=>{stOpen('d');ST.row=0;renderContent();});await page.waitForTimeout(150);
let say=await page.evaluate(()=>document.querySelector('.st-say').innerText);
assert(/a flow \(new volume each period\); nothing happens during the delay/.test(say),'flow delay explained '+say);
let sel=await page.evaluate(()=>{const s=document.querySelector('select[aria-label="Fill during the delay"]');return s&&[...s.options].map(o=>o.textContent);});
assert(sel&&sel.some(x=>/Nothing happens \(zero\) · default/.test(x)),'fill control offers the class default '+JSON.stringify(sel));
await page.evaluate(()=>{ST.row=1;renderContent();});await page.waitForTimeout(150);
say=await page.evaluate(()=>document.querySelector('.st-say').innerText);
assert(/another kind of driver; choose what happens during the delay/.test(say),'unclassed driver asks for a choice '+say);
await page.evaluate(()=>stRowSet('fill','hold'));
assert(await page.evaluate(()=>_stScenarios()[0].severities[0].overrides[1].fill)==='hold','fill choice stored on the change');
// Lab reverse stress: failures never read as "no breach"
const head=await page.evaluate(()=>{const base={spec:{lo:1,hi:5},variable:'CRE · Charge off',window:{label:'M1 to M36'},evaluations:[{x:1,margin:null,breach:null,error:'x'},{x:3,margin:2,breach:false}],crossings:[],breaking_point:null,limitations:['1 of 2 evaluations failed'],failed_evaluations:1};
  return [labReverseResultHtml(Object.assign({},base,{status:'inconclusive'})),labReverseResultHtml(Object.assign({},base,{status:'search_failed'}))].map(h=>{const d=document.createElement('div');d.innerHTML=h;return d.innerText;});});
assert(/Inconclusive: 1 of 2 evaluations failed, so no breach cannot be claimed/.test(head[0])&&!/No breach within/.test(head[0]),'inconclusive heading');
assert(/The search failed/.test(head[1]),'failed heading');
// Liquidity: hypothetical line draw, LCR method, after-day-30 input, entered resource location
await page.evaluate(()=>{LQ.res=null;stView('liquidity');});await page.waitForFunction(()=>LQ.meta&&LQ.meta.template);
await page.evaluate(()=>lqRun());await page.waitForFunction(()=>!LQ.busy&&LQ.res);
let t=await page.evaluate(()=>document.getElementById('content').innerText);
assert(/\(hypothetical\)/.test(t)&&/Hypothetical\./.test(t)&&/sensitivity, not an available source/.test(t),'unavailable line draw labeled hypothetical');
assert(/balance-sheet illustration/.test(t),'capital after the draw labeled an illustration');
await page.evaluate(()=>lqTab('lcr'));t=await page.evaluate(()=>document.getElementById('content').innerText);
assert(/Simplified management calculation/.test(t)&&/Rule rate/.test(t),'LCR method note and rule-rate tag');
await page.evaluate(()=>{lqTab('setup');lqSet('stress_day.run_days','90','int');});
t=await page.evaluate(()=>document.getElementById('content').innerText);
assert(/After day 30 \(%\)/.test(t),'after-day-30 rate offered for a 90-day run');
const where=await page.evaluate(()=>[...document.querySelectorAll('select[aria-label="Where this asset sits"] option')].map(o=>o.textContent));
assert(where.includes('Part of projected cash')&&where.includes('Outside projected cash and securities'),'entered resource says where it sits');
// Reporting: settings changed since the run
await page.evaluate(()=>{ST.records=[{run_id:'r1',status:'completed',scenario_id:'d',scenario_version:1,scenario_name:'Late growth',severity_id:'x',severity_label:'X',kind:'idiosyncratic',started_at:'2026-11-13T00:00:00Z',state:'current',window:{periods:36,label:'M1 to M36'}}];cfg.stress_reporting={primary_run_id:'r1'};ST.rep['r1']={error:'Not stored in this test.',changed:true,fp:'abcd1234abcd1234',key:_stRepKey()};stView('reporting');});
t=await page.evaluate(()=>document.getElementById('content').innerText);
assert(/Reporting settings \(classifications, policy minimums or window\) changed since this run/.test(t),'settings change flagged');
assert.deepStrictEqual(errors,[]);
console.log('PASS r503 corrections UI: delay class and fill, inconclusive and failed reverse searches, hypothetical line draw, LCR method note, after-day-30 input, resource location, reporting settings change');
}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
