// r447: opt-in live band weights preserve authored amounts and entered-weight drafts.
const {chromium}=require('playwright'),fs=require('fs'),assert=require('assert'),{execFileSync}=require('child_process');
(async()=>{
const fx=JSON.parse(execFileSync('python3',['-c',`import json
from foundry.v2.run_q import run_v2
c=json.load(open('foundry/fixtures/universal_template_bank.json'))
from foundry.v2.tests_r429_composition import setup
from foundry.v2.tests_r447_population_deposits import product
c['assumptions']['cac_feeds'].update(setup()['cac_feeds']);p=c['assumptions']['deposit_products'][0];p.update(product());p.update(opening_balance=0,growth_per_period=0,runoff_per_period=0,new_deposits_per_period=0,avg_maturity_m=0)
for k in ('growth_q','runoff_q','new_deposits_q','overrides'):p.pop(k,None)
r=run_v2(c)
s=p['balance_driver']['balance_per_customer_spec'];s.pop('weight_source')
for row,band in zip(s['components'],c['assumptions']['cac_feeds']['Practices']['population_composition']['bands']):row['name']=band['name'];row.pop('population_band_id')
print(json.dumps({'cfg':c,'result':r}))`],{encoding:'utf8',maxBuffer:1<<28}));
const html=fs.readFileSync('web/console_v2.html','utf8').replace('<script src="/web/rates_workspace.js"></script>','<script>'+fs.readFileSync('web/rates_workspace.js','utf8')+'</script>').replace('<head>','<head><script>window.V3=true;window.V31=true;</script>').replace(/renderTabs\(\);\nwhoami\(\)\.then[^\n]+/,'');
const browser=await chromium.launch({executablePath:process.env.FOUNDRY_CHROMIUM_PATH,args:['--no-sandbox','--disable-gpu','--single-process','--no-zygote'],headless:true});
try{
const page=await browser.newPage({viewport:{width:1600,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>d.dismiss());page.setDefaultTimeout(15000);
await page.route('**/*',r=>r.fulfill({status:200,json:{}}));await page.goto('http://foundry.test');await page.setContent(html);
await page.evaluate(f=>{cfg=normalizeCfg(f.cfg);lastRes=f.result;window._runs=0;refresh=()=>{window._runs++;};scheduleAutosave=()=>{};document.body.classList.add('insp-closed');renderTabs();setTab('products');},fx);

await page.evaluate(()=>{window._prdSel=cfg.assumptions.deposit_products[0];window._prdView='product';window._prdTab='setup';renderContent();prdGroupSetup();});
await page.locator('.lnv-ri').first().click();
const weights=page.getByLabel('Deposit weight source',{exact:true});
assert.strictEqual(await weights.inputValue(),'entered');
const before=await page.evaluate(()=>JSON.parse(JSON.stringify(cfg.assumptions.deposit_products[0].balance_driver.balance_per_customer_spec)));
await weights.selectOption('active_population');
assert.strictEqual(await page.locator('select[aria-label^="Acquisition band "]').count(),4);
let live=await page.evaluate(()=>JSON.parse(JSON.stringify(cfg.assumptions.deposit_products[0].balance_driver.balance_per_customer_spec)));
assert.deepStrictEqual(live.components.map(c=>c.population_band_id),['b0','b1','b2','b3']);
assert.deepStrictEqual(live.components.map(c=>c.amount_spec),before.components.map(c=>c.amount_spec));
assert.strictEqual(await page.getByLabel('Population weight',{exact:true}).count(),0,'no editable inactive weights');
await page.evaluate(()=>{cfg=JSON.parse(JSON.stringify(cfg));window._prdSel=cfg.assumptions.deposit_products[0];renderContent();prdGroupSetup();});
assert.strictEqual(await page.getByLabel('Deposit weight source',{exact:true}).inputValue(),'active_population','save/reload preserves choice');
await page.getByLabel('Deposit weight source',{exact:true}).selectOption('entered');
const restored=await page.evaluate(()=>cfg.assumptions.deposit_products[0].balance_driver.balance_per_customer_spec.components.map(c=>c.weight_spec));
assert.deepStrictEqual(restored,before.components.map(c=>c.weight_spec),'entered shares retained');
await page.getByLabel('Deposit weight source',{exact:true}).selectOption('active_population');
assert(await page.locator('.deposit-local-amount').evaluate(e=>e.scrollWidth<=e.clientWidth+2),'breakdown fits available width');
await page.screenshot({path:'/workspace/scratch/370303911165/r447-population-deposit.png',fullPage:true});
assert.deepStrictEqual(errors,[]);console.log('PASS r447 live population weights: select, map, preserve amounts, reload and restore entered shares');
}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
