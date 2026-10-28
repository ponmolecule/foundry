const {chromium}=require('playwright'),fs=require('fs'),assert=require('assert'),{execFileSync}=require('child_process');
(async()=>{
const cfgData=JSON.parse(execFileSync('python3',['-c',"import json;from foundry.v2.tests_balance_components import configured,component;print(json.dumps(configured([component('cash','cash_allocation',0)])))"],{encoding:'utf8'}));
const html=fs.readFileSync('web/console_v2.html','utf8').replace(/renderTabs\(\);\nwhoami\(\)\.then[^\n]+/,'');
const browser=await chromium.launch({executablePath:process.env.FOUNDRY_CHROMIUM_PATH,args:['--no-sandbox','--disable-gpu','--single-process','--no-zygote'],headless:true});
try{const page=await browser.newPage({viewport:{width:1440,height:1100}});page.setDefaultTimeout(8000);const errors=[];page.on('pageerror',e=>errors.push(e.message));
await page.route('**/*',r=>r.fulfill({json:{}}));await page.goto('http://foundry.test');await page.setContent(html);
await page.evaluate(c=>{document.querySelectorAll('style').forEach(s=>document.head.appendChild(s.cloneNode(true)));cfg=c;window._fkOpen={bc0:true};refresh=()=>{};renderContent=()=>{document.body.innerHTML='<main id="content"><section id="card-sec">'+_bcEditorHtmlFk()+'</section></main>';};renderContent();},cfgData);
const method=()=>page.locator('select[onchange*="bcIncomeMethod"]');assert.strictEqual(await method().locator('option').count(),2);
await method().selectOption('separate_balance_yield');
assert(await page.getByText('Income balance basis',{exact:false}).last().isVisible());
assert(await page.locator('[title*="This basis prices income only"]').count());
await page.screenshot({path:'/tmp/r411-cash-basis.png',fullPage:true});
assert.strictEqual(await page.evaluate(()=>cfg.assumptions.balance_components_model.components[0].income_balance_spec.unit),'money');
await page.locator('select[onchange*="bcTreatment"]').selectOption('earning_asset');assert.strictEqual(await method().locator('option').count(),3);
await page.locator('select[onchange*="bcTreatment"]').selectOption('cash_allocation');assert.strictEqual(await method().inputValue(),'separate_balance_yield');
await page.locator('select[onchange*="bcTreatment"]').selectOption('residual_cash');assert.strictEqual(await method().count(),0);
assert.strictEqual(await page.evaluate(()=>cfg.assumptions.balance_components_model.components[0].income_method),'balance_yield');assert.deepStrictEqual(errors,[]);
console.log('PASS cash basis editor, money source, treatment changes and residual fallback');
}finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
