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
// 1. A blank cell is rejected: the stored value stays, the cell shows it again, and the user is told why.
const c1=G.locator('input.fxs-cell').first();await c1.fill('');await c1.press('Tab');await settle();
assert.deepStrictEqual((await spec()).values,[0.1,0.2],'blank does not silently keep or drop a value');
assert.strictEqual(await page.locator('.lfx-sted .fxs-mod .fxs-sched input.fxs-cell').first().inputValue(),'10','stored value shown again');
assert(await page.evaluate(()=>window._st.some(([k,m])=>k==='err'&&/needs a value/.test(m))),'reason shown');
// 2. Step / Smooth highlight follows the stored choice (yearly schedule in a monthly model).
const res=page.locator('.lfx-sted .fxs-mod .fxs-seg.fxs-res');assert.strictEqual(await res.count(),1,'step/smooth shown for a yearly schedule');
await res.locator('button',{hasText:'Smooth'}).click();await page.waitForTimeout(30);
assert.strictEqual((await spec()).resolution,'smooth');
assert.strictEqual(await page.locator('.lfx-sted .fxs-mod .fxs-seg.fxs-res button.on').innerText(),'Smooth','highlight matches the stored choice');
// 3. Clear also clears the grid's paste draft.
await page.locator('.lfx-sted .fxs-mod .fxs-link',{hasText:'Paste values'}).click();
const ta=page.locator('.lfx-sted .fxs-mod .fxs-paste textarea');await ta.fill('30\t40\t50');
await page.locator('.lfx-sted .fxs-mod .fxs-link',{hasText:'Clear'}).click();await settle();
assert.deepStrictEqual((await spec()).values,[],'values cleared');
const left=await page.evaluate(()=>[...document.querySelectorAll('.lfx-sted .fxs-mod .fxs-paste textarea')].map(t=>t.value));
assert(left.every(v=>v===''),'no stale pasted text: '+JSON.stringify(left));
// 4. Product-path grid (fxsFaSet) refuses a blank too, without touching the stored path.
const before=await page.evaluate(()=>{window._st=[];fxsFaSet('assumptions.no_such_path',1,'','rate');return window._st.length;});
assert.strictEqual(before,1,'blank refused on product-path grid');
assert.deepStrictEqual(errors,[]);
console.log('r440 review fixes: ok');
}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
