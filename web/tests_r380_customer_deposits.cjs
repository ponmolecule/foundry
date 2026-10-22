const {chromium}=require('playwright'),fs=require('fs'),assert=require('assert'),{execFileSync}=require('child_process');
(async()=>{
 const c=JSON.parse(execFileSync('python3',['-c','import json;from foundry.v2.tests_r380_customer_deposits import config;print(json.dumps(config()))'],{encoding:'utf8'}));
 const html=fs.readFileSync('web/console_v2.html','utf8').replace(/renderTabs\(\);\nwhoami\(\)\.then[^\n]+/,'');
 const browser=await chromium.launch({executablePath:process.env.FOUNDRY_CHROMIUM_PATH,args:['--no-sandbox','--disable-gpu','--single-process','--no-zygote'],headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/*',r=>r.fulfill({status:200,json:{}}));await page.goto('http://foundry.test');await page.setContent(html);
  await page.evaluate(c=>{cfg=c;refresh=()=>{};renderContent=()=>{window._ppMark=true;const body=fieldsFor('deposit',cfg.assumptions.deposit_products[0],'assumptions.deposit_products.0');window._ppMark=false;document.getElementById('content').innerHTML='<div class="prd-card" data-fam="deposit" data-i="0"><div class="pp-sec" data-pp="setup">'+body+'</div></div>';lfgDecorate(document.querySelector('.prd-card'));};renderContent();},c);
  assert.strictEqual(await page.getByLabel('Deposit customer-count source').inputValue(),'accounts');
  await page.getByRole('group',{name:'Customer-count measure',exact:true}).getByRole('button',{name:'Period average',exact:true}).click();
  assert.strictEqual(await page.evaluate(()=>cfg.assumptions.deposit_products[0].balance_driver.measure),'period_average');
  const amount=page.locator('input[onchange*="balance_per_customer_spec"]').first();
  assert.strictEqual(await amount.inputValue(),'950');await amount.fill('1250');await amount.dispatchEvent('change');
  assert.strictEqual(await page.evaluate(()=>cfg.assumptions.deposit_products[0].balance_driver.balance_per_customer_spec.value),1250);
  for(const width of [1440,1024,768]){
   await page.setViewportSize({width,height:1000});
   for(const el of await page.locator('.lfx-s[data-lfg-key="deposit:0:balance"] select,.lfx-s[data-lfg-key="deposit:0:balance"] input').all()){
    const b=await el.boundingBox();if(b)assert(b.x>=0&&b.x+b.width<=width+1,'control overflow at '+width);
   }
  }
  await page.screenshot({path:'/tmp/r380-customer-deposit.png',fullPage:true});
  await page.evaluate(()=>{depositMode(0,'rollforward');depositMode(0,'linked_customer_level');});
  assert.strictEqual(await page.getByLabel('Deposit customer-count source').inputValue(),'accounts');
  assert.strictEqual(await amount.inputValue(),'1250');
  await page.evaluate(()=>{cfg.assumptions.cac_feeds.Renamed=cfg.assumptions.cac_feeds.Accounts;delete cfg.assumptions.cac_feeds.Accounts;renderContent();});
  assert((await page.getByLabel('Deposit customer-count source').innerText()).includes('Renamed'));
  assert.deepStrictEqual(errors,[]);console.log('PASS customer source/measure, raw dollars per customer, mode restoration, feed rename, 1440/1024/768 control containment, no runtime errors');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
