const {chromium}=require('playwright'),fs=require('fs'),assert=require('assert'),{execFileSync}=require('child_process');
(async()=>{
const data=JSON.parse(execFileSync('python3',['-c',"import json;from foundry.v2.tests_r412_securities_cash_targets import CashTargets;from foundry.v2.tests_balance_components import component;c=CashTargets().config();c['assumptions']['balance_components_model']={'enabled':True,'components':[component('cash-source','cash_allocation',0)]};print(json.dumps(c))"],{encoding:'utf8'}));
const html=fs.readFileSync('web/console_v2.html','utf8').replace('<head>','<head><script>window.V31=true;window.V3=true;</script>').replace(/renderTabs\(\);\nwhoami\(\)\.then[^\n]+/,'');
const browser=await chromium.launch({executablePath:process.env.FOUNDRY_CHROMIUM_PATH,args:['--no-sandbox','--disable-gpu','--single-process','--no-zygote'],headless:true});
try{const page=await browser.newPage({viewport:{width:1440,height:1100}}),errors=[];page.setDefaultTimeout(8000);page.on('pageerror',e=>errors.push(e.message));await page.route('**/*',r=>{const path=new URL(r.request().url()).pathname;if(path==='/web/rates_workspace.js')return r.fulfill({contentType:'text/javascript',body:fs.readFileSync('web/rates_workspace.js','utf8')});if(path==='/web/rates_workspace.css')return r.fulfill({contentType:'text/css',body:fs.readFileSync('web/rates_workspace.css','utf8')});return r.fulfill({json:{}});});await page.goto('http://foundry.test');await page.setContent(html);
await page.evaluate(c=>{cfg=c;refresh=()=>{};currentTab='config';lastRes=null;lastErrs=[];window._cfgModule='sec';window._cfgSectionOpen={secaoci:true};window._fsxActive='s5';window._fsxOpen={s5:true};renderContent();},data);
const source=()=>page.locator('select[onchange*="secManagedTargetSource"]');
await source().selectOption('balance_component.cash-source.end');
assert.strictEqual(await page.locator('select[onchange*="secManagedTargetTiming"]').inputValue(),'prior_period');
assert.strictEqual(await page.locator('select[onchange*="secManagedTargetPriorInit"]').inputValue(),'opening_source');
await page.locator('select[onchange*="secManagedTargetCadence"]').selectOption('model_period');
assert.strictEqual(await page.locator('select[onchange*=".target_path"]').count(),0);
await page.locator('select[onchange*="secManagedTargetCadence"]').selectOption('quarter');
await page.locator('select[onchange*=".target_path"]').selectOption('ramp');
await page.locator('select[onchange*=".interest_balance_measure"]').last().selectOption('period_average');
assert(await page.getByText('Source: User-defined cash-source', {exact:false}).isVisible());
for(const width of [1440,1024,768]){await page.setViewportSize({width,height:1100});assert(await source().isVisible());const box=await source().boundingBox();assert(box.x>=0&&box.x+box.width<=width+1);}
await page.setViewportSize({width:1440,height:1100});await page.screenshot({path:'/tmp/r412-managed.png',fullPage:true});
assert.deepStrictEqual(errors,[]);console.log('PASS real managed portfolio renderer, named cash source, prior opening initialization, quarter/ramp/average controls and responsive source bounds');
}finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
