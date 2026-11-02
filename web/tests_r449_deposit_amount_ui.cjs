// r449: Balance per customer on the field system (segmented method and weight source, balance share field,
// full-width Amount per customer table) and a Type column in the fee-stream table. Presentation only.
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
s=p['balance_driver']['balance_per_customer_spec']
print(json.dumps({'cfg':c,'result':r}))`],{encoding:'utf8',maxBuffer:1<<28}));
const html=fs.readFileSync('web/console_v2.html','utf8').replace('<script src="/web/rates_workspace.js"></script>','<script>'+fs.readFileSync('web/rates_workspace.js','utf8')+'</script>').replace('<head>','<head><script>window.V3=true;window.V31=true;</script>').replace(/renderTabs\(\);\nwhoami\(\)\.then[^\n]+/,'');
const browser=await chromium.launch({executablePath:process.env.FOUNDRY_CHROMIUM_PATH,args:['--no-sandbox','--disable-gpu','--single-process','--no-zygote'],headless:true});
try{
const page=await browser.newPage({viewport:{width:1440,height:1100}}),errors=[];page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>d.dismiss());page.setDefaultTimeout(15000);
await page.route('**/*',r=>r.fulfill({status:200,json:{}}));await page.goto('http://foundry.test');await page.setContent(html);
await page.evaluate(f=>{cfg=normalizeCfg(f.cfg);lastRes=f.result;refresh=()=>{};scheduleAutosave=()=>{};renderTabs();setTab('products');},fx);
const open=()=>page.evaluate(()=>{window._prdSel=cfg.assumptions.deposit_products[0];window._prdView='product';window._prdTab='setup';renderContent();prdGroupSetup();});
await open();await page.locator('.lnv-ri').first().click();
const spec=()=>page.evaluate(()=>JSON.parse(JSON.stringify(cfg.assumptions.deposit_products[0].balance_driver)));
// 1. Method and weight source are segmented fields; the stored values drive the highlight.
const method=page.getByRole('group',{name:'Balance per customer',exact:true}),ws=page.getByRole('group',{name:'Weight source',exact:true});
assert.strictEqual(await method.locator('button.on').innerText(),'Weighted breakdown');
assert.strictEqual(await ws.locator('button.on').innerText(),'Acquisition population');
// 2. The table spans the section (outside the narrow field column) and reconciles with the engine.
const card=page.locator('.dep-apc');assert.strictEqual(await card.count(),1);
assert(await card.evaluate(e=>e.parentElement.classList.contains('lfx-b')),'table spans the section under the fields and results');
assert.strictEqual(await page.locator('.dep-apc-t tbody>tr:not(.fcb-tot):not(.fcb-edr)').count(),4);
assert.strictEqual(await page.locator('.dep-apc .dep-ro small').count(),4,'live shares are read-only');
const strip=await page.evaluate(()=>{const C=_lfgCtx('deposit',0),o=C.P.depositCustomerCalculation;return o.endingBalanceDollars[C.ref-1]/1000;});
await page.locator('.dep-apc .fcb-explain>summary').click();
const chain=await page.locator('.dep-chain div b').allInnerTexts();
assert.strictEqual(chain[3],Math.round(strip).toLocaleString('en-US'),'explain chain equals the engine balance: '+chain.join(' / '));
const eff=Number((await page.locator('.dep-apc .fcb-tot td:nth-child(5) b').innerText()).replace(/,/g,''));
assert(Math.abs(eff-Number(chain[1].replace(/,/g,'')))<0.011,'weighted total equals the resolved amount per customer');
// 3. Entered shares: editable, totals checked, path tag opens the series editor.
await ws.getByRole('button',{name:'Entered shares',exact:true}).click();
assert.strictEqual((await spec()).balance_per_customer_spec.weight_source,undefined);
assert.strictEqual(await page.getByLabel('Population weight',{exact:true}).count(),4);
await page.getByRole('button',{name:'Edit Amount ($000s per customer) path 2',exact:true}).click();
assert.strictEqual(await page.locator('.dep-apc .deposit-path-panel').count(),1);await page.locator('.dep-apc .fcb-close').click();
assert.strictEqual(await page.locator('.dep-apc .deposit-path-panel').count(),0);
// 3b. Precision: focus shows the full stored value; an unchanged edit (a stray space) never writes back a rounded value.
await page.evaluate(()=>{const c=cfg.assumptions.deposit_products[0].balance_driver;c.balance_per_customer_spec.components[0].amount_spec.value=404711.92264;c.balance_per_customer_spec.components[0].weight_spec.value=.735414627;c.balance_share_spec.value=.7123456789;renderContent();});
const before3=await spec();
for(const lab of ['Amount ($000s per customer)','Population weight','Share of calculated balance (%)']){const el=page.getByLabel(lab,{exact:true}).first();
 const shown=await el.inputValue();await el.focus();const full=await el.inputValue();assert(full.length>shown.length,lab+' focus shows full precision: '+shown+' → '+full);
 await el.press('End');await el.press(' ');await el.press('Tab');await page.waitForTimeout(30);
 assert.deepStrictEqual(await spec(),before3,lab+': unchanged value is not rounded on save');}
assert.strictEqual((await spec()).balance_per_customer_spec.components[0].amount_spec.value,404711.92264);
const amt=page.getByLabel('Amount ($000s per customer)',{exact:true}).first();await amt.fill('404.71192265');await amt.press('Tab');await page.waitForTimeout(30);
assert(Math.abs((await spec()).balance_per_customer_spec.components[0].amount_spec.value-404711.92265)<1e-6,'a real edit still saves');
// 4. Balance share is a field; Use full balance and + Apply a balance share round-trip.
const share=page.getByLabel('Share of calculated balance (%)',{exact:true});assert.strictEqual(await share.inputValue(),'71.23');
await page.getByRole('button',{name:'Use full balance',exact:true}).click();assert.strictEqual((await spec()).balance_share_spec,undefined);
await page.getByRole('button',{name:'+ Apply a balance share',exact:true}).click();assert.strictEqual((await spec()).balance_share_spec.value,1);
// 5. No band composition: Acquisition population is offered but disabled.
await page.evaluate(()=>{Object.values(cfg.assumptions.cac_feeds).forEach(f=>delete f.population_composition);renderContent();});
assert(await page.getByRole('group',{name:'Weight source',exact:true}).getByRole('button',{name:'Acquisition population',exact:true}).isDisabled());
// 6. Containment at three widths.
for(const width of [1440,1024,768]){await page.setViewportSize({width,height:1100});await page.waitForTimeout(80);
 const over=await page.evaluate(()=>[...document.querySelectorAll('.dep-apc, .dep-share-fld, .st-list')].filter(e=>e.scrollWidth>e.clientWidth+2).map(e=>e.className));
 assert.deepStrictEqual(over,[],'no overflow at '+width);}
// 7. Streams table: Type column from each stream's basis; source rows blank.
await page.setViewportSize({width:1440,height:1100});
const exp=await page.evaluate(()=>{const e=cfg.assumptions.obs_exposures.find(x=>(x.fee_streams||[]).length>=5);window._prdSel=e;window._prdView='product';window._prdTab='streams';window._stSelObj=e.fee_streams[0];renderContent();return e.fee_streams.map(s=>({balance:'Balance',transaction:'Transaction',account:'Account',flat:'Flat',event:'Event'})[s.basis]);});
const L=page.locator('.st-list').first();
assert.deepStrictEqual(await L.locator('thead th').allInnerTexts().then(a=>a.slice(0,4).map(x=>x.trim().toLowerCase())),['#','stream','type','role']);
assert.deepStrictEqual(await L.locator('tr.fee-stream-row td.st-ty').allInnerTexts().then(a=>a.map(x=>x.trim())),exp);
assert((await L.locator('tr.st-src td.st-ty').allInnerTexts()).every(x=>!x.trim()),'source rows have no type');
assert(await L.evaluate(e=>e.scrollWidth<=e.clientWidth+2),'stream table fits');
assert.deepStrictEqual(errors,[]);
console.log('r449 deposit amount UI and stream types: ok');
}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
