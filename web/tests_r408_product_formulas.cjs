const {chromium}=require('playwright'),fs=require('fs'),assert=require('assert'),{execFileSync}=require('child_process');
(async()=>{
const data=JSON.parse(execFileSync('python3',['-c',"import json;from foundry.v2.tests_r408_product_formulas import config;from foundry.v2.source_catalog import catalog;c=config();print(json.dumps({'config':c,'sources':catalog(c['assumptions'])}))"],{encoding:'utf8'}));
const html=fs.readFileSync('web/console_v2.html','utf8').replace(/renderTabs\(\);\nwhoami\(\)\.then[^\n]+/,'');
const browser=await chromium.launch({executablePath:process.env.FOUNDRY_CHROMIUM_PATH,args:['--no-sandbox','--disable-gpu','--single-process','--no-zygote'],headless:true});
try{const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
await page.route('**/*',r=>{
 if(r.request().url().endsWith('/api/v2/product-cost-transfer')){
  const input=r.request().postData();
  try{const out=execFileSync('python3',['-c',"import sys,json;from foundry.v2.product_formula_costs import verified_move;b=json.load(sys.stdin);print(json.dumps(verified_move(b['config'],b['collection'],b['product_index'],b['category_id'],b['component_id'])))"],{input,encoding:'utf8'});return r.fulfill({json:JSON.parse(out)})}catch(e){return r.fulfill({status:422,json:{error:String(e.stderr||e.message)}})}
 }
 return r.fulfill({json:{}});
});await page.goto('http://foundry.test');await page.setContent(html);
await page.evaluate(({config,sources})=>{cfg=config;sourceCatalogRows=sources;refresh=()=>{};renderContent=()=>{const pi=cfg.assumptions.obs_exposures.length-1;window.testFi=pi;const p=cfg.assumptions.obs_exposures[pi];document.getElementById('content').innerHTML=_feeStreamsSectionHtml('obs',p,'assumptions.obs_exposures.'+pi,pi);prdAfterRender();};renderContent();},data);
await page.getByText('Move an existing Operating Expense formula',{exact:true}).click();const fi=await page.evaluate(()=>window.testFi);
await page.locator('#productFormulaMove_'+fi).selectOption(JSON.stringify(['agreement','fraud']));await page.getByRole('button',{name:'Move to this product',exact:true}).click();
await page.waitForFunction(()=>cfg.assumptions.obs_exposures.at(-1).fee_streams.length===1);
assert.strictEqual(await page.evaluate(()=>cfg.assumptions.nie_detail.categories[0].linked_components.length),1);
await page.evaluate(()=>renderContent());assert.strictEqual(await page.locator('.product-formula-editor').count(),1);
await page.locator('.product-formula-editor input[onchange*="nieCatFormulaEnteredValue"]').fill('0.2');await page.locator('.product-formula-editor input[onchange*="nieCatFormulaEnteredValue"]').dispatchEvent('change');
assert.strictEqual(await page.evaluate(()=>cfg.assumptions.obs_exposures.at(-1).fee_streams[0].cost.params.formula.factors[0].spec.value),.002);
// The moved formula edits its product owner, not the remaining Opex formula.
assert.strictEqual(await page.evaluate(()=>cfg.assumptions.nie_detail.categories[0].linked_components[0].factors[0].spec.value),.2);
await page.getByRole('button',{name:'+ Add / subtract item',exact:true}).click();assert.strictEqual(await page.evaluate(()=>cfg.assumptions.obs_exposures.at(-1).fee_streams[0].cost.params.formula.base_terms.length),3);
// Remove the intentionally incomplete extra base item before checking reload.
await page.evaluate(()=>{cfg.assumptions.obs_exposures.at(-1).fee_streams[0].cost.params.formula.base_terms.pop();cfg=JSON.parse(JSON.stringify(cfg));renderContent()});
for(const width of [1440,1024,768]){await page.setViewportSize({width,height:1200});const box=await page.locator('.product-formula-editor').boundingBox();assert(box&&box.width>0);for(const el of await page.locator('.product-formula-editor input,.product-formula-editor select').all()){const b=await el.boundingBox();if(b)assert(b.x>=0&&b.x+b.width<=width+1,'control overflow '+width)}}
await page.setViewportSize({width:1440,height:1400});await page.locator('.product-formula-editor').screenshot({path:'/tmp/r408-product-formula.png'});
assert.deepStrictEqual(errors,[]);console.log('PASS reconciled transfer, removal from Opex, product-targeted formula editing, add/subtract, reload, and responsive containment');
}finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
