const {chromium}=require('playwright'),fs=require('fs'),assert=require('assert'),{execFileSync}=require('child_process');
(async()=>{
const html=fs.readFileSync('web/console_v2.html','utf8').replace(/renderTabs\(\);\nwhoami\(\)\.then[^\n]+/,'');
const browser=await chromium.launch({executablePath:process.env.FOUNDRY_CHROMIUM_PATH,args:['--no-sandbox','--disable-gpu','--single-process','--no-zygote'],headless:true});
try{
const page=await browser.newPage({viewport:{width:1440,height:900}}),errors=[];page.on('pageerror',e=>errors.push(e.message));let authenticated=false,holdSave=null,saveReceived=false;
await page.route('**/*',async r=>{const u=r.request().url();if(u.endsWith('/api/auth/login')){authenticated=true;return r.fulfill({status:200,json:{user:'analyst'}});}if(u.includes('/api/auth/'))return r.fulfill({status:authenticated?200:401,json:authenticated?{user:'analyst'}:{detail:'Unauthorized'}});if(u.endsWith('/api/v31/engagement/save-current')){saveReceived=true;if(holdSave)await holdSave;return r.fulfill({status:200,json:{slug:'working'}});}if(u.endsWith('/api/v2/preview'))return r.fulfill({status:401,json:{detail:'Unauthorized'}});return r.fulfill({status:200,json:{}});});
await page.goto('http://foundry.test');await page.setContent(html);
const c=JSON.parse(execFileSync('python3',['-c','import json;from foundry.v2.tests_r369_lending_contracts import config;print(json.dumps(config()))'],{encoding:'utf8'}));
await page.evaluate(c=>{window.AUTHED='analyst';cfg=c;cfg.scenario_name='working';normalizeCfg(cfg);syncModules();LC.land('open','saved');markPristine();cfg.assumptions.test_recovery=123;sessionSafety.checkpoint();},c);
assert(await page.evaluate(()=>Object.keys(localStorage).some(k=>k.startsWith('foundry-recovery-v1:analyst:'))),'saved engagement edits not protected');
// Authentication loss preserves model and latest results; no page navigation/reinitialization.
await page.evaluate(()=>{lastRes={workforce:{counts:[[1,2]]},run_hash:'last-good'};lastErrs=null;window._before=JSON.stringify(cfg);normalizeCfg=()=>{};syncModules=()=>{};loadSourceCatalog=async()=>{};paintChrome=()=>{};renderContent=()=>{};refreshConfigPreviews=()=>{};refreshLsrcLive=()=>{};currentTab='config';});
await page.evaluate(()=>preview());assert(await page.evaluate(()=>lastRes?.run_hash==='last-good'&&lastErrs[0].message.includes('Session expired')&&JSON.stringify(cfg)===window._before),'401 removed results or edited model');
assert(await page.locator('#sessionSafetyNotice').isVisible(),'no session warning');
await page.evaluate(()=>{window._realSave=engMenuSave;window._retry=0;engMenuSave=async nm=>{window._retry++;window._retryName=nm;};refresh=()=>{};sessionSafety.saveFailed('working');});
await page.screenshot({path:'/tmp/r373-session.png'});await page.locator('#sessionSafetyPassword').fill('secret');await page.locator('#sessionSafetyDialog button[type=submit]').click();
await page.waitForFunction(()=>window._retry===1);assert(await page.evaluate(()=>JSON.stringify(cfg)===window._before&&window._retryName==='working'),'reauth replaced edits or lost requested save');
assert.strictEqual(await page.locator('#sessionSafetyPassword').inputValue(),'');
// Another user's local copy must never be offered. Recovery requires an explicit choice.
await page.evaluate(()=>{sessionSafety.saved(JSON.stringify(cfg));localStorage.setItem('foundry-recovery-v1:someone-else:x',JSON.stringify({user:'someone-else',at:Date.now(),config:{scenario_name:'private'}}));sessionSafety.offer();});
assert(!(await page.locator('#sessionSafetyDialog').evaluate(e=>e.open)),'cross-account draft offered');
await page.evaluate(()=>{cfg.assumptions.test_recovery=456;sessionSafety.checkpoint();window._unrestored=JSON.stringify(cfg);sessionSafety.offer();});
assert(await page.locator('#sessionSafetyDialog').evaluate(e=>e.open),'no reload recovery offer');assert(await page.evaluate(()=>JSON.stringify(cfg)===window._unrestored),'offer silently replaced model');
await page.locator('#sessionSafetyDismiss').click();
// Explicit restore does not run boot or replace the server copy, and is marked unsaved.
await page.evaluate(()=>{renderGlobals=()=>{};setTab=()=>{};syncNameChrome=()=>{};freezeOriginal=()=>{};confirmDiscardUnsaved=()=>true;cfg.assumptions.test_recovery=999;sessionSafety.offer();});
await page.locator('#sessionSafetyRestore').click();assert(await page.evaluate(()=>cfg.assumptions.test_recovery===456&&!isPristine()&&LC.hasUnsaved()&&window._openSlug===null),'restore failed or falsely marked saved');
// An in-flight save must not mark edits made after its submitted snapshot as saved.
let release;holdSave=new Promise(r=>release=r);saveReceived=false;
await page.evaluate(()=>{engMenuSave=window._realSave;window._saveMessage='';appStatus=(_s,m)=>window._saveMessage=m;_purgeRecoveryDrafts=async()=>{};syncBankLabel=()=>{};loadEngStore=async()=>{};window._marked=0;LC.markSaved=()=>window._marked++;engMenuSave('working');});
await page.waitForTimeout(50);assert(saveReceived,'save not submitted');await page.evaluate(()=>{cfg.assumptions.test_recovery=777;});release();await page.waitForFunction(()=>window._saveMessage.includes('Newer edits'));
assert(await page.evaluate(()=>window._marked===0&&cfg.assumptions.test_recovery===777&&!isPristine()),'in-flight save swallowed newer edits');holdSave=null;

await page.route('**/api/auth/renew',r=>r.abort());await page.evaluate(()=>sessionSafety.check());assert((await page.locator('#sessionSafetyNotice').innerText()).includes('Connection interrupted'));
// Quota/private-mode failure cannot be advertised as protected.
await page.evaluate(()=>{Storage.prototype.setItem=function(){throw Error('quota');};cfg.assumptions.test_recovery=789;sessionSafety.checkpoint();});
assert((await page.locator('#sessionSafetyNotice').innerText()).includes('storage is unavailable'));
assert.deepStrictEqual(errors,[]);console.log('PASS saved-engagement local recovery, 401 result/input retention, in-place reauthentication + one save retry, password clearing, account isolation, explicit recovery, storage failure warning');
}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
