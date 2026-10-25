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

await page.evaluate(f=>{window.AUTHED='analyst';cfg=normalizeCfg(f.cfg);lastRes=f.result;currentTab='config';refresh=()=>{};renderContent();},fixture);
const before=await page.evaluate(f=>{localStorage.clear();localStorage.setItem('foundry-recovery-v1:analyst:old-session',JSON.stringify({user:'analyst',at:Date.now()-86400000,config:f.cfg}));window._serverRecoveryCandidates=[];return localStorage.getItem('foundry-recovery-v1:analyst:old-session');},fixture);
await page.evaluate(()=>sessionSafety.offer());assert.strictEqual(await page.locator('#recoveryCopiesNotice').count(),0);assert.strictEqual(await page.locator('#sessionSafetyDialog[open]').count(),0);
assert.strictEqual(await page.evaluate(()=>localStorage.getItem('foundry-recovery-v1:analyst:old-session')),before,'Startup deleted checkpoint');
await page.evaluate(()=>{paintEngMenu();document.getElementById('engMenu').style.display='block';});await page.getByRole('button',{name:'Recovery copies…',exact:true}).click();await page.locator('#sessionSafetyDialog').waitFor({state:'visible'});assert((await page.locator('#sessionSafetyDialog').textContent()).includes('Previous recovery copies'));await page.locator('#sessionSafetyDismiss').click();
assert.strictEqual(await page.evaluate(()=>localStorage.getItem('foundry-recovery-v1:analyst:old-session')),before,'Review deleted checkpoint');
await page.evaluate(()=>{localStorage.clear();window._serverRecoveryCandidates=[];});await page.evaluate(()=>sessionSafety.offer(true));assert((await page.locator('#sessionSafetyDialog').textContent()).includes('No recovery copies'));await page.locator('#sessionSafetyDismiss').click();
assert.deepStrictEqual(errors,[]);console.log('PASS no startup banner/dialog, checkpoint preservation, menu review, dismissal and empty-state access');
}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
