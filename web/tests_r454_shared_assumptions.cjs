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

const count=()=>page.evaluate(()=>_sharedInputs().length);
const saved=await page.evaluate(()=>JSON.stringify(cfg));
await page.evaluate(()=>{loanAmountMode(0,'shared');loanAmountMode(0,'entered');loanAmountMode(0,'shared');});
assert.equal(await page.evaluate(()=>JSON.stringify(cfg)),saved,'amount mode round trip preserves shared settings and factors');
for(let k=0;k<3;k++)await page.getByRole('button',{name:'+ New shared assumption',exact:true}).click();
assert.equal(await count(),1,'opening draft never creates saved inputs');
await page.getByLabel('New shared assumption name').fill('Annual TPV');
assert(await page.getByRole('button',{name:'Create assumption',exact:true}).isDisabled());
await page.getByRole('button',{name:'Cancel',exact:true}).click();
assert.equal(await page.evaluate(()=>JSON.stringify(cfg)),saved,'cancel leaves entire config unchanged');
await page.getByRole('button',{name:'+ New shared assumption',exact:true}).click();
await page.getByLabel('New shared assumption name').fill('Line amount');
await page.getByRole('button',{name:'Create assumption',exact:true}).click();
assert.equal(await count(),2);
assert(await page.evaluate(()=>JSON.stringify(cfg.assumptions.lending_products[0].balance_driver.average_balance_per_customer_spec.factors)===factorBefore));
await page.evaluate(()=>loanSharedCreate(0));
assert.equal(await count(),2,'duplicate commit is idempotent');
await page.getByLabel('Shared amount',{exact:true}).selectOption('tpv');
for(let k=0;k<3;k++){await page.getByLabel('Lending weight source').selectOption('active_population');await page.getByLabel('Lending weight source').selectOption('entered');}
assert.equal(await count(),2,'selecting and changing weights never creates inputs');
await page.evaluate(()=>{
 const blank=id=>({id,name:'Weighted amount per customer',unit:'money_per_unit',amount_time_basis:'year',spec:{source:'weighted_sum',unit:'money_per_unit',components:[{id:'part-'+id,name:'Component 1',amount_spec:{source:'entered',trajectory:'flat',value:0,unit:'money_per_unit'},weight_spec:{source:'entered',trajectory:'flat',value:1,unit:'share'}}]}});
 _sharedInputs().push(blank('empty-1'),blank('empty-2'),blank('protected'));
 cfg.assumptions.lending_products[1].test_reference={source:'input_ref',input_id:'protected'};
 cfg.assumptions.lending_products[0].balance_driver.average_balance_per_customer_spec.input_id='empty-1';renderContent();
});
assert.equal(await page.getByLabel('Shared amount',{exact:true}).locator('option').filter({hasText:'Weighted amount per customer ·'}).count(),3,'duplicate names disambiguated');
await page.getByText('Manage shared assumptions',{exact:true}).click();
await page.getByRole('button',{name:'Remove unused empty entries',exact:true}).click();
assert.deepEqual(await page.evaluate(()=>_sharedInputs().map(x=>x.id).filter(x=>x.startsWith('empty'))),[]);
assert(await page.evaluate(()=>_sharedInputs().some(x=>x.id==='protected')),'referenced placeholder protected');
assert.equal(await page.getByLabel('Shared amount',{exact:true}).inputValue(),'');
await page.evaluate(()=>{loanSharedRemove(0,'protected');loanSharedRemove(0,'tpv');});
assert(!await page.evaluate(()=>_sharedInputs().some(x=>x.id==='tpv')),'unused configured assumption can be explicitly removed');
assert(await page.evaluate(()=>_sharedInputs().some(x=>x.id==='protected')));
assert(await page.evaluate(()=>JSON.stringify(cfg.assumptions.lending_products[0].balance_driver.average_balance_per_customer_spec.factors)===factorBefore));
assert(await page.evaluate(()=>{const s=JSON.stringify(cfg);cfg=normalizeCfg(JSON.parse(s));return JSON.stringify(cfg)===s;}));

await page.evaluate(()=>{
 const p=cfg.assumptions.lending_products[0];p.balance_mode='linked_customer_level';
 renderContent=()=>{const host=document.getElementById('loan-test');host.innerHTML='<div class="product-card" data-fam="lending" data-i="0"><div class="pp-sec" data-pp="setup">'+_loanAmountEditor(0,p,'assumptions.lending_products.0')+'</div></div>';lfgDecorate(host.firstElementChild);};renderContent();
});
const beforeDecorated=await count();
await page.getByRole('button',{name:'+ New shared assumption',exact:true}).click();
await page.getByLabel('New shared assumption name').fill('Decorated test');
await page.getByRole('button',{name:'Create assumption',exact:true}).click();
assert.equal(await count(),beforeDecorated+1,'decorated production fields create once');
await page.getByLabel('Shared amount',{exact:true}).click();
await page.keyboard.press('Escape');
assert.equal(await count(),beforeDecorated+1,'opening production dropdown never creates an assumption');
await page.screenshot({path:'/workspace/scratch/370303911165/r454-shared-controls.png',fullPage:true});
assert.deepStrictEqual(errors,[]);console.log('PASS r454 named draft, cancel/no mutation, duplicate protection, factor retention, safe empty cleanup, reference protection, deletion, reload');
}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
