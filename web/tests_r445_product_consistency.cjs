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

await page.evaluate(()=>{loanContractEnable(0,true);window._prdView='product';});
const SIX=['Balance','Structure & timing','Pricing','Credit & allowance','Costs & accounting','Additional settings'];
const fams={lending:'lending_products',deposit:'deposit_products',obs:'obs_exposures'};
// First render assigns existing stable source IDs; the second pass must preserve all assumptions.
async function pass(check){
 for(const [fam,key] of Object.entries(fams)){
  const n=await page.evaluate(k=>cfg.assumptions[k].length,key);
  for(let i=0;i<n;i++){
   await page.evaluate(([key,i])=>{window._prdSel=cfg.assumptions[key][i];window._prdView='product';window._prdTab='setup';renderContent();prdGroupSetup();},[key,i]);
   if(fam==='lending')assert.deepStrictEqual(await page.locator('.lnv-ri .t').allTextContents(),SIX);
   const ns=await page.locator('.lnv-ri').count();
   for(let j=0;j<ns;j++){
    await page.locator('.lnv-ri').nth(j).click();await page.waitForTimeout(30);
    if(check){const labs=await page.locator('section.lnv-on .fxs-pane .lfx-grid>.fld>label:visible').evaluateAll(es=>es.map(e=>({align:getComputedStyle(e).textAlign,x:e.getBoundingClientRect().right})));
     assert(labs.every(e=>e.align==='right'),'shared label alignment '+fam+'/'+i+'/'+j+JSON.stringify(labs));}
   }
  }
 }
}
await pass(false);const before=await page.evaluate(()=>JSON.stringify(cfg));await pass(true);
assert.strictEqual(await page.evaluate(()=>JSON.stringify(cfg)),before,'render preserves all assumptions');
for(const width of [2048,1440,1100]){
 await page.setViewportSize({width,height:1100});
 await page.evaluate(()=>{window._prdSel=cfg.assumptions.lending_products.find(p=>p.repayment_profile);window._prdTab='setup';renderContent();});
 await page.locator('.lnv-ri').nth(0).click();await page.waitForTimeout(60);
 const native=page.locator('section.lnv-on .lfx-grid>.lfx-f:has(>label)');
 assert(await native.count()>0);
 assert(await native.evaluateAll(es=>es.every(e=>e.classList.contains('fld'))),'native fields use shared geometry');
 await page.locator('.lnv-ri').nth(2).click();await page.waitForTimeout(60);
 assert(await page.locator('section.lnv-on').getByText('Interest accrues on',{exact:true}).isVisible());
 const body=page.locator('section.lnv-on .fxs-pane');
 await body.screenshot({path:require('path').join(require('os').tmpdir(),'r445-pricing-')+width+'.png'});
}
// The inspector receives the now-published engine provision, rather than manufacturing a client series.
const series=await page.evaluate(()=>{const p=lastRes.products.find(p=>p.family==='lending'&&p.balanceMode==='funded_flow_level');return _resultPanelSeries(p,'cred','Allowance','lending');});
assert.strictEqual(series.find(s=>s.name==='Funded provision / (release)').values.length,36);
await page.locator('.lnv-ri').nth(3).click();await page.locator('section.lnv-on .result-numbers-link').click();
assert(await page.locator('#result-numbers-dialog').locator('tbody th').filter({hasText:'Funded provision / (release)'}).isVisible(),'provision available in the actual Numbers dialog');
assert.deepStrictEqual(errors,[]);console.log('r445 product consistency: ok');
}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
