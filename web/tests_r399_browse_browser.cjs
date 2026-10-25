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
await page.evaluate(f=>{cfg=f.cfg;lastRes=f.result;currentTab='config';window._cfgModule='cac';window._cfgSectionOpen={customeracq:true};refresh=()=>{};scheduleAutosave=()=>{};renderContent();},fixture);

// Warm the pre-existing legacy view normalization, then reproduce an older saved
// engagement that has stable source identities but no publication-map fields.
await page.evaluate(()=>{for(const f of Object.values(cfg.assumptions.cac_feeds)){delete f.activity_series_ids;for(const c of f.channels||[])delete c.activity_series_ids;}LC.land('open','Browse test');window._beforeBrowse=JSON.stringify(cfg);});
async function same(){assert.strictEqual(await page.evaluate(()=>JSON.stringify(cfg)),await page.evaluate(()=>window._beforeBrowse),'Browsing changed configuration');assert.strictEqual(await page.evaluate(()=>LC.state()),'CLEAN','Browsing dirtied the engagement');}
for(let n=0;n<3;n++)await page.evaluate(()=>renderContent());await same();
const feedButtons=page.locator('#card-cac .cacn-ri');await feedButtons.nth(1).click();await same();
const edit=page.locator('#card-cac .cacn-ch button').filter({hasText:/Edit/}).first();if(await edit.count()){await edit.click();await same();}
await page.evaluate(()=>{_accountActivityOptions('transaction');_workforceCapacityOptions();});await same();
const semantic=await page.evaluate(()=>{const f=Object.values(cfg.assumptions.cac_feeds)[0];f.beginning_customers=(f.beginning_customers||0)+1;return JSON.stringify(cfg);});
await page.evaluate(()=>renderContent());assert.strictEqual(await page.evaluate(()=>JSON.stringify(cfg)),semantic,'Browsing after an edit added metadata');assert.strictEqual(await page.evaluate(()=>LC.state()),'MODIFIED');
assert.deepStrictEqual(errors,[]);console.log('PASS actual Customer Acquisition render/feed navigation, clean baseline, no publication writes, real edit retained');
}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
