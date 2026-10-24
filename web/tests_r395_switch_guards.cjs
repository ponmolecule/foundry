// r395: leaving Loan roll-forward with Loan production on asks first, removes the inputs the engine would reject,
// restores them on the way back; a saved product already in that state says so and offers the fix.
// The fee-product AUC ramp is labelled in the model's own period, as the engine counts it.
const {chromium}=require('playwright'),fs=require('fs'),assert=require('assert');
(async()=>{
const html=fs.readFileSync(process.env.CONSOLE_HTML||'web/console_v2.html','utf8').replace(/renderTabs\(\);\nwhoami\(\)\.then[^\n]+/,'');
const browser=await chromium.launch({executablePath:process.env.FOUNDRY_CHROMIUM_PATH,args:['--no-sandbox','--disable-gpu','--single-process','--no-zygote'],headless:true});
try{
const page=await browser.newPage({viewport:{width:1600,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>{errors.push('dialog '+d.message());d.dismiss();});page.setDefaultTimeout(15000);
await page.route('**/*',r=>r.fulfill({status:200,body:'{}',contentType:'application/json'}));await page.goto('http://foundry.test');
await page.setContent(html.replace('<script>','<script>window.V3=true;window.V31=true;</script><script>'));
const config=JSON.parse(fs.readFileSync('foundry/fixtures/universal_template_bank.json','utf8'));
await page.evaluate(c=>{cfg=normalizeCfg(c);refresh=()=>{};scheduleAutosave=()=>{};currentTab='products';window._prdView='product';},config);
const open=(fam,i)=>page.evaluate(([fam,i])=>{const key=fam==='lending'?'lending_products':fam==='deposit'?'deposit_products':'obs_exposures';window._prdSel=cfg.assumptions[key][i];window._prdTab='setup';renderContent();prdGroupSetup();},[fam,i]);
const I=2,P=()=>page.evaluate(i=>{const p=cfg.assumptions.lending_products[i];return {mode:p.balance_mode||'rollforward',lr:p.loan_rollforward?JSON.stringify(p.loan_rollforward):null};},I);
// 1. Loan production on, then choose a level method: nothing changes until you answer.
await open('lending',I);await page.evaluate(i=>{loanContractEnable(i,true);const c=cfg.assumptions.lending_products[i].loan_rollforward;c.payment_rate_spec.value=0.02;prdGroupSetup();},I);
const saved=(await P()).lr;assert(saved,'loan production on');
await page.evaluate(i=>loanBalanceModeChange(i,'explicit_level'),I);
assert.deepStrictEqual(await P(),{mode:'rollforward',lr:saved},'first choice only asks');
assert(await page.locator('.lbm-note.ask').isVisible(),'the question is visible (settings drawer open)');
assert(/Entered target balance/.test(await page.locator('.lbm-note.ask').innerText()));
await page.locator('.lbm-note.ask .lbm-btn',{hasText:'Keep Loan roll-forward'}).click();
assert.deepStrictEqual(await P(),{mode:'rollforward',lr:saved},'keep leaves the product unchanged');assert.strictEqual(await page.locator('.lbm-note.ask').count(),0);
// 2. Confirm: the method changes and the production inputs leave the product.
await page.evaluate(i=>loanBalanceModeChange(i,'explicit_level'),I);await page.locator('.lbm-note.ask .lbm-btn.dk').click();
assert.deepStrictEqual(await P(),{mode:'explicit_level',lr:null},'switch removes loan production');
assert(/Switch back to Loan roll-forward/.test(await page.locator('.lending-balance-authoring').first().innerText()));
// 3. Switching back in the same session restores the same inputs.
await page.evaluate(i=>loanBalanceModeChange(i,'rollforward'),I);
assert.deepStrictEqual(await P(),{mode:'rollforward',lr:saved},'switching back restores loan production');
// 4. Without loan production, the switch is immediate (no question).
await page.evaluate(i=>{loanContractEnable(i,false);loanBalanceModeChange(i,'funded_flow_level');},I);assert.strictEqual((await P()).mode,'funded_flow_level');
await page.evaluate(i=>{loanBalanceModeChange(i,'rollforward');},I);
// 5. A product saved in the rejected state says so and offers the fix.
await page.evaluate(([i,lr])=>{const p=cfg.assumptions.lending_products[i];p.balance_mode='explicit_level';p.ending_balance_spec={source:'entered',trajectory:'flat',value:0};p.loan_rollforward=JSON.parse(lr);},[I,saved]);
await open('lending',I);assert(await page.locator('.lbm-note.bad').isVisible(),'stale state is flagged with the drawer open');
await page.locator('.lbm-note.bad .lbm-btn').click();assert.strictEqual((await P()).lr,null);assert.strictEqual(await page.locator('.lbm-note.bad').count(),0);
// 6. AUC ramp label follows the model period.
const k=await page.evaluate(()=>cfg.assumptions.obs_exposures.findIndex(p=>p.managed_notional));
if(k>=0){await page.evaluate(k=>{const p=cfg.assumptions.obs_exposures[k];p.managed_notional_source=null;p.managed_notional.trajectory='ramp_to_target';},k);await open('obs',k);
  const per=await page.evaluate(()=>PLAB('full')+'s');
  const got=await page.evaluate(()=>{const inp=document.querySelector('.prd-card input[data-focus$="managed_notional.ramp_periods"]');if(!inp)return null;const f=inp.closest('.fld');return {label:f.querySelector('label').textContent.trim(),unit:(f.querySelector('.lfx-in>i')||{}).textContent||''};});
  assert(got,'ramp field present');assert.strictEqual(got.label+' ('+(got.unit||per)+')','Ramp to target ('+per+')','ramp unit follows the model period: '+JSON.stringify(got));}
assert.deepStrictEqual(errors,[]);
console.log('PASS r395: loan production asks before leaving Loan roll-forward, removes and restores its inputs, flags saved products the engine would reject; AUC ramp labelled in model periods');
}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
