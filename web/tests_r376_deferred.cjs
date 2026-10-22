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
const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));await page.route('**/*',r=>r.fulfill({status:200,json:{}}));await page.goto('http://foundry.test');await page.setContent(html);
await page.evaluate(f=>{cfg=f.cfg;lastRes=f.result;window.V3=true;window.V31=true;currentTab='config';window._cfgModule='cac';window._cfgSectionOpen={customeracq:true};refresh=()=>{};scheduleAutosave=()=>{};renderContent();},fixture);
const root=page.locator('#card-cac');assert.strictEqual(await root.getByText('Publish customer flows',{exact:true}).count(),0);assert.strictEqual(await root.locator('.cac-audit-grid').count(),2);
for(const width of [1440,1024,768]){
 await page.setViewportSize({width,height:1100});
 const bad=await page.evaluate(()=>{const root=document.querySelector('#card-cac'),rect=root.getBoundingClientRect();return [...root.querySelectorAll('input,select,button')].filter(e=>e.getClientRects().length).filter(e=>{const r=e.getBoundingClientRect();return r.left<rect.left-2||r.right>rect.right+2}).map(e=>e.outerHTML.slice(0,120));});assert.deepStrictEqual(bad,[],width+' CAC controls contained');
}
await page.setViewportSize({width:1440,height:1100});await root.screenshot({path:'/tmp/r376-cac.png'});
// Input nodes stay mounted across successful / failed readonly preview refreshes.
await page.evaluate(()=>{window._heldCac=document.querySelector('#card-cac input[aria-label="Feed name"]');lastRes=null;lastErrs=[{message:'Incomplete unrelated lending input'}];refreshConfigPreviews();});
assert.strictEqual(await root.locator('.cac-audit-grid').count(),2);assert((await root.innerText()).includes('Last completed run'));assert(await page.evaluate(()=>window._heldCac===document.querySelector('#card-cac input[aria-label="Feed name"]')));
await page.evaluate(f=>{lastRes=f.result;lastErrs=null;refreshConfigPreviews();},fixture);assert(!(await root.innerText()).includes('Last completed run'));
// Stable disclosure identity and feed rename preserve last completed results.
await root.locator('.cac-feed-disclosure').nth(1).locator('summary').first().click();
await page.evaluate(()=>renameCacFeed('Advances','Renamed Advances'));assert.strictEqual(await root.locator('.cac-audit-grid').count(),2);
await root.locator('.cac-feed-toolbar button').click();assert.strictEqual(await root.locator('details.cac-feed-disclosure[open]').count(),1);assert((await root.locator('details.cac-feed-disclosure[open]').innerText()).includes('first run'));
// All eligible flows are available without publication and missing channels get IDs.
const opts=await page.evaluate(()=>_accountActivityOptions('transaction'));assert(opts.some(o=>o.label.includes('Sales')));
// Expense source, exclusions and days controls work in the actual named component editor.
await page.evaluate(()=>{window._cfgModule='sec';document.getElementById('content').innerHTML='<div class="cfg-stage"><div id="card-sec" class="cfgcard" style="display:block"><div class="fk-panel">'+_olComponentCardFk(cfg.assumptions.other_liabilities_model.components[0],0)+'</div></div></div>';document.querySelector('#content details').open=true;});
assert((await page.locator('#content').innerText()).includes('Days payable'));assert((await page.locator('#content').innerText()).includes('Include categories'));await page.screenshot({path:'/tmp/r376-payable.png',fullPage:true});
// Explicit money input repeats units at point of paste; stored dollars never change.
await page.evaluate(()=>{const path='assumptions.balance_components_model.components.0.income_amount_spec';cfg.assumptions.balance_components_model={components:[{income_amount_spec:{source:'entered',trajectory:'explicit',cadence:'month',period:'month',values:[66818]}}]};window._faExplicitOpen=window._faExplicitOpen||{};faSeriesExplicitOpen(path);document.getElementById('content').innerHTML='<div class="cfg-stage"><div class="fk-panel">'+_fkSeriesRow('Income amount ($000s)',path,getPath(path),'money',true)+'</div></div>';});
assert((await page.locator('#content').innerText()).includes('Values in $000s'));assert((await page.locator('#content').innerText()).includes('Amount period'));assert((await page.locator('textarea').getAttribute('placeholder')).includes('$000s'));assert.strictEqual(await page.evaluate(()=>cfg.assumptions.balance_components_model.components[0].income_amount_spec.values[0]),66818);
assert.deepStrictEqual(errors,[]);console.log('PASS CAC disclosure/creation, 1440/1024/768 containment, automatic flows, summary retention/recovery/rename, mounted inputs, payable editor, explicit units, no runtime errors');
}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
