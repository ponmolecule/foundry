const {chromium}=require('playwright'),fs=require('fs'),assert=require('assert'),{execFileSync}=require('child_process');
(async()=>{
const c=JSON.parse(execFileSync('python3',['-c','import json;from foundry.v2.tests_r386_reuse import setup,attach_formula;print(json.dumps(attach_formula(setup())))'],{encoding:'utf8'}));
const sources=JSON.parse(execFileSync('python3',['-c','import json;from foundry.v2.tests_r386_reuse import setup,attach_formula;from foundry.v2.source_catalog import catalog;print(json.dumps(catalog(attach_formula(setup())["assumptions"])))'],{encoding:'utf8'}));
const html=fs.readFileSync('web/console_v2.html','utf8').replace(/renderTabs\(\);\nwhoami\(\)\.then[^\n]+/,'');
const browser=await chromium.launch({executablePath:process.env.FOUNDRY_CHROMIUM_PATH,args:['--no-sandbox','--disable-gpu','--single-process','--no-zygote'],headless:true});
try{const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));await page.route('**/*',r=>r.fulfill({json:r.request().url().includes('source-catalog')?{sources}:{}}));await page.goto('http://foundry.test');await page.setContent(html);
await page.evaluate(c=>{cfg=c;refresh=()=>{};window.testIndex=0;renderContent=()=>{const i=window.testIndex,p=cfg.assumptions.deposit_products[i];window._ppMark=true;const h=fieldsFor('deposit',p,'assumptions.deposit_products.'+i);window._ppMark=false;document.getElementById('content').innerHTML='<div class="cfg-stage"><div class="prd-card" data-fam="deposit" data-i="'+i+'"><div class="pp-sec" data-pp="setup">'+h+'</div></div>'+_opexFormulaDriverEditorHtml(0,0,cfg.assumptions.nie_detail.categories[0].linked_components[0])+'</div>';lfgDecorate(document.querySelector('.prd-card'));const b=document.querySelector('[data-lfg-key="deposit:'+i+':balance"]');if(b){b.classList.remove('c');const body=b.querySelector('.lfx-b');if(body)body.hidden=false;}};renderContent();},c);
assert.strictEqual(await page.getByLabel('Breakdown label',{exact:true}).count(),4);
assert.strictEqual(await page.getByRole('button',{name:/Create weighted assumption/}).count(),0);
await page.getByLabel('Breakdown label',{exact:true}).first().fill('Small customers');await page.getByLabel('Breakdown label',{exact:true}).first().press('Tab');
assert.strictEqual(await page.evaluate(()=>cfg.assumptions.deposit_products[0].balance_driver.balance_per_customer_spec.components[0].name),'Small customers');
await page.getByRole('button',{name:'+ Add row',exact:true}).click();assert.strictEqual(await page.getByLabel('Breakdown label',{exact:true}).count(),5);
await page.evaluate(()=>depositAmountComponent(0,4));
await page.evaluate(()=>{window.testIndex=1;renderContent();});
assert.strictEqual(await page.getByLabel('Linked deposit amount source',{exact:true}).inputValue(),'0');
await page.evaluate(()=>depositAmountLink(1,'0'));assert.strictEqual(await page.evaluate(()=>cfg.assumptions.deposit_products[1].balance_driver.balance_per_customer_spec.series_id),'part-a');
// Switching amount method retains inactive inputs through a saved/reloaded config.
await page.evaluate(()=>{depositAmountMethod(0,'entered');cfg=JSON.parse(JSON.stringify(cfg));depositAmountMethod(0,'weighted_sum');});
assert.strictEqual(await page.evaluate(()=>cfg.assumptions.deposit_products[0].balance_driver.balance_per_customer_spec.components[0].name),'Small customers');
// The existing Formula control owns the flat add/subtract items; no expression-tree editor exists.
assert.strictEqual(await page.locator('.formula-base-item').count(),4);
assert.strictEqual(await page.locator('.linked-calc-node').count(),0);
await page.getByLabel('Base item sign',{exact:true}).nth(2).selectOption('-1');
await page.getByLabel('Base balance measure',{exact:true}).first().selectOption('period_average');
await page.getByLabel('Base rate source',{exact:true}).first().selectOption('prime');
assert.strictEqual(await page.evaluate(()=>cfg.assumptions.nie_detail.categories[0].linked_components[0].base_terms[0].factors[1].series_id),'prime');
await page.getByLabel('Base rate source',{exact:true}).first().selectOption('none');
assert.strictEqual(await page.evaluate(()=>cfg.assumptions.nie_detail.categories[0].linked_components[0].base_terms[0].factors.length),1);
await page.getByLabel('Base rate source',{exact:true}).first().selectOption('effr');
await page.getByRole('button',{name:'Select / change source',exact:true}).nth(2).click();
await page.locator('#sourceCatalogList button').filter({hasText:'Deposit › Deposit portion A › Interest expense'}).click();
assert.strictEqual(await page.evaluate(()=>cfg.assumptions.nie_detail.categories[0].linked_components[0].base_terms[2].factors[0].source),'deposit_interest');
await page.getByRole('button',{name:'+ Add / subtract item',exact:true}).click();assert.strictEqual(await page.locator('.formula-base-item').count(),5);
await page.evaluate(()=>{cfg.assumptions.nie_detail.categories[0].linked_components[0].base_terms.pop();renderContent();});
await page.getByLabel('Zero acquisition denominator',{exact:true}).selectOption('error');
assert.strictEqual(await page.evaluate(()=>cfg.assumptions.nie_detail.categories[0].linked_components[0].factors[1].zero_denominator),'error');
for(const width of [1440,1024,768]){await page.setViewportSize({width,height:1100});await page.evaluate(()=>{if(typeof fitControls==='function')fitControls();});for(const el of await page.locator('.deposit-local-amount input,.deposit-local-amount select,.deposit-local-amount button,.formula-base-editor input,.formula-base-editor select,.formula-base-editor button').all()){const b=await el.boundingBox();if(b)assert(b.x>=0&&b.x+b.width<=width+1,'control overflow at '+width+': '+await el.evaluate(x=>x.outerHTML));}if(width===1440)await page.locator('.formula-base-editor').screenshot({path:'/tmp/r386-formula.png'});}
await page.evaluate(()=>{window.testIndex=0;renderContent();});await page.setViewportSize({width:1440,height:1100});await page.locator('.deposit-local-amount').screenshot({path:'/tmp/r386-balance.png'});
assert.deepStrictEqual(errors,[]);console.log('PASS local breakdown, live link, existing Formula base edits, source-catalog actual interest selection, linked rate, acquisition zero policy, grouped 1440/1024/768 layout');
}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
