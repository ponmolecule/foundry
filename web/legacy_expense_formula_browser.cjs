const {chromium}=require('playwright'),fs=require('fs'),path=require('path'),assert=require('assert'),{execFileSync}=require('child_process');
const repo=path.resolve(__dirname,'..');
(async()=>{
const html=fs.readFileSync(path.join(repo,'web/console_v2.html'),'utf8').replace('renderTabs();\nwhoami().then(u=>{ paintWho(); if(u){ boot(); } else { currentTab = "welcome"; renderContent(); } });','');
const cfg=JSON.parse(execFileSync('python3',['-c','import json;from foundry.v2.tests_source_catalog import setup;print(json.dumps(setup()))'],{cwd:repo}));
const browser=await chromium.launch({executablePath:process.env.FOUNDRY_CHROMIUM_PATH,args:['--no-sandbox','--disable-gpu','--single-process','--no-zygote'],headless:true});
const page=await browser.newPage({viewport:{width:1440,height:1000}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
await page.route('**/*',r=>{if(r.request().url().includes('/source-catalog'))return r.fulfill({status:200,contentType:'application/json',body:execFileSync('python3',['-c',"import sys,json;from foundry.v2.source_catalog import catalog;p=json.load(sys.stdin);print(json.dumps({'sources':catalog((p.get('config') or p)['assumptions'])}))"],{cwd:repo,input:r.request().postData()})});return r.fulfill({status:200,body:'{}',contentType:'application/json'});});
await page.goto('http://foundry.test');await page.setContent(html);await page.evaluate(c=>{cfg=c;refresh=()=>{};scheduleAutosave=()=>{};_renderContentBody=()=>{const x=cfg.assumptions.nie_detail.categories[0].linked_components[0];document.getElementById('content').innerHTML=_opexFormulaDriverEditorHtml(0,0,_isLegacyLinkedExpense(x)?_legacyLinkedFormulaView(x):x)};},cfg);
const cases=['fee_income','gain_on_sale','servicing_net','noninterest_income','net_fee_income','fee_stream_quantity','customer_acquisition_auc','workforce_count'].map(driver=>({driver,series_id:driver==='workforce_count'?'wf':driver==='customer_acquisition_auc'?'auc':'qty',rate_spec:{source:'entered',trajectory:'flat',value:.015},amount_spec:{trajectory:'growth',value:120,period:'year',growth_spec:{rate:.1,period:'year',method:'step'}},measure:'period_average',rate_period:'year'}));
const pairs=[];
for(const old of cases){
 await page.evaluate(x=>{cfg.assumptions.nie_detail.categories[0].linked_components=[x];window._fxOpen={};renderContent();},old);
 assert.deepStrictEqual(await page.evaluate(()=>cfg.assumptions.nie_detail.categories[0].linked_components[0]),old,'render mutated legacy component');
 assert.strictEqual(await page.locator('.fx-chip').textContent(),'Formula');assert.strictEqual(await page.getByText('Browse / search',{exact:true}).count(),1);
 await page.locator('.fx-head b').textContent();
 await page.evaluate(()=>nieCatFormulaName(0,0,'Renamed expense'));
 const promoted=await page.evaluate(()=>cfg.assumptions.nie_detail.categories[0].linked_components[0]);assert.strictEqual(promoted.driver,'formula_driver');pairs.push({old,promoted});
 if(old.driver==='workforce_count'){
   await page.evaluate(()=>renderContent());await page.locator('.fx-num input').fill('240');await page.locator('.fx-num input').dispatchEvent('change');
   assert.strictEqual(await page.evaluate(()=>cfg.assumptions.nie_detail.categories[0].linked_components[0].factors[1].spec.value),240);
 }
 if(old.driver==='customer_acquisition_auc'){
   await page.evaluate(()=>renderContent());assert.strictEqual(await page.locator('.fx-time select').inputValue(),'year');
   await page.locator('.fx-time select').selectOption('quarter');assert.strictEqual(await page.evaluate(()=>cfg.assumptions.nie_detail.categories[0].linked_components[0].factors[1].rate_period),'quarter');
   await page.evaluate(()=>nieCatFormulaAddEnteredFactor(0,0));assert.strictEqual(await page.evaluate(()=>cfg.assumptions.nie_detail.categories[0].linked_components[0].accrual_cadence),'monthly');
 }
}
execFileSync('python3',['-c',`import json,sys
from foundry.v2.opex_extensions import resolve_linked_components,linked_component_amount
pairs=json.load(sys.stdin)
for ppy in (12,4):
 m={'periods_per_year':ppy,'fee_income':1200,'gain_on_sale':200,'servicing_net':300,'fee_product_costs':100,'fee_stream_quantities':{'qty':1234},'workforce_count':{'wf':7},'customer_acquisition_auc_beginning':{'auc':100},'customer_acquisition_auc_monthly':{'auc':[100*(i+2) for i in range(12)]}}
 for pair in pairs:
  a=resolve_linked_components({'linked_components':[pair['old']]},ppy,ppy)[0];b=resolve_linked_components({'linked_components':[pair['promoted']]},ppy,ppy)[0]
  assert [linked_component_amount(a,i,m) for i in range(ppy)]==[linked_component_amount(b,i,m) for i in range(ppy)],pair
print('PASS browser-created promotions preserve monthly/quarterly economics')`],{cwd:repo,input:JSON.stringify(pairs),stdio:['pipe','inherit','inherit']});
// Browse from an unedited legacy component promotes only upon choosing a source.
await page.evaluate(()=>{cfg.assumptions.nie_detail.categories[0].linked_components=[{driver:'fee_income',rate_spec:{source:'entered',trajectory:'flat',value:.015}}];renderContent();});
await page.getByText('Browse / search',{exact:true}).click();await page.locator('#sourceCatalogSearch').fill('Retained on-book');await page.locator('#sourceCatalogList button').click();assert.strictEqual(await page.evaluate(()=>cfg.assumptions.nie_detail.categories[0].linked_components[0].factors[0].series_id),'deposit_pool.pool.retainedBalance');
if(process.env.FOUNDRY_EXPENSE_SCREENSHOT)await page.screenshot({path:process.env.FOUNDRY_EXPENSE_SCREENSHOT});
assert.deepStrictEqual(errors,[]);console.log('PASS all legacy types use Formula + Browse; render is inert; rename, workforce growth edit, balance-rate period and source selection');await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
