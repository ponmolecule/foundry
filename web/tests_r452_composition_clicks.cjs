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

await page.evaluate(()=>{cfg.assumptions.cac_feeds={Test:{series_id:'test-feed',customer_count_series_id:'test-count',beginning_customers:0,channels:[{name:'Sales',method:'pool_conversion',params:{},derived_series_ids:{new_customers:'sales'}}]}};});
await mod('cac');
await page.evaluate(()=>{window._cacnSel='test-feed';cacCompositionEdit('Test');});
const band=page.getByLabel('Band name',{exact:true});
await band.fill('Small');
await page.getByRole('button',{name:'+ Band',exact:true}).click();
assert.equal(await band.count(),2,'one click adds band after committing edited name');
assert.equal(await band.first().inputValue(),'Small');
await page.getByLabel('Sales share for Small').fill('40');
await page.getByLabel('Sales share for Band 2').fill('60');
await page.getByLabel('Associated population name').fill('Line account population');
await page.evaluate(()=>{window._compositionInput=document.querySelector('[aria-label="Associated population name"]');cacnRefresh();});
assert(await page.evaluate(()=>window._compositionInput===document.querySelector('[aria-label="Associated population name"]')),'preview refresh preserves draft input nodes');

await page.getByRole('button',{name:'Apply',exact:true}).click();
const saved=await page.evaluate(()=>JSON.stringify(cfg));
await page.evaluate(()=>{lastRes={customer_acquisition:{Test:{annual:[{end_cust:1234,new_cust:1234,total_spend:259,end_auc:0,channels:[{new_customers:1234,spend:259}]}],customerEndByMonth:[0,1234]}}};refreshConfigPreviews();});
assert((await page.locator('.cacn-es').innerText()).includes('259'),'acquisition headline refreshes');
assert((await page.locator('.cacn-rail').innerText()).includes('1,234'),'rail count refreshes');

assert.equal(await page.getByRole('button',{name:'Apply',exact:true}).count(),0,'one click applies after editing population name');
assert.equal(await page.evaluate(()=>cfg.assumptions.cac_feeds.Test.population_composition.population_name),'Line account population');
await page.evaluate(()=>{const saved=JSON.stringify(cfg);cfg=normalizeCfg(JSON.parse(saved));renderContent();});
assert.equal(await page.evaluate(()=>JSON.stringify(cfg)),saved,'reload normalization preserves all authored config');
await page.evaluate(()=>{lastRes=null;lastErrs=[{message:'Population bands do not reconcile to the feed'}];refreshConfigPreviews();});
assert((await page.locator('.config-run-error').innerText()).includes('Population bands do not reconcile'));
await page.evaluate(()=>{lastErrs=null;refreshConfigPreviews();});
assert.equal(await page.locator('.config-run-error').count(),0);
await page.evaluate(f=>{lastRes=f.result;lastErrs=null;},fx);
await mod('nie');
await page.evaluate(()=>refreshConfigPreviews());
assert(!(await page.locator('[data-engine-preview="nie-kpis"]').innerText()).includes('—'),'successful result restores expense headlines');
assert.deepStrictEqual(errors,[]);console.log('PASS r452 single-click add/apply, latest field commit, saved config reload, visible calculation failure and recovery');
}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
