// r448: product navigation resizing is a local display preference.
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

const handle=page.getByRole('separator',{name:'Product sidebar width'});
const width=()=>page.locator('.prd-nav').evaluate(e=>e.getBoundingClientRect().width);
assert.strictEqual(await width(),300);
const box=await handle.boundingBox();await page.mouse.move(box.x+3,box.y+120);await page.mouse.down();await page.mouse.move(box.x+183,box.y+120);await page.mouse.up();
assert(Math.abs(await width()-480)<5,'drag widens list');
assert(!await page.locator('body').evaluate(e=>e.classList.contains('prd-resizing')));
await page.evaluate(()=>renderContent());assert(Math.abs(await width()-480)<5,'survives render');
assert(Number(await page.evaluate(()=>localStorage.getItem('foundry.productSidebarWidth')))>=480);
await handle.focus();await page.keyboard.press('ArrowLeft');assert(Math.abs(await width()-460)<5,'keyboard narrows');
await handle.dblclick();assert.strictEqual(await width(),300,'reset');
await page.setViewportSize({width:900,height:900});assert(!await handle.isVisible(),'stacked layout hides handle');
assert.deepStrictEqual(errors,[]);console.log('PASS r448 product sidebar drag, persistence, keyboard, reset and narrow layout');
}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
