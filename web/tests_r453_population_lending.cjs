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
 const a=cfg.assumptions;const names=['5–10 practitioners','11–24 practitioners','25–49 practitioners','50+ practitioners'];
 a.cac_feeds={Lines:{series_id:'lines-feed',customer_count_series_id:'lines-count',beginning_customers:0,channels:[],population_composition:{population_series_id:'line-pop',population_name:'Line accounts',bands:names.map((name,i)=>({id:'b'+i,series_id:'band'+i,name,opening:0,units_per_customer:1})),channel_shares:{},rounding:'none'}}};
 a.balance_components_model={inputs:[{id:'tpv',name:'Annual TPV',unit:'money_per_unit',spec:{source:'weighted_sum',unit:'money_per_unit',components:names.map((name,i)=>({id:'c'+i,name,amount_spec:{source:'entered',value:100000*(i+1),unit:'money_per_unit'},weight_spec:{source:'entered',value:.25,unit:'share'}}))}}]};
 const p=a.lending_products[0];p.balance_driver={source:'customer_acquisition_count',series_id:'lines-count',measure:'period_end',average_balance_per_customer_spec:{source:'input_ref',input_id:'tpv',factors:[{name:'Advance Percentage',source:'entered',value:.04109589041,unit:'share'}]}};
 window.sharedBefore=JSON.stringify(a.balance_components_model);window.factorBefore=JSON.stringify(p.balance_driver.average_balance_per_customer_spec.factors);
 document.getElementById('content').innerHTML='<div id="loan-test"></div>';
 renderContent=()=>{document.getElementById('loan-test').innerHTML=_loanAmountEditor(0,p,'assumptions.lending_products.0');};renderContent();
});
await page.getByLabel('Lending weight source').selectOption('active_population');
assert.equal(await page.getByLabel('Lending weight source').inputValue(),'active_population');
assert.equal(await page.getByLabel('Acquisition band for 5–10 practitioners').inputValue(),'b0');
assert.equal(await page.getByLabel('Acquisition band for 50+ practitioners').inputValue(),'b3');
await page.getByLabel('Acquisition band for 5–10 practitioners').selectOption('b1');
assert.equal(await page.evaluate(()=>cfg.assumptions.lending_products[0].balance_driver.average_balance_per_customer_spec.population_band_map.c0),'b1');
assert(await page.evaluate(()=>JSON.stringify(cfg.assumptions.balance_components_model)===sharedBefore));
assert(await page.evaluate(()=>JSON.stringify(cfg.assumptions.lending_products[0].balance_driver.average_balance_per_customer_spec.factors)===factorBefore));
await page.getByLabel('Lending weight source').selectOption('entered');
assert.equal(await page.evaluate(()=>cfg.assumptions.lending_products[0].balance_driver.average_balance_per_customer_spec.weight_source),undefined);
await page.getByLabel('Lending weight source').selectOption('active_population');
assert.equal(await page.getByLabel('Acquisition band for 5–10 practitioners').inputValue(),'b1','explicit mapping retained on toggle');
assert(await page.evaluate(()=>{const s=JSON.stringify(cfg);cfg=normalizeCfg(JSON.parse(s));return JSON.stringify(cfg)===s;}),'serialize/reload retains source, stable band mapping, factors and shared inputs');
assert.deepStrictEqual(errors,[]);console.log('PASS r453 live weight source, band mapping, shared-input isolation, factor retention, toggling and reload');
}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
