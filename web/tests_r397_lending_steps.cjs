// r397: every lending product shows the same six steps; funded flow's fee view and fee chart sit in Pricing;
// level methods keep every step (read-only where the method decides); charts stay on every step that has one;
// the header names the Add product type; step 06 holds the loan reporting category; deposits get theirs in settings;
// the product-settings band stays on one row with long values wrapping inside their own box.
const {chromium}=require('playwright'),fs=require('fs'),assert=require('assert');
(async()=>{
const html=fs.readFileSync(process.env.CONSOLE_HTML||'web/console_v2.html','utf8').replace(/renderTabs\(\);\nwhoami\(\)\.then[^\n]+/,'');
const browser=await chromium.launch({executablePath:process.env.FOUNDRY_CHROMIUM_PATH,args:['--no-sandbox','--disable-gpu','--single-process','--no-zygote'],headless:true});
try{
const page=await browser.newPage({viewport:{width:1600,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>{errors.push('dialog '+d.message());d.dismiss();});page.setDefaultTimeout(15000);
await page.route('**/*',r=>r.fulfill({status:200,body:'{}',contentType:'application/json'}));await page.goto('http://foundry.test');
await page.setContent(html.replace('<script>','<script>window.V3=true;window.V31=true;</script><script>'));
const config=JSON.parse(fs.readFileSync('foundry/fixtures/universal_template_bank.json','utf8'));
await page.evaluate(c=>{cfg=normalizeCfg(c);refresh=()=>{};scheduleAutosave=()=>{};currentTab='products';window._prdView='product';const L=cfg.assumptions.lending_products;
  Object.assign(L[0],{balance_mode:'funded_flow_level',term_days:60,day_count:360,reserve_share:0,target_retention_share:1,interest_balance_measure:'period_end',funded_flow_driver:{source:'entered',input_stage:'funded_volume',start_period:1,ramp_periods:1,take_up_share:1,flow_path:{unit_kind:'money_flow',period:'month',trajectory:'flat',value:100000}}});
  loanBalanceModeChange(1,'explicit_level');},config);
const open=(fam,i)=>page.evaluate(([fam,i])=>{const key=fam==='lending'?'lending_products':fam==='deposit'?'deposit_products':'obs_exposures';window._prdSel=cfg.assumptions[key][i];window._prdTab='setup';renderContent();prdGroupSetup();},[fam,i]);
const titles=()=>page.evaluate(()=>[...document.querySelectorAll('.lnv-ri .t')].map(x=>x.textContent));
const SIX=['Balance','Structure & timing','Pricing','Credit & allowance','Costs & accounting','Additional settings'];
// 1. Same six steps, same order, for funded flow, roll-forward and a level method; rendering never changes the configuration.
for(const i of [0,1,2]){const before=await page.evaluate(()=>JSON.stringify(cfg));await open('lending',i);
  assert.deepStrictEqual(await titles(),SIX,'lending '+i+' steps');assert.strictEqual(await page.evaluate(()=>JSON.stringify(cfg)),before,'render leaves the configuration unchanged '+i);}
// 2. Funded flow: no separate Fee streams step; Pricing holds the fee view and both charts; adding a fee lands in the same list.
await open('lending',0);
assert.strictEqual(await page.locator('.lnv-pane>section[data-lfx="fees"]').count(),0);
await page.evaluate(()=>lnvGo('lending',0,'price'));
const pr=page.locator('.lnv-pane>section[data-lfx="price"]');
assert(await pr.locator('.lfx-add',{hasText:'+ Fee on funded flow'}).isVisible(),'fee buttons in Pricing');
assert.strictEqual(await pr.locator('.lfx-ro .lnc-rosep').count(),1,'fee chart joins the Pricing results column');
const n0=await page.evaluate(()=>(cfg.assumptions.lending_products[0].fee_streams||[]).length);
await pr.locator('.lfx-add',{hasText:'+ Fee on funded flow'}).click();
assert.strictEqual(await page.evaluate(()=>(cfg.assumptions.lending_products[0].fee_streams||[]).length),n0+1,'stream added to the product list');
assert.strictEqual((await page.locator('.prd-tab[data-tab="streams"] small').innerText()).trim(),String(n0+1),'Fee streams tab counts it');
// 3. Charts: steps 01-05 keep a results column and it shows at 1600px for every kind of product.
for(const i of [0,1,2]){await open('lending',i);
  const ro=await page.evaluate(()=>[...document.querySelectorAll('.lnv-pane>section.lfx-s')].map(s=>!!s.querySelector(':scope>.lfx-b>.lfx-ro')));
  assert.deepStrictEqual(ro.slice(0,5),[true,true,true,true,true],'charts on steps 01-05 for lending '+i+' '+JSON.stringify(ro));
  for(const k of await page.evaluate(()=>[...document.querySelectorAll('.lnv-ri')].map(x=>x.getAttribute('data-k')).slice(0,5))){await page.evaluate(([i,k])=>lnvGo('lending',i,k),[i,k]);
    assert(await page.evaluate(()=>{const r=document.querySelector('.lnv-pane>section.lnv-on>.lfx-b>.lfx-ro');return !!r&&getComputedStyle(r).display!=='none'&&r.offsetHeight>40;}),'chart visible '+i+' '+k);}}
// 4. A level method keeps Structure & timing as a read-only step with the derived-originations chart.
await open('lending',1);await page.evaluate(()=>lnvGo('lending',1,'timing'));
assert(await page.locator('.lnv-pane>section.lnv-on.lnc-ro .lnc-fx').isVisible());assert.strictEqual(await page.locator('.lnv-pane>section.lnv-on aside.lnc-dro').count(),1);
assert(/Entered target balance/.test(await page.locator('.lnv-ri[data-k="balance"] .s').innerText()),'balance summary follows the method');
// 5. Step 06 holds the loan reporting category for roll-forward and level methods; it writes the stored line.
for(const i of [1,2]){await open('lending',i);await page.evaluate(i=>{const k=[...document.querySelectorAll('.lnv-ri')].pop().getAttribute('data-k');lnvGo('lending',i,k);},i);
  const sel=page.locator('.lnv-pane>section.lnv-on select[aria-label="Loan reporting category"]');assert(await sel.isVisible(),'reporting category in step 06 '+i);
  await sel.selectOption('loanCommercial');assert.strictEqual(await page.evaluate(i=>cfg.assumptions.lending_products[i].call_report_line,i),'loanCommercial');}
// 6. Header: type from Add product, inferred for older products, editable in Product settings.
assert.strictEqual(await page.evaluate(()=>lncTypeLine(cfg.assumptions.lending_products[0])),'Flow-based lending · 60-day exposure term · reports in '+await page.evaluate(()=>LINE_LABELS_V31[cfg.assumptions.lending_products[0].call_report_line]));
assert(/^Commercial & Industrial · target-balance lending · reports in Loans: Commercial/.test(await page.evaluate(()=>lncTypeLine(cfg.assumptions.lending_products[1]))),'inferred from the reporting line');
await page.evaluate(()=>{cfg.assumptions.lending_products[2].call_report_line='loanOther';delete cfg.assumptions.lending_products[2].product_type;});
assert(/^Other lending · /.test(await page.evaluate(()=>lncTypeLine(cfg.assumptions.lending_products[2]))));
await open('lending',2);await page.evaluate(()=>lnvSettings('lending',2));
await page.locator('.lnv-drawer select[aria-label="Product type"]').selectOption('ci');
assert.strictEqual(await page.evaluate(()=>cfg.assumptions.lending_products[2].product_type),'ci');
assert(/^Commercial & Industrial · /.test(await page.locator('.prd-band-s').innerText()),'header shows the chosen type');

// 7. Deposits: reporting category in Product settings.
await open('deposit',0);await page.evaluate(()=>{lnvSettings('deposit',0);prdGroupSetup();});
const ds=page.locator('.lnv-drawer select[aria-label="Deposit reporting category"]');assert(await ds.isVisible());await ds.selectOption('depSavings');assert.strictEqual(await page.evaluate(()=>cfg.assumptions.deposit_products[0].call_report_line),'depSavings');
// 8. Band: one row; nothing overlaps at 1440, 1280 and 1100; short values stay on one line.
await page.evaluate(()=>{const p=cfg.assumptions.lending_products[1];loanBalanceModeChange(1,'rollforward');loanContractEnable(1,true);});
for(const width of [1440,1280,1100]){await page.setViewportSize({width,height:1000});await open('lending',1);
  const g=await page.evaluate(()=>{const k=[...document.querySelectorAll('.lnv-ps>*')].filter(e=>e.offsetWidth>0).map(e=>e.getBoundingClientRect());const b=document.querySelector('.lnv-ps').getBoundingClientRect();
    return {rows:new Set(k.map(r=>Math.round(r.top))).size,overlap:k.some((r,j)=>j&&r.left<k[j-1].right-1),inside:k.every(r=>r.right<=b.right+1)||document.querySelector('.lnv-ps').scrollWidth>document.querySelector('.lnv-ps').clientWidth,short:[...document.querySelectorAll('.lnv-ps>.lnv-kv:not(.lnc-long)>b')].every(x=>x.getClientRects().length===1)};});
  assert.deepStrictEqual(g,{rows:1,overlap:false,inside:true,short:true},'band at '+width);}
// 9. Add product records the choice (last: newly added products take the selection).
const added=await page.evaluate(()=>{const L=cfg.assumptions.lending_products,b1=document.createElement('button'),b2=document.createElement('button'),k=TAX31()['Loans'].findIndex(s=>s.name==='Commercial Real Estate');addFlowLoanMulti(b1);addFromTaxonomyMulti('Loans',k,b2);return [b1._added&&b1._added.product_type,b2._added&&b2._added[0]&&b2._added[0].product_type];});
assert.deepStrictEqual(added,['flow','cre'],'Add product records the choice');
assert.deepStrictEqual(errors,[]);
console.log('PASS r397 lending steps: six steps for every method, fee view and charts in Pricing, read-only level steps with derived chart, charts on steps 01-05 at 1600px, reporting category in step 06 and deposit settings, header type from Add product (stored, inferred, editable), one-row band');
}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
