// r440: GPT review of r433–r439. Clear also clears a grid's paste draft; a blank schedule cell is rejected visibly and
// the stored value stays and shows again; segmented Step/Smooth follows the stored choice without a full render.
const {chromium}=require('playwright'),fs=require('fs'),assert=require('assert'),{execFileSync}=require('child_process');
(async()=>{
const fx=JSON.parse(execFileSync('python3',['-c',`import json
from foundry.v2.count_breakdown_fixture import config
from foundry.v2.run_q import run_v2
c=config();print(json.dumps({'cfg':c,'result':run_v2(c)}))`],{encoding:'utf8',maxBuffer:1<<28}));
const html=fs.readFileSync('web/console_v2.html','utf8').replace('<script src="/web/rates_workspace.js"></script>','<script>'+fs.readFileSync('web/rates_workspace.js','utf8')+'</script>').replace('<head>','<head><script>window.V3=true;window.V31=true;</script>').replace(/renderTabs\(\);\nwhoami\(\)\.then[^\n]+/,'');
const browser=await chromium.launch({executablePath:process.env.FOUNDRY_CHROMIUM_PATH,args:['--no-sandbox','--disable-gpu','--single-process','--no-zygote'],headless:true});
try{
const page=await browser.newPage({viewport:{width:1600,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));page.setDefaultTimeout(15000);
await page.route('**/*',r=>r.fulfill({status:200,json:{}}));await page.goto('http://foundry.test');await page.setContent(html);
await page.evaluate(f=>{cfg=f.cfg;lastRes=f.result;window._st=[];appStatus=(k,m)=>window._st.push([k,m]);refresh=()=>{};scheduleAutosave=()=>{};document.body.classList.add('insp-closed');renderTabs();setTab('products');
  const s=cfg.assumptions.obs_exposures[2].fee_streams[0];s.driver.trajectory='flat';s.driver.params.base=1250;s.driver.params.share_spec={source:'entered',trajectory:'explicit',cadence:'year',values:[0.1,0.2],unit:'share'};
  window._prdSel=cfg.assumptions.obs_exposures[2];window._prdView='product';window._prdTab='streams';window._stSelObj=s;window._stTab='activity';renderContent();},fx);
const settle=()=>page.waitForTimeout(120);const spec=()=>page.evaluate(()=>JSON.parse(JSON.stringify(cfg.assumptions.obs_exposures[2].fee_streams[0].driver.params.share_spec)));
const G=page.locator('.lfx-sted .fxs-mod .fxs-sched');
// Collapse and reopen the actual participation grid without writing any configuration.
const original=await page.evaluate(()=>JSON.stringify(cfg));
await G.locator('[data-fxs-collapse]').click();
assert.strictEqual(await G.locator('input.fxs-cell').first().isVisible(),false);
assert.strictEqual(await G.locator('[data-fxs-collapse]').innerText(),'Edit schedule');
await page.evaluate(()=>renderContent());
assert.strictEqual(await G.locator('input.fxs-cell').first().isVisible(),false,'collapse survives render');
await G.locator('[data-fxs-collapse]').click();
assert.strictEqual(await G.locator('input.fxs-cell').first().isVisible(),true);
assert.strictEqual(await page.evaluate(()=>JSON.stringify(cfg)),original);
await G.locator('button',{hasText:'Paste values'}).click();
// r480: a paste must cover the horizon, so the draft is the full schedule (30, 40, then 40 held by the author).
const _sp0=await spec(),_need=await page.evaluate(c=>_seriesSourcePeriods(c||_nativeFlowPeriod()),_sp0.cadence);const DRAFT=['30','40'].concat(Array(Math.max(0,_need-2)).fill('40')).join('\t');
await G.locator('textarea').fill(DRAFT);
await G.locator('[data-fxs-paste-close]').click();
assert.strictEqual(await G.locator('.paste-surface-closed-note').count(),0);
assert.strictEqual(await G.locator('textarea').isVisible(),false);
await G.locator('button',{hasText:'Paste values'}).click();
assert.strictEqual(await G.locator('textarea').inputValue(),DRAFT,'draft survives close');
await G.locator('button',{hasText:'Load (replace)'}).click();await settle();
assert.deepStrictEqual((await spec()).values.slice(0,2),[.3,.4]);
await G.locator('[data-fxs-collapse]').click();await G.locator('[data-fxs-collapse]').click();
assert.deepStrictEqual((await spec()).values.slice(0,2),[.3,.4]);
// All other renderer families expose the same disclosure and preserve model data.
await page.evaluate(()=>{
 const host=document.createElement('div');host.id='review-grids';document.body.appendChild(host);
 host.innerHTML=['level','stock','coef'].map(kind=>_fxSchedGridHtml({kind,fi:0,si:0,obj:{schedule:{1:2,2:3}},per:'month',title:kind,unit:'count',pasteId:'review-'+kind,clear:'',hint:''})).join('')+_fxsFaGrid('assumptions.deposit_products.0.balance_path',{cadence:'month',values:[1000,2000]},'money');
 fxScheduleDisclosures();
});
const extra=page.locator('#review-grids .fxs-sched');assert.strictEqual(await extra.count(),4);
for(let i=0;i<4;i++){const g=extra.nth(i);await g.locator('[data-fxs-collapse]').click();assert.strictEqual(await g.locator('input').first().isVisible(),false);await g.locator('[data-fxs-collapse]').click();assert.strictEqual(await g.locator('input').first().isVisible(),true);}
await page.screenshot({path:'/workspace/scratch/370303911165/r441-schedules.png',fullPage:true});
assert.deepStrictEqual(errors,[]);
console.log('r441 schedule disclosure: ok');
}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
