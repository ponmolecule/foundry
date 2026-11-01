// r434: the field system on product setup steps (lending, deposits, off-balance-sheet) and the customer-acquisition
// channel editor and feed settings: one right-aligned label column, fields sized to content, path as segmented buttons
// driving the existing selects, captions lifted (not duplicated), narrow steps stack, and rendering leaves the config alone.
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
await page.evaluate(f=>{cfg=normalizeCfg(f.cfg);lastRes=f.result;window._runs=0;refresh=()=>{window._runs++;};scheduleAutosave=()=>{};document.body.classList.add('insp-closed');renderTabs();setTab('products');},fx);


await page.evaluate(()=>{window._prdSel=cfg.assumptions.lending_products.find(p=>p.repayment_profile);window._prdView='product';window._prdTab='setup';renderContent();prdGroupSetup();});
const baseline=await page.evaluate(()=>JSON.stringify(cfg));
for(const width of [2048,1440,1100]){
 await page.setViewportSize({width,height:1100});
 for(const step of [0,1,2,3]){
  await page.locator('.lnv-ri').nth(step).click();await page.waitForTimeout(80);
  const gaps=await page.locator('section.lnv-on .fxs-pane .lfx-grid>.lfx-f').evaluateAll(es=>es.filter(e=>e.nextElementSibling&&getComputedStyle(e).display!=='none').map(e=>parseFloat(getComputedStyle(e).marginBottom)));
  assert(gaps.length&&gaps.every(g=>g>=12),'spacing between native fields '+width+'/'+step+': '+gaps);
  if(step===1){
   const labs=page.locator('section.lnv-on .loan-profile-field>label');
   const pos=await labs.evaluateAll(es=>es.map(e=>({x:e.getBoundingClientRect().x,align:getComputedStyle(e).textAlign})));
   assert(pos.length===4&&pos.every(p=>p.align==='left'),'all profile labels align left '+JSON.stringify(pos));
   assert(Math.max(...pos.map(p=>p.x))-Math.min(...pos.map(p=>p.x))<2,'one profile label edge');
   const panel=page.locator('section.lnv-on .loan-profile-panel');
   assert(await panel.evaluate(e=>e.scrollWidth<=e.clientWidth+1),'profile panel contains its controls at '+width);
   await panel.screenshot({path:'/workspace/scratch/370303911165/r443-profile-'+width+'.png'});
  }
 }
}
assert.strictEqual(await page.evaluate(()=>JSON.stringify(cfg)),baseline,'layout does not mutate assumptions');
assert.deepStrictEqual(errors,[]);console.log('r443 product spacing: ok');
}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
