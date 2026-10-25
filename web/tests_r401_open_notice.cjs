// r393: customer acquisition edits through a feed rail. All feeds compares every feed; a feed shows its settings band,
// a channel results table and, while editing, the existing channel driver editor inline beneath the table.
const {chromium}=require('playwright'),fs=require('fs'),assert=require('assert'),{execFileSync}=require('child_process');
(async()=>{
const fixture=JSON.parse(execFileSync('python3',['-c',`import json,copy
from foundry.v2.tests_r376_deferred import config
from foundry.v2.run_q import run_v2
c=config();c['assumptions']['cac_feeds']['Advances']=copy.deepcopy(c['assumptions']['cac_feeds']['Practices']);f=c['assumptions']['cac_feeds']['Advances'];f['series_id']='advance-auc';f['customer_count_series_id']='advance-customers'
r=run_v2(c);print(json.dumps({'cfg':c,'result':r}))`],{encoding:'utf8'}));
const html=fs.readFileSync('web/console_v2.html','utf8').replace('<script src="/web/rates_workspace.js"></script>','<script>'+fs.readFileSync('web/rates_workspace.js','utf8')+'</script>').replace('<head>','<head><script>window.V3=true;window.V31=true;</script>').replace(/renderTabs\(\);\nwhoami\(\)\.then[^\n]+/,'');
const browser=await chromium.launch({executablePath:process.env.FOUNDRY_CHROMIUM_PATH,args:['--no-sandbox','--disable-gpu','--single-process','--no-zygote'],headless:true});
try{
const page=await browser.newPage({viewport:{width:1600,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>d.accept());page.setDefaultTimeout(15000);
await page.route('**/*',r=>r.fulfill({status:200,json:{}}));await page.goto('http://foundry.test');await page.setContent(html);

await page.evaluate(f=>{cfg=normalizeCfg(f.cfg);lastRes=f.result;currentTab='config';refresh=()=>{};renderGlobals=()=>{};setTab=()=>{};loadSourceCatalog=async()=>{};subCheck=()=>{};LC.land('open','Existing');markPristine();},fixture);
await page.route('**/api/v31/engagement/good',route=>route.fulfill({status:200,json:fixture.cfg,headers:{'X-Foundry-Revision':'revision-a'}}));
const ok=await page.evaluate(()=>engMenuOpen('good'));assert.strictEqual(ok,true,'Success result must propagate through both wrappers');assert.strictEqual(await page.locator('#appStatus').isVisible(),false,'No busy/success zombie after open');assert.strictEqual(await page.evaluate(()=>window._saveHead.revision),'revision-a');
// A dirty engagement opens the existing guard, not a fake loading state.
await page.evaluate(()=>{cfg.assumptions.notice_test_edit=1;window._guardCount=0;_showGuard=()=>window._guardCount++;});
await page.evaluate(()=>engMenuOpen('good'));assert.strictEqual(await page.evaluate(()=>window._guardCount),1);assert.strictEqual(await page.locator('#appStatus').isVisible(),false);
await page.evaluate(()=>{delete cfg.assumptions.notice_test_edit;LC.land('open','Existing');markPristine();});
// HTTP and network failures replace the busy status with an actionable error.
await page.route('**/api/v31/engagement/missing',route=>route.fulfill({status:404,json:{error:'No such engagement'}}));assert.strictEqual(await page.evaluate(()=>engMenuOpen('missing')),false);assert((await page.locator('#appStatus').textContent()).includes('Could not open'));assert(!(await page.locator('#appStatus').textContent()).includes('Opening engagement'));
await page.route('**/api/v31/engagement/network-failure',route=>route.abort());assert.strictEqual(await page.evaluate(()=>engMenuOpen('network-failure')),false);assert((await page.locator('#appStatus').textContent()).includes('Could not open'));
// Finishing one operation must not erase a later, unrelated notice.
let release;await page.route('**/api/v31/engagement/delayed',async route=>{await new Promise(resolve=>release=resolve);await route.fulfill({status:200,json:fixture.cfg});});
await page.evaluate(()=>{window._openTask=engMenuOpen('delayed');});await page.waitForFunction(()=>document.getElementById('appStatus').textContent.includes('Opening engagement'));
await page.evaluate(()=>appStatus('err','A newer notice'));release();await page.evaluate(()=>window._openTask);assert((await page.locator('#appStatus').textContent()).includes('A newer notice'),'Completion erased newer status');
await page.evaluate(()=>appStatus(null));assert.deepStrictEqual(errors,[]);console.log('PASS engagement opening success, guard, HTTP/network failure, notice cleanup and newer-notice preservation');
}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
