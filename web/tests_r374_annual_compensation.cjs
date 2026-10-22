const {chromium}=require('playwright'),fs=require('fs'),assert=require('assert'),{execFileSync}=require('child_process');
(async()=>{
const html=fs.readFileSync('web/console_v2.html','utf8').replace(/renderTabs\(\);\nwhoami\(\)\.then[^\n]+/,'');
const fixture=JSON.parse(execFileSync('python3',['-c','import json;from foundry.v2.tests_r374_annual_compensation import config;from foundry.v2.engine_q_a import run_pf_a;c=config();print(json.dumps({"cfg":c,"result":run_pf_a(c)}))'],{encoding:'utf8'}));
const browser=await chromium.launch({executablePath:process.env.FOUNDRY_CHROMIUM_PATH,args:['--no-sandbox','--disable-gpu','--single-process','--no-zygote'],headless:true});
try{
const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));await page.route('**/*',r=>r.fulfill({status:200,json:{}}));await page.goto('http://foundry.test');await page.setContent(html);
await page.evaluate(f=>{cfg=f.cfg;lastRes=f.result;window.V3=true;window.V31=true;refresh=()=>{};scheduleAutosave=()=>{};renderContent=()=>{document.getElementById('content').innerHTML='<div class="cfg-stage"><div class="cfg-md-detail wf-pool-detail-card" style="max-width:940px;margin:20px auto;padding:12px"><div class="cfg-md-body"><div class="wf-pools wf-pool-detail">'+_workforcePiecewiseEditorHtml(cfg.assumptions.nie_detail.workforce.additive_components[0],0)+'</div></div></div></div>';};renderContent();},fixture);
for(const width of [1440,1024,768]){
 await page.setViewportSize({width,height:1000});
 const report=await page.evaluate(()=>{const root=document.querySelector('.opex-piecewise-card'),rect=root.getBoundingClientRect();const bad=[];for(const e of root.querySelectorAll('input,select,button')){if(!e.getClientRects().length)continue;const r=e.getBoundingClientRect();if(r.left<rect.left-2||r.right>rect.right+2)bad.push(e.outerHTML.slice(0,80));}return {bad,overflow:document.documentElement.scrollWidth>innerWidth+2};});assert.deepStrictEqual(report.bad,[],width+' controls overflow');assert(!report.overflow,width+' page overflow');
}
await page.setViewportSize({width:1440,height:1000});await page.screenshot({path:'/tmp/r374-annual-pool.png',fullPage:true});
assert.strictEqual(await page.locator('.wf-floor-roles input:checked').count(),6);
// Links use stable IDs after rename/reorder; changing a selection changes the authored model.
await page.evaluate(()=>{const w=cfg.assumptions.nie_detail.workforce;w.roles.reverse();w.roles.find(r=>r.series_id==='role-0').role='Renamed leader';renderContent();});
const renamed=page.locator('.wf-floor-roles label').filter({hasText:'Renamed leader'}).locator('input');await renamed.uncheck();assert(await page.evaluate(()=>!cfg.assumptions.nie_detail.workforce.additive_components[0].salary_floor.role_series_ids.includes('role-0')));
await page.locator('.wf-pool-calculation summary').click();assert((await page.locator('.wf-pool-calculation').innerText()).includes('1,000'));
// Only the existing event controls are used for old components; annual mode is opt-in.
await page.evaluate(()=>{const c=cfg.assumptions.nie_detail.workforce.additive_components[0];delete c.salary_floor;delete c.allocation;delete c.payroll_load_rate;renderContent();});
assert.strictEqual(await page.locator('[aria-label="Compensation recognition"]').inputValue(),'event');assert.strictEqual(await page.locator('.wf-floor-roles').count(),0);assert((await page.locator('.opex-piecewise-card').textContent()).includes('First event model period'));
await page.selectOption('[aria-label="Compensation recognition"]','model_year_equal');assert(!(await page.locator('.opex-piecewise-card').innerText()).includes('First event model period'));
await page.selectOption('[aria-label="Compensation recognition"]','event');assert((await page.locator('.opex-piecewise-card').textContent()).includes('First event model period'));
assert.deepStrictEqual(errors,[]);console.log('PASS annual/event pool UI, 1440/1024/768px control containment, stable role links after rename/reorder, selection editing, collapsed calculations, reversible opt-in and no browser errors');
}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
