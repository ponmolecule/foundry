const {chromium}=require('playwright'),fs=require('fs'),assert=require('assert'),{execFileSync}=require('child_process');
(async()=>{
const c=JSON.parse(execFileSync('python3',['-c','import json;from foundry.v2.tests_r386_reuse import setup;print(json.dumps(setup()))'],{encoding:'utf8'}));
const html=fs.readFileSync('web/console_v2.html','utf8').replace(/renderTabs\(\);\nwhoami\(\)\.then[^\n]+/,'');
const browser=await chromium.launch({executablePath:process.env.FOUNDRY_CHROMIUM_PATH,args:['--no-sandbox','--disable-gpu','--single-process','--no-zygote'],headless:true});
try {const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));await page.route('**/*',r=>r.fulfill({json:{}}));await page.goto('http://foundry.test');await page.setContent(html);
await page.evaluate(c=>{cfg=c;cfg.assumptions.deposit_products[0].fee_streams=[{name:'Fraud',basis:'balance',driver:{source:'own_balance',trajectory:'flat',params:{}},rate:{behavior:'flat',params:{rate_ann:0}},cost:{kind:'none',params:{}},timing:{start_period:1}}];refresh=()=>{};renderContent=()=>{const p=cfg.assumptions.deposit_products[0];document.getElementById('content').innerHTML=_feeStreamsSectionHtml('deposit',p,'assumptions.deposit_products.0',2000)};renderContent()},c);
for(const width of [1440,1024,768]){
 await page.setViewportSize({width,height:1100});
 const positions=await page.evaluate(()=>{const b=document.querySelector('.st-body');const a=b.querySelector('select[onchange*="feeStreamDriverSourceChange"]');const m=b.querySelector('select[onchange*=".driver.measure"]');const field=a.closest('.fld'),label=field.querySelector('label');return {a:a.getBoundingClientRect().toJSON(),m:m.getBoundingClientRect().toJSON(),label:label.getBoundingClientRect().toJSON()}});
 assert(positions.a.width>0 && positions.m.width>0,'fields should be visible');
 assert(Math.abs(positions.a.y-positions.m.y)<2,'balance/source controls aligned at '+width+': '+JSON.stringify(positions));
 assert(positions.a.y-positions.label.bottom<12,'source label sits above selector at '+width+': '+JSON.stringify(positions));
}
let sel=page.locator('select[onchange*=".driver.measure"]');assert.strictEqual(await sel.inputValue(),'period_average');await sel.evaluate(e=>{e.value='period_begin';e.dispatchEvent(new Event('change',{bubbles:true}))});
await page.locator('select[onchange*="_feeCostFactorSetKind"]').evaluate(e=>{e.value='pct_of_balance_opex';e.dispatchEvent(new Event('change',{bubbles:true}))});await page.waitForTimeout(100);
const input=page.locator('input[onchange*="_feeCostFactorValue"]');await input.evaluate(e=>{e.value='0.1';e.dispatchEvent(new Event('change',{bubbles:true}))});
const data=await page.evaluate(()=>JSON.parse(JSON.stringify(cfg.assumptions.deposit_products[0].fee_streams[0])));assert.strictEqual(data.driver.measure,'period_begin');assert.strictEqual(data.cost.kind,'pct_of_balance_opex');assert(Math.abs(data.cost.params.factor_path.value-.001)<1e-12);
await page.evaluate(()=>{cfg=JSON.parse(JSON.stringify(cfg));renderContent()});assert.strictEqual(await page.locator('select[onchange*=".driver.measure"]').inputValue(),'period_begin');assert.strictEqual(await page.locator('select[onchange*="_feeCostFactorSetKind"]').inputValue(),'pct_of_balance_opex');assert.strictEqual(errors.length,0,errors.join('\n'));console.log('PASS beginning balance choice, rate, alignment, and reload');
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exit(1)});
