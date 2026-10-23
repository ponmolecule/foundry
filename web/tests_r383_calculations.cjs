const {chromium}=require('playwright'),fs=require('fs'),assert=require('assert'),{execFileSync}=require('child_process');
(async()=>{
 const c=JSON.parse(execFileSync('python3',['-c','import json;from foundry.v2.tests_r383_linked_calculations import setup,with_calc;print(json.dumps(with_calc(setup())))'],{encoding:'utf8'}));
 const html=fs.readFileSync('web/console_v2.html','utf8').replace(/renderTabs\(\);\nwhoami\(\)\.then[^\n]+/,'');
 const browser=await chromium.launch({executablePath:process.env.FOUNDRY_CHROMIUM_PATH,args:['--no-sandbox','--disable-gpu','--single-process','--no-zygote'],headless:true});
 try{const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));await page.route('**/*',r=>r.fulfill({json:{}}));await page.goto('http://foundry.test');await page.setContent(html);
 await page.evaluate(c=>{cfg=c;refresh=()=>{};renderContent=()=>{const p=cfg.assumptions.deposit_products[0];document.getElementById('content').innerHTML='<div class="cfg-stage" style="padding:20px;max-width:1100px">'+depositBalanceHtml(p,'assumptions.deposit_products.0')+calcEditorHtml(0,0,cfg.assumptions.nie_detail.categories[0].linked_components[0])+'</div>';};renderContent();},c);
 await page.getByLabel('Deposit shared amount',{exact:true}).selectOption('balances');
 assert.strictEqual(await page.evaluate(()=>cfg.assumptions.deposit_products[0].balance_driver.balance_per_customer_spec.input_id),'balances');
 await page.getByText('Edit shared assumption · affects every consumer',{exact:true}).click();
 assert(await page.getByLabel('Component name',{exact:true}).count()===2);
 await page.getByLabel('Component name',{exact:true}).first().fill('Renamed component');await page.getByLabel('Component name',{exact:true}).first().press('Tab');
 assert.strictEqual(await page.evaluate(()=>cfg.assumptions.balance_components_model.inputs[0].spec.components[0].name),'Renamed component');
 // Fully expand the arithmetic and exercise a source-measure edit without changing the structure.
 await page.evaluate(()=>document.querySelectorAll('.linked-calc-node').forEach(x=>x.open=true));
 await page.getByLabel('Calculation balance measure',{exact:true}).selectOption('period_average');
 assert.strictEqual(await page.evaluate(()=>cfg.assumptions.nie_detail.categories[0].linked_components[0].expression.args[1].args[0].args[0].args[1].measure),'period_average');
 await page.getByLabel('Calculation flow observation',{exact:true}).first().selectOption('current');
 for(const width of [1440,1024,768]){await page.setViewportSize({width,height:1100});await page.evaluate(()=>{if(typeof fitControls==='function')fitControls();});for(const el of await page.locator('.linked-calc-editor input,.linked-calc-editor select,.linked-calc-editor button').all()){const b=await el.boundingBox();if(b)assert(b.x>=0&&b.x+b.width<=width+1,'control overflow at '+width);}if(width===1440)await page.locator('.cfg-stage').screenshot({path:'/tmp/r383-calculations.png'});}
 await page.evaluate(()=>{calcAdd(0)});assert.strictEqual(await page.evaluate(()=>cfg.assumptions.nie_detail.categories[0].linked_components.length),2);
 assert.deepStrictEqual(errors,[]);console.log('PASS weighted deposit editor, shared rename, expression measures/observations, nested layout at 1440/1024/768');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
