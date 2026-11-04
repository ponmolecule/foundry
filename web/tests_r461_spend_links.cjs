const {chromium}=require('playwright'),fs=require('fs'),assert=require('assert'),{execFileSync}=require('child_process');
(async()=>{
const fx=JSON.parse(execFileSync('python',['-c',`import json
from foundry.v2.tests_r461_spend_links import fixture
from foundry.v2.source_catalog import catalog
from foundry.v2.run_q import run_v2
c,st,sid,other=fixture();r=run_v2(c);st['cost']['params']={'factor_path':{'value':21624,'period':'month','trajectory':'flat'}}
print(json.dumps(dict(cfg=c,result=r,sources=catalog(c['assumptions']),sid=sid,other=other)))`],{encoding:'utf8',maxBuffer:1<<27}));
const html=fs.readFileSync('web/console_v2.html','utf8').replace('<script src="/web/rates_workspace.js"></script>','<script>'+fs.readFileSync('web/rates_workspace.js','utf8')+'</script>').replace('<head>','<head><script>window.V3=true;window.V31=true;</script>').replace(/renderTabs\(\);\nwhoami\(\)\.then[^\n]+/,'');
const browser=await chromium.launch({executablePath:process.env.FOUNDRY_CHROMIUM_PATH,args:['--no-sandbox'],headless:true});
try{
const page=await browser.newPage({viewport:{width:1500,height:1050}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
await page.route('**/*',r=>r.fulfill({status:200,json:{sources:fx.sources}}));await page.goto('http://foundry.test');await page.setContent(html);
await page.evaluate(f=>{cfg=normalizeCfg(f.cfg);lastRes=f.result;lastErrs=[];refresh=()=>{};scheduleAutosave=()=>{};window._stTab='costs';window.SNAPSHOT=false;let i=cfg.assumptions.obs_exposures.length-1;window._stSelObj=cfg.assumptions.obs_exposures[i].fee_streams[0];renderContent=()=>{document.getElementById('content').innerHTML=_feeStreamsSectionHtml('obs',cfg.assumptions.obs_exposures[i],'assumptions.obs_exposures.'+i,i)};renderContent();_calculatedInputs=JSON.stringify(cfg);_calculationState='idle';},fx);
await page.getByRole('button',{name:'+ Add linked source',exact:true}).click();await page.locator('#sourceCatalogSearch').fill('Digital');await page.locator('#sourceCatalogList button:enabled').click();
assert(await page.getByText('Allocation (%)',{exact:false}).count());
assert.equal(await page.evaluate(()=>cfg.assumptions.obs_exposures.at(-1).fee_streams[0].cost.params.factor_path),undefined);
await page.getByRole('button',{name:'+ Add linked source',exact:true}).click();await page.locator('#sourceCatalogSearch').fill('Other');await page.locator('#sourceCatalogList button:enabled').click();
const allocations=page.locator('input[onchange*="linked_sources"]');assert.equal(await allocations.count(),2);await allocations.nth(1).fill('25');await allocations.nth(1).dispatchEvent('change');
assert.equal(await page.evaluate(()=>cfg.assumptions.obs_exposures.at(-1).fee_streams[0].cost.params.linked_sources[1].share),.25);
await page.screenshot({path:'/tmp/r461-spend-links.png',fullPage:true});
await page.getByRole('button',{name:'Remove link',exact:true}).nth(1).click();assert.equal(await page.locator('input[onchange*="linked_sources"]').count(),1);
await page.getByRole('button',{name:'Remove link',exact:true}).click();assert(await page.getByText('Product cost ($000s)',{exact:true}).count());
assert.deepEqual(errors,[]);console.log('PASS linked-spend UI: catalog, amount replacement, two sources, allocation, removal, entered fallback; no browser errors');
}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
