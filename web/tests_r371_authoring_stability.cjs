const {chromium}=require('playwright'),fs=require('fs'),assert=require('assert'),{execFileSync}=require('child_process');
(async()=>{
const html=fs.readFileSync(process.env.CONSOLE_HTML||'web/console_v2.html','utf8').replace('renderTabs();\nwhoami().then(u=>{ paintWho(); if(u){ boot(); } else { currentTab = "welcome"; renderContent(); } });','');
const browser=await chromium.launch({executablePath:process.env.FOUNDRY_CHROMIUM_PATH,args:['--no-sandbox','--disable-gpu','--single-process','--no-zygote'],headless:true});
try{
const page=await browser.newPage({viewport:{width:1440,height:900}}),errors=[];page.on('pageerror',e=>errors.push(e.message));await page.route('**/*',r=>r.fulfill({status:200,body:'{}',contentType:'application/json'}));await page.goto('http://foundry.test');await page.setContent(html.replace('<script>','<script>window.V3=true;window.V31=true;</script><script>'));
const config=JSON.parse(execFileSync('python3',['-c','import json;from foundry.v2.tests_r369_lending_contracts import config;print(json.dumps(config()))'],{encoding:'utf8'}));
await page.evaluate(c=>{cfg=c;refresh=()=>{};scheduleAutosave=()=>{};currentTab='products';window._prdView='product';window._prdSel=cfg.assumptions.lending_products[0];window._prdTab='setup';renderTabs();renderContent();prdGroupSetup();},config);
for(const width of [1440,768]){
 await page.setViewportSize({width,height:900});await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
 const stability=await page.evaluate(async()=>{
  _authoringClickTarget=null;
  const target=document.querySelector('[data-loan-contract-group="costs"]');window.scrollTo(0,target.getBoundingClientRect().top+scrollY-180);
  const before=target.getBoundingClientRect().top,snapshot=JSON.stringify(cfg);renderContent();const frames=[];
  for(let i=0;i<4;i++){await new Promise(requestAnimationFrame);frames.push(document.querySelector('[data-loan-contract-group="costs"]').getBoundingClientRect().top-before);}
  return {frames,unchanged:JSON.stringify(cfg)===snapshot};
 });assert(stability.frames.every(x=>Math.abs(x)<2),width+' rerender moved editor: '+JSON.stringify(stability));assert(stability.unchanged);
 const header=page.locator('.lfx-gen [data-lfx="credit"]>button.lfx-h');await header.scrollIntoViewIfNeeded();
 await page.evaluate(()=>{window._stableCard=document.querySelector('.lfx-gen');window._stableInput=document.querySelector('[data-loan-contract-group="costs"] input');});
 await header.click();await header.click();assert(await page.evaluate(()=>window._stableCard===document.querySelector('.lfx-gen')&&window._stableInput===document.querySelector('[data-loan-contract-group="costs"] input')),'standard section toggle replaced inputs');
}
// Authoring a schedule changes the active rate path without losing the edited control's position.
await page.setViewportSize({width:1440,height:900});const trajectory=page.locator('[data-loan-contract-group="timing"] select').first();await trajectory.scrollIntoViewIfNeeded();const y=await trajectory.evaluate(e=>e.getBoundingClientRect().top);await trajectory.selectOption('growth');await page.evaluate(()=>new Promise(requestAnimationFrame));assert(Math.abs(await page.locator('[data-loan-contract-group="timing"] select').first().evaluate(e=>e.getBoundingClientRect().top)-y)<2,'trajectory edit jumped');
// Funded-flow sections retain mounted bodies and unsaved DOM input buffers.
await page.evaluate(()=>{const p=cfg.assumptions.lending_products[0];delete p.loan_rollforward;Object.assign(p,{balance_mode:'funded_flow_level',structure:'revolving',mortgage_banking:null,term_days:60,day_count:360,reserve_share:0,target_retention_share:1,interest_balance_measure:'period_average',funded_flow_driver:{source:'entered',input_stage:'funded_volume',start_period:1,ramp_periods:1,take_up_share:1,flow_path:{unit_kind:'money_flow',period:'month',trajectory:'flat',value:100000}}});renderContent();prdGroupSetup();window._fundedRoot=document.querySelector('.lfx:not(.lfx-gen)');window._fundedInput=document.querySelector('[data-lfx="acct"] input');});
const funded=page.locator('.lfx:not(.lfx-gen) [data-lfx="acct"]>button.lfx-h');await funded.click();await funded.click();assert(await page.evaluate(()=>window._fundedRoot===document.querySelector('.lfx:not(.lfx-gen)')&&!!window._fundedInput&&window._fundedInput===document.querySelector('[data-lfx="acct"] input')),'funded section remounted');
assert.deepStrictEqual(errors,[]);console.log('PASS 1440/768px settled-frame scroll stability, mounted standard/funded section inputs, anchored trajectory edit, unchanged config, no browser errors');
}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
