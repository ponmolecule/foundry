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


await page.evaluate(f=>{window.AUTHED='analyst';cfg=normalizeCfg(f.cfg);cfg.proposed_bank='Example Community Bank';cfg.client_legal_name=cfg.proposed_bank;cfg.scenario_name='Example Community Bank · Expanded engagement version with a long name';lastRes=f.result;currentTab='config';refresh=()=>{};scheduleAutosave=()=>{};loadEngStore=async()=>{};renderContent();syncBankLabel();LC.land('open',cfg.scenario_name);_syncSaveBtn();window._cfgBefore=JSON.stringify(cfg);},fixture);

const name='A very long engagement scenario name with multiple descriptive terms and no truncation even when it must wrap at the end of the available screen';
await page.evaluate(name=>{engStore={engagements:[{name:'Example Community Bank · '+name,bank_display:'Example Community Bank',slug:'example-community-bank-long-version-20261027'}]};paintEngMenu();},name);
for(const width of [1600,1024,768]){
 await page.setViewportSize({width,height:900});await page.evaluate(()=>{document.getElementById('engMenu').style.display='none';});await page.locator('#engMenuBtn').click();
 const v=page.locator('#engMenu .eng-menu-version');await v.waitFor();assert.strictEqual(await v.textContent(),name);const z=await v.evaluate(el=>({client:el.clientWidth,scroll:el.scrollWidth,height:el.clientHeight,sh:el.scrollHeight,lines:getComputedStyle(el).whiteSpace}));assert(z.scroll<=z.client+1&&z.sh<=z.height+1&&z.lines==='normal',JSON.stringify(z));
 const menu=await page.locator('#engMenu').boundingBox();assert(menu.x>=7&&menu.x+menu.width<=width-7,JSON.stringify(menu));assert.strictEqual(await page.locator('#engMenu a[title="Delete this engagement"]').count(),1);
 if(width===1600){assert(Math.abs(menu.width-640)<1);await page.screenshot({path:'/workspace/scratch/370303911165/header-r404.png'});}
 await page.locator('#engMenuBtn').click();
}
assert.strictEqual(await page.evaluate(()=>JSON.stringify(cfg)),await page.evaluate(()=>window._cfgBefore));assert.deepStrictEqual(errors,[]);console.log('PASS 640px menu, long name wrapping, controls, responsive viewport and unchanged configuration');
}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
