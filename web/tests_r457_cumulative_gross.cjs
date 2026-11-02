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
await page.locator('select[onchange*="feeStreamDriverSourceChange"]').filter({visible:true}).selectOption('account_activity');
const activity=page.locator('select[onchange*="driver.ref"]').filter({visible:true});
assert(await activity.locator('option').filter({hasText:'Lines › Cumulative gross acquisitions'}).count());
await activity.selectOption('lines-count::cumulative_gross_acquisitions');
assert.equal(await page.evaluate(()=>cfg.assumptions.obs_exposures[0].fee_streams[0].driver.ref),'lines-count::cumulative_gross_acquisitions');
assert.equal(await page.evaluate(()=>cfg.assumptions.obs_exposures[0].fee_streams[0].driver.measure),'period_end');
assert(await page.evaluate(()=>{const text=JSON.stringify(cfg);cfg=normalizeCfg(JSON.parse(text));return JSON.stringify(cfg)===text;}));
await page.evaluate(()=>{cfg.assumptions.cac_feeds.Renamed=cfg.assumptions.cac_feeds.Lines;delete cfg.assumptions.cac_feeds.Lines;renderContent();});
assert(await activity.locator('option').filter({hasText:'Renamed › Cumulative gross acquisitions'}).count());
assert.equal(await activity.inputValue(),'lines-count::cumulative_gross_acquisitions');
assert(await page.evaluate(()=>_accountActivityOptions('transaction').every(x=>!x.series_id.endsWith('::cumulative_gross_acquisitions'))),'stock is not offered as a monthly acquisition flow');
await page.evaluate(()=>{cfg.assumptions.cac_feeds.Renamed.intra_period_path='straight_line';renderContent();});
assert(await page.evaluate(()=>!_accountActivityOptions('account').some(x=>x.series_id==='lines-count::cumulative_gross_acquisitions')),'net stock interpolation is unavailable');
assert.deepStrictEqual(errors,[]);console.log('PASS r457 account-source selection, stock measure, persisted reference, rename stability, stock/flow separation and straight-line exclusion');
}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
