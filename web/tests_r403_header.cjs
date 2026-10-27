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
for(const width of [1600,1180,1024,768]){
 await page.setViewportSize({width,height:900});await page.evaluate(()=>{document.getElementById('engMenu').style.display='none';});await page.locator('#engMenuBtn').click();
 const r=await page.evaluate(()=>{const rect=id=>{let r=document.getElementById(id).getBoundingClientRect();return {left:r.left,right:r.right,width:r.width,top:r.top,bottom:r.bottom};};return {menu:rect('engMenu'),chip:rect('versionChip'),bank:rect('bankLabel'),box:rect('chevBox'),button:rect('engMenuBtn'),save:rect('saveBtn'),width:innerWidth};});
 assert(r.menu.left>=7&&r.menu.right<=width-7,JSON.stringify(r));assert(r.menu.top>=r.box.bottom,JSON.stringify(r));assert(r.button.right<=width,JSON.stringify(r));
 if(width===1600){await page.screenshot({path:'/workspace/scratch/370303911165/header-r403.png'});assert(Math.abs(r.menu.width-640)<1,JSON.stringify(r));assert(Math.abs(r.menu.left-r.chip.left)<2,JSON.stringify(r));assert(r.box.left>210,JSON.stringify(r));}
 await page.locator('#engMenuBtn').click();
}
await page.setViewportSize({width:1600,height:900});await page.locator('#versionChip').click();const edit=await page.locator('#scenarioName').boundingBox();assert(edit.width>=339&&edit.width<=353,JSON.stringify(edit));await page.locator('#scenarioName').press('Escape');
assert.strictEqual(await page.evaluate(()=>JSON.stringify(cfg)),await page.evaluate(()=>window._cfgBefore));assert.deepStrictEqual(errors,[]);console.log('PASS header spacing, expanded version editor/menu, anchor, viewport containment and no configuration changes');
}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
