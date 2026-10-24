// r392: every product family edits through a section rail with one focused section, a product-settings band,
// advanced-setting badges read from the stored product, and method names that describe the modeling approach.
const {chromium}=require('playwright'),fs=require('fs'),assert=require('assert');
(async()=>{
const html=fs.readFileSync(process.env.CONSOLE_HTML||'web/console_v2.html','utf8').replace(/renderTabs\(\);\nwhoami\(\)\.then[^\n]+/,'');
const browser=await chromium.launch({executablePath:process.env.FOUNDRY_CHROMIUM_PATH,args:['--no-sandbox','--disable-gpu','--single-process','--no-zygote'],headless:true});
try{
const page=await browser.newPage({viewport:{width:1600,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));page.setDefaultTimeout(15000);
await page.route('**/*',r=>r.fulfill({status:200,body:'{}',contentType:'application/json'}));await page.goto('http://foundry.test');
await page.setContent(html.replace('<script>','<script>window.V3=true;window.V31=true;</script><script>'));
const config=JSON.parse(fs.readFileSync('foundry/fixtures/universal_template_bank.json','utf8'));
const open=async(fam,i)=>page.evaluate(([fam,i])=>{const key=fam==='lending'?'lending_products':fam==='deposit'?'deposit_products':'obs_exposures';window._prdSel=cfg.assumptions[key][i];window._prdTab='setup';renderContent();prdGroupSetup();},[fam,i]);
await page.evaluate(c=>{cfg=normalizeCfg(c);refresh=()=>{};scheduleAutosave=()=>{};currentTab='products';window._prdView='product';},config);
const state=()=>page.evaluate(()=>{const r=document.querySelector('.prd-card .lfx.lnv');if(!r)return null;const vis=[...r.querySelectorAll('.lnv-pane>section.lfx-s')].filter(s=>getComputedStyle(s).display!=='none');
  return {rail:[...r.querySelectorAll('.lnv-ri')].map(x=>x.getAttribute('data-k')),on:r.querySelector('.lnv-ri.on')?.getAttribute('data-k'),visible:vis.map(s=>s.getAttribute('data-lfx')),band:r.querySelector('.lnv-ps')?.innerText||'',drawerHidden:r.querySelector('.lnv-drawer')?.hidden,minH:parseFloat(r.querySelector('.lnv-ws').style.minHeight)||0,wsH:r.querySelector('.lnv-ws').offsetHeight,strayVisible:[...document.querySelectorAll('.prd-card .pp-sec>.fld')].filter(e=>e.offsetParent&&/Balance authoring|Starting balance|Measurement/.test(e.textContent)).length};});
// 1. Every family gets the rail; one section shows at a time.
for(const [fam,i,min] of [['lending',2,5],['deposit',0,4],['obs',0,3],['obs',1,1]]){
  await open(fam,i);const s=await state();assert(s,fam+' '+i+' has the rail layout');
  assert(s.rail.length>=min,fam+' rail lists its sections '+JSON.stringify(s.rail));assert.deepStrictEqual(s.visible,[s.on],fam+' shows exactly the active section');
  assert(/PRODUCT SETTINGS/.test(s.band),fam+' product settings band');assert.strictEqual(s.drawerHidden,true,fam+' settings drawer starts closed');
}
// 2. Rail navigation does not re-render the card and keeps one section visible; the workspace keeps its height.
await open('lending',2);
const before=await state();
await page.evaluate(()=>{window._card=document.querySelector('.prd-card .lfx');});
for(const k of before.rail){await page.locator(`.lnv-ri[data-k="${k}"]`).click();const s=await state();assert.deepStrictEqual(s.visible,[k],'rail shows '+k);assert(s.wsH>=before.minH-1,'workspace keeps its height on '+k);}
assert(await page.evaluate(()=>window._card===document.querySelector('.prd-card .lfx')),'switching sections keeps the mounted editor');
await page.locator('.lnv-ri[data-k="balance"]').click();await page.keyboard.press('ArrowDown');assert.strictEqual((await state()).on,before.rail[1],'arrow keys move between sections');
await page.evaluate(()=>lnvStep(1));assert.strictEqual((await state()).on,before.rail[2],'next moves forward');
// 3. Duplicate mode fields are out of view; the settings drawer holds the product name and balance authoring.
assert.strictEqual(before.strayVisible,0,'duplicate balance authoring fields are hidden');
await page.locator('.lnv-ps .lnv-btn').click();
assert(await page.evaluate(()=>{const d=document.querySelector('.lnv-drawer');return !d.hidden&&!!d.querySelector('input[onchange*="renameProduct"]')&&!!d.querySelector('select[onchange*="loanBalanceModeChange"]');}),'drawer holds name and balance authoring');
// 4. Method cards: production on; switching back asks first and only then removes the production inputs.
const labels=await page.evaluate(()=>[...document.querySelectorAll('.lnv-mc .t')].map(e=>e.textContent));
assert.deepStrictEqual(labels,['Dollar originations · single runoff rate','Loan production · separate payment and prepayment rates']);
await page.locator('.lnv-mc').nth(1).click();
assert(await page.evaluate(()=>!!cfg.assumptions.lending_products[2].loan_rollforward),'production method enabled');
await page.evaluate(()=>{const c=cfg.assumptions.lending_products[2].loan_rollforward;c.provision_release_policy='floor_zero';c.opening_allowance=160000;loanContractDeferred(2,true);});
await page.evaluate(()=>{renderContent();prdGroupSetup();});
const badges=await page.evaluate(()=>Object.fromEntries([...document.querySelectorAll('.lnv-ri')].map(x=>[x.getAttribute('data-k'),x.querySelector('.bd')?.textContent||''])));
assert.strictEqual(badges.credit,'2 advanced','credit shows two active advanced settings');assert.strictEqual(badges.costs,'1 advanced','deferred fees badge');
await page.evaluate(()=>lnvGo('lending',2,'credit'));
const chips=await page.evaluate(()=>[...document.querySelectorAll('.lnv-on .lnv-adv .lnv-chip')].map(e=>e.textContent));
assert.deepStrictEqual(chips,['Provision floored at zero','Opening allowance 160'],'chips name the active settings');
await page.locator('.lnv-mc').nth(0).click();
assert(await page.evaluate(()=>!!cfg.assumptions.lending_products[2].loan_rollforward),'first click only asks');
assert(await page.locator('.lnv-confirm').isVisible(),'confirmation shown');
await page.locator('.lnv-confirm .lnv-btn').first().click();
assert(await page.evaluate(()=>!!cfg.assumptions.lending_products[2].loan_rollforward),'cancel keeps the inputs');
await page.locator('.lnv-mc').nth(0).click();await page.locator('.lnv-confirm .lnv-btn.dk').click();
assert(await page.evaluate(()=>!cfg.assumptions.lending_products[2].loan_rollforward),'confirmed switch uses the existing handler');
// 5. An unset choice is flagged in the rail.
await page.evaluate(()=>{const p=cfg.assumptions.lending_products[2];delete p.structure;renderContent();prdGroupSetup();});
assert(await page.evaluate(()=>{const it=document.querySelector('.lnv-ri[data-k="timing"]');return !!it.querySelector('.wd')&&/Not chosen yet/.test(it.textContent);}),'unset structure is flagged');
// 6. Funded-flow lending uses the same rail.
await page.evaluate(()=>{const p=cfg.assumptions.lending_products[0];Object.assign(p,{balance_mode:'funded_flow_level',term_days:60,day_count:360,reserve_share:0,target_retention_share:1,interest_balance_measure:'period_end',funded_flow_driver:{source:'entered',input_stage:'funded_volume',start_period:1,ramp_periods:1,take_up_share:1,flow_path:{unit_kind:'money_flow',period:'month',trajectory:'flat',value:100000}}});});
await open('lending',0);const f=await state();assert(f&&f.rail.includes('vol')&&f.visible.length===1,'funded flow rail');
assert.deepStrictEqual(errors,[]);
console.log('PASS r392 product rail: every family, one section at a time, stable height, keyboard, settings drawer, method cards with confirmation, advanced badges and chips from stored settings, unset-choice flag, funded flow');
}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
