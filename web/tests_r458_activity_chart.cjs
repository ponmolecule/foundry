// r437: Configuration editors on the field system: workforce populations and expense categories on one label column
// with each path beside its value (segmented, driving the existing selects), other income lines, and capital raises /
// borrowings as small tables. Rendering leaves the configuration alone; every control still writes its own field.
const {chromium}=require('playwright'),fs=require('fs'),assert=require('assert'),{execFileSync}=require('child_process');
(async()=>{
const fx=JSON.parse(execFileSync('python3',['-c',`import json
from foundry.v2.run_q import run_v2
c=json.load(open('foundry/fixtures/universal_template_bank.json'))
print(json.dumps({'cfg':c,'result':run_v2(c)}))`],{encoding:'utf8',maxBuffer:1<<28}));
const html=fs.readFileSync('web/console_v2.html','utf8').replace('<script src="/web/rates_workspace.js"></script>','<script>'+fs.readFileSync('web/rates_workspace.js','utf8')+'</script>').replace('<head>','<head><script>window.V3=true;window.V31=true;</script>').replace(/renderTabs\(\);\nwhoami\(\)\.then[^\n]+/,'');
const browser=await chromium.launch({executablePath:process.env.FOUNDRY_CHROMIUM_PATH,args:['--no-sandbox','--disable-gpu','--single-process','--no-zygote'],headless:true});
try{
const page=await browser.newPage({viewport:{width:1600,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>d.dismiss());page.setDefaultTimeout(15000);
await page.route('**/*',r=>r.fulfill({status:200,json:{}}));await page.goto('http://foundry.test');await page.setContent(html);
await page.evaluate(f=>{cfg=normalizeCfg(f.cfg);lastRes=f.result;refresh=()=>{};scheduleAutosave=()=>{};document.body.classList.add('insp-closed');renderTabs();setTab('config');},fx);
const settle=()=>page.waitForTimeout(100);
const mod=async m=>{await page.evaluate(m=>document.querySelector('.cfg-mod[data-cfg-mod="'+m+'"]').click(),m);await settle();};
const vis=sel=>page.locator(sel).filter({visible:true});



await page.evaluate(()=>{
 cfg.assumptions.cac_feeds.Lines={series_id:'lines-auc',customer_count_series_id:'lines-count',beginning_customers:0,channels:[]};
 const p=cfg.assumptions.obs_exposures[0];p.fee_streams=[{name:'Advance Activation Marketing',quantity_series_id:'activation',basis:'account',driver:{source:'constant',trajectory:'flat',params:{base:0}},rate:{behavior:'flat',params:{unit_fee:{value:0,period:'year'}}},cost:{kind:'none',params:{}},timing:{start_period:1}}];
 document.getElementById('content').innerHTML='<div id="activity-test"></div>';
 renderContent=()=>{document.getElementById('activity-test').innerHTML=_feeStreamsSectionHtml('obs',p,'assumptions.obs_exposures.0',0);};renderContent();
});
const check=await page.evaluate(()=>{
 const st=cfg.assumptions.obs_exposures[0].fee_streams[0];
 st.cost={kind:'per_account',params:{cost_per_account:45}};
 lastRes.fee_stream_quantities={series:{activation:Array.from({length:60},(_,i)=>i===59?4147.63:i+1)}};
 lastRes.fee_stream_economics={series:{activation:{reported_fee_income:Array(60).fill(0),fee_product_cost:Array.from({length:60},(_,i)=>i===59?16704.1:i+1)}}};
 window._stTab='activity';
 document.getElementById('activity-test').innerHTML=_lfxLiveHtml('sro',0,0);
 return JSON.stringify(cfg);
});
assert(await page.locator('[data-lfx-live="sro"]').innerText().then(t=>t.includes('Resolved count')&&t.includes('4,147.63')&&!t.includes('Sum,')));
await page.evaluate(()=>stTabSet('costs'));
assert(await page.locator('[data-lfx-live="sro"]').innerText().then(t=>t.includes('Stream cost')&&t.includes('16.7041')&&t.includes('$000s')));
await page.evaluate(()=>stTabSet('activity'));
assert(await page.locator('[data-lfx-live="sro"]').innerText().then(t=>t.includes('Resolved count')&&t.includes('4,147.63')));
assert.equal(await page.evaluate(()=>JSON.stringify(cfg)),check,'tab changes preserve inputs');
assert.equal(await page.evaluate(()=>_feeStreamResolvedOutput(0,0,lastRes).label),'Stream cost','other result surfaces preserve posting semantics');
assert.deepStrictEqual(errors,[]);console.log('PASS r458 activity count, cost chart, tab switching, input preservation and posting semantics');
}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
