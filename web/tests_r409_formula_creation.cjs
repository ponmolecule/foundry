const {chromium}=require('playwright'),fs=require('fs'),assert=require('assert'),{execFileSync}=require('child_process');
(async()=>{
const data=JSON.parse(execFileSync('python3',['-c',"import json;from foundry.v2.tests_r408_product_formulas import config;from foundry.v2.source_catalog import catalog;c=config();print(json.dumps({'config':c,'sources':catalog(c['assumptions'])}))"],{encoding:'utf8'}));
const html=fs.readFileSync('web/console_v2.html','utf8').replace('<head>','<head><script>window.V31=true;window.V3=true;</script>').replace(/renderTabs\(\);\nwhoami\(\)\.then[^\n]+/,'');
const browser=await chromium.launch({executablePath:process.env.FOUNDRY_CHROMIUM_PATH,args:['--no-sandbox','--disable-gpu','--single-process','--no-zygote'],headless:true});
try{const page=await browser.newPage({viewport:{width:1440,height:1100}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
await page.route('**/*',r=>{
 if(r.request().url().endsWith('/api/v2/product-cost-transfer')){
  try{const out=execFileSync('python3',['-c',"import sys,json;from foundry.v2.product_formula_costs import verified_move;b=json.load(sys.stdin);print(json.dumps(verified_move(b['config'],b['collection'],b['product_index'],b['category_id'],b['component_id'])))"],{input:r.request().postData(),encoding:'utf8'});return r.fulfill({json:JSON.parse(out)})}catch(e){return r.fulfill({status:422,json:{error:String(e.stderr||e.message)}})}
 }
 return r.fulfill({json:{}});
});await page.goto('http://foundry.test');await page.setContent(html);
await page.evaluate(({config,sources})=>{cfg=config;sourceCatalogRows=sources;sourceCatalogKey=_sourceCatalogKey();refresh=()=>{};currentTab='products';lastRes=null;lastErrs=[];window.testFi=cfg.assumptions.obs_exposures.length-1;const owner=_stOwner(window.testFi);window._prdSel=owner;window._prdView='product';window._prdTab='streams';window._prdSeen=new WeakSet(allProducts().map(x=>x.p));window._prdSeenInit=true;renderContent();},data);
const signature=await page.evaluate(()=>JSON.stringify(cfg));
await page.getByRole('button',{name:'+ Formula cost stream',exact:true}).click();
const dlg=page.getByRole('dialog',{name:'New formula cost stream'});
assert(await dlg.isVisible());assert(await dlg.getByRole('button',{name:'Create stream',exact:true}).isDisabled());
assert.strictEqual(await page.evaluate(()=>JSON.stringify(cfg)),signature);
await dlg.getByRole('button',{name:'Cancel',exact:true}).click();assert.strictEqual(await page.evaluate(()=>JSON.stringify(cfg)),signature);
await page.getByRole('button',{name:'+ Formula cost stream',exact:true}).click();await dlg.getByLabel('Stream name',{exact:true}).fill('   ');assert(await dlg.getByRole('button',{name:'Create stream',exact:true}).isDisabled());await page.keyboard.press('Escape');assert.strictEqual(await page.evaluate(()=>JSON.stringify(cfg)),signature);
await page.getByRole('button',{name:'+ Formula cost stream',exact:true}).click();await dlg.getByLabel('Stream name',{exact:true}).fill('Named formula cost');await dlg.getByRole('button',{name:'Create stream',exact:true}).click();
assert.deepStrictEqual(await page.evaluate(()=>_stOwner(testFi).fee_streams.map(s=>s.name)),['Named formula cost']);
for(let j=0;j<3;j++){await page.evaluate(()=>renderContent());assert(await page.evaluate(()=>window._prdSel===_stOwner(testFi)&&window._prdTab==='streams'&&window._stSelObj===_stOwner(testFi).fee_streams[0]));}
await page.getByRole('button',{name:'+ Formula cost stream',exact:true}).click();await dlg.getByLabel('Stream name',{exact:true}).fill('Named formula cost');await dlg.getByRole('button',{name:'Create stream',exact:true}).click();assert(await dlg.getByRole('alert').isVisible());assert.strictEqual(await page.evaluate(()=>_stOwner(testFi).fee_streams.length),1);await dlg.getByRole('button',{name:'Cancel',exact:true}).click();
// Exercise the real product navigator after the API replaces every config object.
await page.getByText('Move an existing Operating Expense formula',{exact:true}).click();const fi=await page.evaluate(()=>testFi);await page.locator('#productFormulaMove_'+fi).selectOption(JSON.stringify(['agreement','fraud']));await page.getByRole('button',{name:'Move to this product',exact:true}).click();
await page.waitForFunction(()=>!window._productFormulaMoveBusy&&_stOwner(testFi).fee_streams.length===2);
for(let j=0;j<3;j++){await page.evaluate(()=>renderContent());assert(await page.evaluate(()=>window._prdSel===_stOwner(testFi)&&window._prdTab==='streams'&&window._stSelObj===_stOwner(testFi).fee_streams[1]));}
assert(await page.locator('.product-formula-editor').isVisible());assert.deepStrictEqual(errors,[]);console.log('PASS cancel/Escape/blank create no model mutation; named creation creates one stream; real product navigator stays on the selected product and cost stream after create, transfer, and rerenders');
}finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
