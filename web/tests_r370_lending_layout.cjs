const {chromium}=require('playwright');
const path=require('path'),{execFileSync}=require('child_process');
const fs=require('fs'),assert=require('assert');
(async()=>{
let html=fs.readFileSync('web/console_v2.html','utf8').replace(/renderTabs\(\);\nwhoami\(\)\.then[^\n]+/,'');
const browser=await chromium.launch({executablePath:process.env.FOUNDRY_CHROMIUM_PATH,args:['--no-sandbox','--disable-gpu','--single-process','--no-zygote'],headless:true});
const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
await page.route('**/*',r=>r.fulfill({status:200,body:'{}',contentType:'application/json'}));await page.goto('http://foundry.test');await page.setContent(html.replace('<script>','<script>window.V3=true;window.V31=true;</script><script>'));
await page.evaluate(c=>{cfg=c;refresh=()=>{};scheduleAutosave=()=>{};currentTab='products';window._prdView='product';window._prdSel=cfg.assumptions.lending_products[0];window._prdTab='setup';renderTabs();renderContent();prdGroupSetup();},JSON.parse(execFileSync('python3',['-c','import json;from foundry.v2.tests_r369_lending_contracts import config;print(json.dumps(config()))'],{encoding:'utf8'})));
await page.locator('.loan-contract-panel').first().waitFor();
let checks=[];
for(const state of ['flat','growth','explicit','expanded','monetary','off','legacy']){
 await page.evaluate(state=>{
   const p=cfg.assumptions.lending_products[0],c=p.loan_rollforward;
   if(state==='growth'){
    for(const spec of [c.count_spec,c.loan_size_spec,c.payment_rate_spec,c.prepayment_rate_spec,c.reserve_rate_spec,...Object.values(c.deferred).filter(x=>x&&typeof x==='object')]){spec.trajectory='growth';spec.base=spec.value||0;}
   }
   if(state==='explicit'){
    for(const spec of [c.count_spec,c.loan_size_spec,c.payment_rate_spec,c.prepayment_rate_spec,c.reserve_rate_spec,...Object.values(c.deferred).filter(x=>x&&typeof x==='object')]){spec.trajectory='explicit';spec.cadence='year';spec.values=Array(5).fill(spec.base||0);spec.resolution='step';spec.extend='hold';}
   }
   if(state==='expanded'){
    faSeriesExplicitOpen('assumptions.lending_products.0.loan_rollforward.reserve_rate_spec');
   }
   if(state==='monetary'){c.source='entered_money';c.amount_spec={source:'entered',trajectory:'flat',value:100000};c.deferred.basis='percent_funded';}
   if(state==='off')delete c.deferred;
   if(state==='legacy')delete p.loan_rollforward;
   renderContent();prdGroupSetup();
 },state);
 if(state==='expanded'){
   const summaries=page.locator('.loan-contract-options>summary');for(let j=0;j<await summaries.count();j++)await summaries.nth(j).click();
   await page.evaluate(()=>{renderContent();prdGroupSetup();});
   assert.equal(await page.locator('.loan-contract-options[open]').count(),2,'secondary settings retain expanded state');
 }
 for(const width of [1920,1440,1280,1024,768]){
 await page.setViewportSize({width,height:1100});await page.evaluate(()=>{fitControls();});
 const report=await page.locator('.lfx-gen').evaluate(root=>{
  const visible=e=>e.getClientRects().length&&getComputedStyle(e).visibility!=='hidden',issues=[];
  for(const panel of root.querySelectorAll('.loan-contract-panel')){
   const pr=panel.getBoundingClientRect();
   for(const e of panel.querySelectorAll('input,select,textarea,button,label')){
    if(!visible(e))continue;const r=e.getBoundingClientRect();if(e.matches('.loan-contract-field>label')&&r.height>64)issues.push({reason:'stretched label',text:e.textContent});
    if(r.right>pr.right+2||r.left<pr.left-2)issues.push({text:e.textContent?.slice(0,50),tag:e.tagName,reason:'outside panel',x:r.x,right:r.right,panel:pr.right});
   }
   const controls=[...panel.querySelectorAll('input,select,textarea,button')].filter(visible);
   for(let i=0;i<controls.length;i++)for(let j=i+1;j<controls.length;j++){const a=controls[i].getBoundingClientRect(),b=controls[j].getBoundingClientRect();if(Math.min(a.right,b.right)-Math.max(a.left,b.left)>2&&Math.min(a.bottom,b.bottom)-Math.max(a.top,b.top)>2)issues.push({reason:'overlap',a:controls[i].outerHTML.slice(0,80),b:controls[j].outerHTML.slice(0,80)});}
  }
  return {issues,pageOverflow:document.documentElement.scrollWidth>innerWidth+2,panels:root.querySelectorAll('.loan-contract-panel').length,heights:[...root.querySelectorAll('.loan-contract-panel')].map(e=>Math.round(e.getBoundingClientRect().height))};
 });checks.push({state,width,...report});assert.deepStrictEqual(report.issues,[],state+' '+width);assert(!report.pageOverflow,state+' '+width+' overflow');
 if(width===1440&&process.env.FOUNDRY_LAYOUT_DIR)await page.locator('.lfx-gen').screenshot({path:path.join(process.env.FOUNDRY_LAYOUT_DIR,'r370-'+state+'.png')});
}
}
assert.deepStrictEqual(errors,[]);console.log('PASS '+checks.length+' browser layouts: Flat/Growth/Explicit/expanded/monetary/off/legacy, 1920–768px, contained controls, no overlaps/overflow or runtime errors');
await browser.close();
})().catch(e=>{console.error(e);process.exitCode=1});
