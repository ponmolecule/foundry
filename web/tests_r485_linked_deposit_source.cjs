// r485: Loan production gains the origination source "Linked deposit balance × percentage"; the two
// production/repayment method cards are selectable radios with a visible Selected indicator and keyboard focus.
const {chromium}=require('playwright'),fs=require('fs'),assert=require('assert');
(async()=>{
const html=fs.readFileSync(process.env.CONSOLE_HTML||'web/console_v2.html','utf8').replace(/renderTabs\(\);\nwhoami\(\)\.then[^\n]+/,'');
const browser=await chromium.launch({executablePath:process.env.FOUNDRY_CHROMIUM_PATH,args:['--no-sandbox','--disable-gpu','--single-process','--no-zygote'],headless:true});
try{
const page=await browser.newPage({viewport:{width:1600,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));page.setDefaultTimeout(15000);
await page.route('**/*',r=>r.fulfill({status:200,body:'{}',contentType:'application/json'}));await page.goto('http://foundry.test');
await page.setContent(html.replace('<script>','<script>window.V3=true;window.V31=true;</script><script>'));
const config=JSON.parse(fs.readFileSync('foundry/fixtures/universal_template_bank.json','utf8'));
await page.evaluate(c=>{cfg=normalizeCfg(c);refresh=()=>{};scheduleAutosave=()=>{};currentTab='products';window._prdView='product';},config);
const open=()=>page.evaluate(()=>{window._prdSel=cfg.assumptions.lending_products[2];window._prdTab='setup';renderContent();prdGroupSetup();lnvGo('lending',2,'balance');});
await open();await page.evaluate(()=>lnvSettings('lending',2));   // method cards live in the settings drawer
// 1. Method cards: radio semantics, visible Selected indicator, focus ring, arrows move focus only.
const cards=()=>page.evaluate(()=>[...document.querySelectorAll('.lnv-mc')].map(b=>({role:b.getAttribute('role'),checked:b.getAttribute('aria-checked'),sel:b.querySelector('.sel')?.textContent,tab:b.tabIndex})));
let cs=await cards();
assert.deepStrictEqual(cs.map(c=>[c.role,c.checked,c.sel,c.tab]),[['radio','true','✓ Selected',0],['radio','false','Select',-1]],'legacy selected at start '+JSON.stringify(cs));
assert(await page.evaluate(()=>document.querySelector('.lnv-mg').getAttribute('role')==='radiogroup'),'cards form a radiogroup');
await page.locator('.lnv-mc').nth(0).focus();await page.keyboard.press('ArrowRight');
assert.strictEqual(await page.evaluate(()=>document.activeElement.getAttribute('data-lnv-method')),'contract','arrow moves focus to the other card');
assert(await page.evaluate(()=>!cfg.assumptions.lending_products[2].loan_rollforward),'arrow alone does not switch method');
const ring=await page.evaluate(()=>{const s=getComputedStyle(document.activeElement);return s.outlineStyle+' '+s.outlineWidth;});
assert(/solid 2px/.test(ring),'keyboard focus ring visible: '+ring);
await page.keyboard.press('Enter');
assert(await page.evaluate(()=>!!cfg.assumptions.lending_products[2].loan_rollforward),'Enter selects Loan production');
await page.evaluate(()=>lnvGo('lending',2,'balance'));
cs=await cards();assert.deepStrictEqual(cs.map(c=>[c.checked,c.sel]),[['false','Select'],['true','✓ Selected']],'Selected indicator follows the choice');
const selBg=await page.evaluate(()=>getComputedStyle(document.querySelector('.lnv-mc.on .sel')).backgroundColor);
assert.strictEqual(selBg,'rgb(44, 44, 44)','Selected badge is filled');
// 2. The new origination source, its four controls and the formula.
const srcSel='select[aria-label="Origination source"]';
const opts=await page.evaluate(s=>[...document.querySelector(s).options].map(o=>o.text),srcSel);
assert.deepStrictEqual(opts,['Entered new-loan count','Gross new-customer flow','Entered monetary originations','Linked deposit balance × percentage']);
const countBefore=await page.evaluate(()=>JSON.stringify(cfg.assumptions.lending_products[2].loan_rollforward.count_spec));
await page.selectOption(srcSel,'deposit_balance');
let c=await page.evaluate(()=>cfg.assumptions.lending_products[2].loan_rollforward);
assert.strictEqual(c.source,'deposit_balance');assert.strictEqual(c.balance_measure,'period_end');assert.strictEqual(c.percentage_period,'month');
assert.deepStrictEqual(c.percentage_spec,{source:'entered',trajectory:'flat',value:0});assert.strictEqual(c.deposit_id,'');
const ui=()=>page.evaluate(()=>{const g=document.querySelector('.lnv-on')||document;const t=g.innerText;return {
  deposits:[...g.querySelectorAll('select[aria-label="Linked deposit product"] option')].map(o=>o.text),
  chosen:g.querySelector('select[aria-label="Linked deposit product"]')?.selectedOptions[0]?.text,
  warn:g.querySelector('.loan-linked-warn')?.textContent||'',
  formula:g.querySelector('.loan-linked-formula')?.textContent||'',
  size:/Amount per new loan/.test(t),measure:/Balance observed/.test(t),period:/Percentage period/.test(t),pct:/Percentage of balance · per month/.test(t),
  paths:[...g.querySelectorAll('.lfx-series-mode button,button')].map(b=>b.textContent.trim()).filter(x=>['Flat','Growth','Schedule'].includes(x))};});
let u=await ui();
const names=config.assumptions.deposit_products.map(d=>d.name);
assert.deepStrictEqual(u.deposits,['Select deposit',...names],'every individual deposit offered');
assert(/Select a deposit product/.test(u.warn),'missing deposit flagged');
assert(u.measure&&u.period&&u.pct&&!u.size,'measure, period and percentage shown; loan size hidden');
assert(['Flat','Growth','Schedule'].every(x=>u.paths.includes(x)),'percentage uses the Flat/Growth/Schedule editor '+u.paths);
assert(/ending balance × percentage per month × 12 ÷ 12/.test(u.formula),u.formula);
await page.selectOption('select[aria-label="Linked deposit product"]',{label:'MMDA / Savings'});
c=await page.evaluate(()=>({c:cfg.assumptions.lending_products[2].loan_rollforward,id:cfg.assumptions.deposit_products[1].source_catalog_id}));
assert(c.id&&c.c.deposit_id===c.id,'selection stores the stable ID');
await page.evaluate(()=>{const c=cfg.assumptions.lending_products[2].loan_rollforward;c.balance_measure='period_average';c.percentage_period='quarter';renderContent();prdGroupSetup();lnvGo('lending',2,'balance');});
u=await ui();assert(/average balance × percentage per quarter × 4 ÷ 12/.test(u.formula),u.formula);assert(/per quarter/.test(await page.evaluate(()=>document.querySelector('.lnv-on').innerText)));
// 3. Stable ID survives rename and reordering; retention-pool members are not offered.
await page.evaluate(()=>{const d=cfg.assumptions.deposit_products;d[1].name='MMDA (renamed)';d.push(d.splice(1,1)[0]);d[0].balance_mode='pool';d[0].retention_pool_id='pool-a';renderContent();prdGroupSetup();lnvGo('lending',2,'balance');});
u=await ui();assert.strictEqual(u.chosen,'MMDA (renamed)','selection follows the stable ID');assert.strictEqual(u.warn,'');
assert(!u.deposits.includes(names[0]),'retention-pool member not offered');
await page.evaluate(()=>{cfg.assumptions.deposit_products.find(d=>d.name==='MMDA (renamed)').source_catalog_id='other';renderContent();prdGroupSetup();lnvGo('lending',2,'balance');});
u=await ui();assert(/no longer exists/.test(u.warn),'stale ID flagged, not substituted');assert.strictEqual(u.chosen,'Select deposit');
// 4. Switching source is non-destructive.
await page.selectOption(srcSel,'entered_count');
c=await page.evaluate(()=>cfg.assumptions.lending_products[2].loan_rollforward);
assert.strictEqual(JSON.stringify(c.count_spec),countBefore,'count inputs kept');assert.strictEqual(c.percentage_period,'quarter','linked inputs kept');
assert(await page.evaluate(()=>/Amount per new loan/.test(document.querySelector('.lnv-on').innerText)),'loan size returns');
assert.deepStrictEqual(errors,[]);
console.log('PASS r485 linked deposit source: radio method cards with Selected badge and focus ring, four controls, live formula, stable ID across rename/reorder, pool members excluded, stale ID flagged, non-destructive source switch');
}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
// r485 (2): deleting the linked deposit names the loan that depends on it.
(async()=>{
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const H=fs.readFileSync(__dirname+'/console_v2.html','utf8');
const dep={name:'Portfolio Partnerships',source_catalog_id:'product-source-pp'},loan={name:'Partner loans',loan_rollforward:{source:'deposit_balance',deposit_id:'product-source-pp'}};
const ctx={cfg:{assumptions:{deposit_products:[dep,{name:'Other',source_catalog_id:'product-source-o'}],lending_products:[loan]}}};vm.createContext(ctx);
vm.runInContext(H.slice(H.indexOf('function feeDeletionConsumers('),H.indexOf('function feeConfirmDeletion(')),ctx);
assert.strictEqual(JSON.stringify(ctx.feeDeletionConsumers(dep,[dep])),JSON.stringify(['Lending / Partner loans / loan rollforward']));
assert.strictEqual(ctx.feeDeletionConsumers(ctx.cfg.assumptions.deposit_products[1],[ctx.cfg.assumptions.deposit_products[1]]).length,0);
console.log('PASS r485 deleting a linked deposit names the dependent loan');
})().catch(e=>{console.error(e);process.exit(1)});
