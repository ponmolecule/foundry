const {chromium}=require('playwright'),fs=require('fs'),assert=require('assert'),{execFileSync}=require('child_process');
(async()=>{
const c=JSON.parse(execFileSync('python3',['-c','import json;from foundry.v2.tests_r383_linked_calculations import setup;print(json.dumps(setup()))'],{encoding:'utf8'}));
const html=fs.readFileSync('web/console_v2.html','utf8').replace(/renderTabs\(\);\nwhoami\(\)\.then[^\n]+/,'');
const browser=await chromium.launch({executablePath:process.env.FOUNDRY_CHROMIUM_PATH,args:['--no-sandbox','--disable-gpu','--single-process','--no-zygote'],headless:true});
try{const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));await page.route('**/*',r=>r.fulfill({json:{}}));await page.goto('http://foundry.test');await page.setContent(html);
await page.evaluate(c=>{cfg=c;refresh=()=>{};renderContent=()=>{document.getElementById('content').innerHTML='<div class="cfg-stage" style="padding:20px">'+depositBalanceHtml(cfg.assumptions.deposit_products[0],'assumptions.deposit_products.0')+'</div>';};renderContent();},c);
const original=await page.evaluate(()=>JSON.stringify(cfg));
await page.getByRole('button',{name:'+ Create weighted assumption…',exact:true}).click();
assert.strictEqual(await page.evaluate(()=>_sharedInputs().length),1);
await page.getByRole('button',{name:'Cancel',exact:true}).click();assert.strictEqual(await page.evaluate(()=>JSON.stringify(cfg)),original);
// Repeated opening replaces the dialog, never creates a record.
await page.evaluate(()=>{depositSharedCreate(0);depositSharedCreate(0);depositSharedCreate(0)});assert.strictEqual(await page.locator('#sharedAssumptionDialog').count(),1);assert.strictEqual(await page.evaluate(()=>JSON.stringify(cfg)),original);
await page.getByLabel('New assumption name',{exact:true}).fill('Weighted balance');await page.getByRole('button',{name:'Create',exact:true}).click();assert.strictEqual(await page.evaluate(()=>_sharedInputs().length),1);assert(await page.getByLabel('New assumption name',{exact:true}).evaluate(x=>!x.validity.valid));
await page.getByLabel('New assumption name',{exact:true}).fill('New deposit value');
await page.evaluate(()=>{const form=document.querySelector('#sharedAssumptionDialog form');form.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}));form.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}));});
assert.strictEqual(await page.evaluate(()=>_sharedInputs().length),2);assert.strictEqual(await page.getByLabel('Deposit shared amount',{exact:true}).inputValue(),await page.evaluate(()=>_sharedInputs()[1].id));
assert(await page.getByText('Edit shared assumption · affects every consumer',{exact:true}).evaluate(x=>x.parentElement.open));
// Add two legacy-style duplicates plus a transitive reference to the original assumption.
await page.evaluate(()=>{_sharedInputs().push({id:'duplicate-1',name:'Weighted amount per customer',unit:'money_per_unit',spec:{source:'entered',value:0}},{id:'duplicate-2',name:'Weighted amount per customer',unit:'money_per_unit',spec:{source:'entered',value:0}},{id:'dependent',name:'Dependent assumption',unit:'money_per_unit',spec:{source:'input_ref',input_id:'balances'}});renderContent();});
await page.getByRole('button',{name:'Manage assumptions…',exact:true}).click();
const item=name=>page.locator('.shared-assumption-item').filter({has:page.locator('strong',{hasText:new RegExp('^'+name+'$')})});
assert(await item('New deposit value').getByRole('button',{name:'Delete',exact:true}).isDisabled());
assert(await item('Weighted balance').getByRole('button',{name:'Delete',exact:true}).isDisabled());
await item('New deposit value').getByRole('button',{name:'Unlink here',exact:true}).click();assert(await item('New deposit value').getByRole('button',{name:'Delete',exact:true}).isEnabled());await item('New deposit value').getByRole('button',{name:'Delete',exact:true}).click();
await item('Weighted amount per customer').first().getByRole('button',{name:'Delete',exact:true}).click();await item('Weighted amount per customer').first().getByRole('button',{name:'Delete',exact:true}).click();
assert.strictEqual(await page.evaluate(()=>_sharedInputs().length),2);assert.strictEqual(await page.evaluate(()=>_sharedInputs().find(x=>x.id==='dependent').spec.input_id),'balances');
for(const width of [1440,1024,768]){await page.setViewportSize({width,height:900});const d=await page.locator('#sharedAssumptionDialog').boundingBox();assert(d.x>=0&&d.x+d.width<=width);if(width===1440)await page.locator('#sharedAssumptionDialog').screenshot({path:'/tmp/r384-manage-assumptions.png'});}
await page.getByLabel('Close shared assumptions',{exact:true}).click();
await page.evaluate(()=>{loanSharedCreate(0)});assert.strictEqual(await page.evaluate(()=>_sharedInputs().length),2);await page.getByRole('button',{name:'Cancel',exact:true}).click();
assert.deepStrictEqual(errors,[]);console.log('PASS explicit create/cancel, duplicate names, repeated clicks/submits, automatic selection/opening, linked deletion protection, unlink, legacy duplicate cleanup, lending path, modal containment');
}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
