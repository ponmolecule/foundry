// r396: a labelled Remove feed button in feed settings asks first, names what links to the feed, then removes it.
const {chromium}=require('playwright'),fs=require('fs'),assert=require('assert'),{execFileSync}=require('child_process');
(async()=>{
const fixture=JSON.parse(execFileSync('python3',['-c',`import json
from foundry.v2.tests_r376_deferred import config
from foundry.v2.run_q import run_v2
c=config();print(json.dumps({'cfg':c,'result':run_v2(c)}))`],{encoding:'utf8'}));
const html=fs.readFileSync('web/console_v2.html','utf8').replace('<script src="/web/rates_workspace.js"></script>','<script>'+fs.readFileSync('web/rates_workspace.js','utf8')+'</script>').replace('<head>','<head><script>window.V3=true;window.V31=true;</script>').replace(/renderTabs\(\);\nwhoami\(\)\.then[^\n]+/,'');
const browser=await chromium.launch({executablePath:process.env.FOUNDRY_CHROMIUM_PATH,args:['--no-sandbox','--disable-gpu','--single-process','--no-zygote'],headless:true});
try{
const page=await browser.newPage({viewport:{width:1600,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>{errors.push('dialog');d.dismiss();});page.setDefaultTimeout(10000);
await page.route('**/*',r=>r.fulfill({status:200,json:{}}));await page.goto('http://foundry.test');await page.setContent(html);
await page.evaluate(f=>{cfg=f.cfg;lastRes=f.result;currentTab='config';window._cfgModule='cac';window._cfgSectionOpen={customeracq:true};refresh=()=>{};scheduleAutosave=()=>{};renderContent();},fixture);
const feeds=()=>page.evaluate(()=>Object.keys(cfg.assumptions.cac_feeds));const root=page.locator('#card-cac');
// 1. A new test feed: Remove feed sits beside Done; the old unlabelled × is gone.
await root.locator('.cacn-add').click();const before=await feeds();const added=before[before.length-1];
assert(await root.locator('.cacn-band .cacn-btn',{hasText:'Remove feed'}).isVisible());
assert.strictEqual(await root.locator('.cacn-set button[aria-label="Remove feed"]').evaluate(b=>getComputedStyle(b).display),'none');
// 2. It asks first; Cancel keeps the feed.
await root.locator('.cacn-band .cacn-btn',{hasText:'Remove feed'}).click();assert(await root.locator('.cacrm').isVisible());
assert(/Nothing else in the model links to this feed/.test(await root.locator('.cacrm').innerText()));assert.deepStrictEqual(await feeds(),before);
await root.locator('.cacrm .cacn-btn',{hasText:'Cancel'}).click();assert.strictEqual(await root.locator('.cacrm').count(),0);assert.deepStrictEqual(await feeds(),before);
// 3. Remove: the feed is gone and the rail returns to All feeds.
await root.locator('.cacn-band .cacn-btn',{hasText:'Remove feed'}).click();await root.locator('.cacrm .cacn-btn.rm').click();
assert.deepStrictEqual(await feeds(),before.filter(x=>x!==added));assert.strictEqual(await root.locator('.cacn-ri.on .t').textContent(),'All feeds');
// 4. A feed with something linked to it names the link before removal.
const fn=(await feeds())[0];
await page.evaluate(fn=>{const fd=cfg.assumptions.cac_feeds[fn];(cfg.assumptions.obs_exposures=cfg.assumptions.obs_exposures||[]).push({name:'Linked fee product',managed_notional_source:fn,managed_notional_source_id:fd.series_id});cacnSelect(0);cacnSettings();cacnRemoveAsk(true);},fn);
assert(/Off-balance-sheet › Linked fee product/.test(await root.locator('.cacrm').innerText()),'link named');
await root.locator('.cacrm .cacn-btn',{hasText:'Cancel'}).click();assert((await feeds()).includes(fn));
assert.deepStrictEqual(errors,[]);
console.log('PASS r396 remove feed: labelled button, asks first, cancel keeps, remove deletes and returns to All feeds, linked products named');
}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
