const {chromium}=require('playwright'),fs=require('fs'),assert=require('assert'),{execFileSync}=require('child_process');
(async()=>{
 const c=JSON.parse(execFileSync('python3',['-c','import json;from foundry.v2.tests_r380_customer_deposits import config;print(json.dumps(config()))'],{encoding:'utf8'}));
 const html=fs.readFileSync('web/console_v2.html','utf8').replace(/renderTabs\(\);\nwhoami\(\)\.then[^\n]+/,'');
 const browser=await chromium.launch({executablePath:process.env.FOUNDRY_CHROMIUM_PATH,args:['--no-sandbox','--disable-gpu','--single-process','--no-zygote'],headless:true});
 try{
 const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));await page.route('**/*',r=>r.fulfill({json:{}}));await page.goto('http://foundry.test');await page.setContent(html);
 await page.evaluate(c=>{cfg=c;Object.assign(cfg.assumptions.deposit_products[0],{rate_type:'float',index:'effr',index_spread:0,deposit_beta:.5});refresh=()=>{};renderContent=()=>{window._ppMark=true;let b=fieldsFor('deposit',cfg.assumptions.deposit_products[0],'assumptions.deposit_products.0');window._ppMark=false;const p=cfg.assumptions.deposit_products[0],base='assumptions.deposit_products.0';b='<div class="fld"><label>Rate type</label><select onchange="setPath(\''+base+'.rate_type\',this.value)"><option value="fixed">Fixed</option><option value="float" selected>Floating (index + spread)</option></select></div>'+(p.rate_type==='float'?'<div class="fld"><label>Reference index</label><select onchange="setPath(\''+base+'.index\',this.value)"><option>sofr</option><option selected>effr</option><option>prime</option></select></div>':'')+b;document.getElementById('content').innerHTML='<div class="prd-card" data-fam="deposit" data-i="0"><div class="pp-sec" data-pp="setup">'+b+'</div></div>';lfgDecorate(document.querySelector('.prd-card'));};renderContent();},c);
await page.evaluate(()=>{if(typeof _lnvActive!=='undefined'){_lnvActive.set(cfg.assumptions.deposit_products[0],'pricing');renderContent();}});   // r392: the rail shows one section; open Pricing
 const pricing=page.locator('[data-lfg-key="deposit:0:pricing"]');
 const labels=await pricing.locator('.lfx-f>label').allTextContents();
 assert.deepStrictEqual(labels.slice(0,7),['Rate type','Reference index','Index beta','Spread over EFFR','Rate floor','Rate cap','Interest balance measure']);
 assert(!(await page.evaluate(()=>cfg.assumptions.deposit_products[0].minimum_interest_expense)));
 await page.getByRole('button',{name:'+ Minimum interest expense',exact:true}).click();
 const amount=page.locator('input[onchange*="minimum_interest_expense.amount_spec"]').first();await amount.fill('30');await amount.dispatchEvent('change');
 assert.strictEqual(await page.evaluate(()=>cfg.assumptions.deposit_products[0].minimum_interest_expense.amount_spec.value),30000);
 await page.getByLabel('Minimum interest expense amount period',{exact:true}).selectOption('year');assert.strictEqual(await page.evaluate(()=>cfg.assumptions.deposit_products[0].minimum_interest_expense.period),'year');await page.getByLabel('Minimum interest expense amount period',{exact:true}).selectOption('month');
 for(const width of [1440,1024,768]){await page.setViewportSize({width,height:1100});for(const el of await pricing.locator('input,select,button').all()){const b=await el.boundingBox();if(b)assert(b.x>=0&&b.x+b.width<=width+1,'pricing overflow at '+width);}if(width===1440)await pricing.screenshot({path:'/tmp/r381-deposit-pricing.png'});}
 await page.getByRole('button',{name:'Remove minimum',exact:true}).click();assert(!(await page.evaluate(()=>cfg.assumptions.deposit_products[0].minimum_interest_expense)));
 // The same section also renders the fixed-rate branch and preserves authored pricing.
 await page.evaluate(()=>{cfg.assumptions.deposit_products[0].rate_type='fixed';cfg.assumptions.deposit_products[0].rate_paid_ann=.02;renderContent();});assert(await pricing.getByText('Rate paid (annual %)',{exact:true}).isVisible());
 await page.evaluate(()=>{const f={driver:'formula_driver',name:'Deposit fraud',factors:[{kind:'linked',source:'catalog_quantity',series_id:'balance',name:'Ending deposits'},{kind:'entered',name:'Annual fraud rate',op:'multiply',display:'percent',rate_period:'year',spec:{source:'entered',trajectory:'flat',value:.001}}]};cfg.assumptions.nie_detail={categories:[{name:'Fraud',linked_components:[f]}]};document.getElementById('content').innerHTML=_opexFormulaDriverEditorHtml(0,0,f);});
 for(const width of [1440,1024,768]){await page.setViewportSize({width,height:900});const b=await page.getByLabel('Expense accrual',{exact:true}).boundingBox();assert(b&&b.width<=321&&b.x>=0&&b.x+b.width<=width+1);}
 assert.deepStrictEqual(errors,[]);console.log('PASS logical pricing order, optional minimum enable/remove, $000s storage conversion, amount period, fixed/floating views, 1440/1024/768 containment and compact expense accrual');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
