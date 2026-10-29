// r418: a name-only member that no longer exists is shown as a repairable problem (no recursion), and saving
// Edit membership removes it; groups created in the browser carry product IDs end to end.
const {chromium}=require('playwright'),fs=require('fs'),assert=require('assert'),{execFileSync}=require('child_process');
(async()=>{
const fixture=JSON.parse(execFileSync('python3',['-c',`import json
from foundry.v2.run_q import run_v2
c=json.load(open('foundry/fixtures/universal_template_bank.json'))
c['reporting_manifest']={'reporting_products':[{'id':'rp-old','name':'Legacy group','members':[{'family':'deposit','name':'Retail Demand'},{'family':'deposit','name':'Gone product'}],'line_overrides':{}}]}
print(json.dumps({'cfg':c,'result':run_v2(c)}))`],{encoding:'utf8',maxBuffer:1<<28}));
const html=fs.readFileSync('web/console_v2.html','utf8').replace('<script src="/web/rates_workspace.js"></script>','<script>'+fs.readFileSync('web/rates_workspace.js','utf8')+'</script>').replace('<head>','<head><script>window.V3=true;window.V31=true;</script>').replace(/renderTabs\(\);\nwhoami\(\)\.then[^\n]+/,'');
const browser=await chromium.launch({executablePath:process.env.FOUNDRY_CHROMIUM_PATH,args:['--no-sandbox','--disable-gpu','--single-process','--no-zygote'],headless:true});
try{
const page=await browser.newPage({viewport:{width:1600,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));page.setDefaultTimeout(15000);
await page.route('**/*',r=>r.fulfill({status:200,json:{}}));await page.goto('http://foundry.test');await page.setContent(html);
await page.evaluate(f=>{cfg=f.cfg;lastRes=f.result;currentTab='detail';refresh=()=>{};scheduleAutosave=()=>{};window._pdView='reporting';renderContent();},fixture);
const C=page.locator('#content');
assert.strictEqual(await page.evaluate(()=>_rptMemKey({family:'deposit',name:'Gone product'})),'deposit/Gone product','unresolved reference, no recursion');
assert(/Gone product.*Edit membership/.test(await C.locator('.rpt-prob').innerText()),'repairable problem shown');
assert(/does not reconcile/.test(await C.locator('.rpt-cov').innerText()));
await page.evaluate(()=>{rptTab('plan');rptTab('objects');rptSelect('recon');rptSelect('rp-old');});
await page.evaluate(()=>rptOpenDialog('edit','rp-old'));
assert(/Gone product.*removed from membership when you save/.test(await C.locator('.rpt-dlg [data-rpt-missing]').innerText()));
await C.locator('.rpt-dlg [data-rpt-confirm]').click();
const mem=await page.evaluate(()=>cfg.reporting_manifest.reporting_products[0].members);
assert.deepStrictEqual(mem.map(m=>m.name),['Retail Demand']);
assert(mem[0].product_id&&mem[0].product_id===await page.evaluate(()=>cfg.assumptions.deposit_products[0].product_id),'saved member carries the product ID');
assert.deepStrictEqual(errors,[]);
console.log('PASS r418 reporting identity: missing legacy member resolves to a repairable problem without recursion; Edit membership removes it and saves product IDs');
}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
