const {chromium}=require('playwright'),fs=require('fs'),assert=require('assert'),{execFileSync}=require('child_process');
(async()=>{
const fx=JSON.parse(execFileSync('python',['-c',`import json
from foundry.v2.tests_r461_spend_links import fixture
from foundry.v2.source_catalog import catalog
from foundry.v2.run_q import run_v2
c,st,sid,other=fixture();c['assumptions']['cac_feeds']['Accounts']['channels'][0]['name']='Digital Sourced Practices';r=run_v2(c);st['cost']['params']={'factor_path':{'value':21624,'period':'month','trajectory':'flat'}}
print(json.dumps(dict(cfg=c,result=r,sources=catalog(c['assumptions']),sid=sid,other=other)))`],{encoding:'utf8',maxBuffer:1<<27}));
const html=fs.readFileSync('web/console_v2.html','utf8').replace('<script src="/web/rates_workspace.js"></script>','<script>'+fs.readFileSync('web/rates_workspace.js','utf8')+'</script>').replace('<head>','<head><script>window.V3=true;window.V31=true;</script>').replace(/renderTabs\(\);\nwhoami\(\)\.then[^\n]+/,'');
const browser=await chromium.launch({executablePath:process.env.FOUNDRY_CHROMIUM_PATH,args:['--no-sandbox'],headless:true});
try{
const page=await browser.newPage({viewport:{width:1500,height:1050}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
await page.route('**/*',r=>r.fulfill({status:200,json:{sources:fx.sources}}));await page.goto('http://foundry.test');await page.setContent(html);
await page.evaluate(f=>{cfg=normalizeCfg(f.cfg);lastRes=f.result;lastErrs=[];refresh=()=>{};scheduleAutosave=()=>{};window._stTab='costs';window.SNAPSHOT=false;let i=cfg.assumptions.obs_exposures.length-1;window._stSelObj=cfg.assumptions.obs_exposures[i].fee_streams[0];renderContent=()=>{document.getElementById('content').innerHTML=_feeStreamsSectionHtml('obs',cfg.assumptions.obs_exposures[i],'assumptions.obs_exposures.'+i,i)};renderContent();_calculatedInputs=JSON.stringify(cfg);_calculationState='idle';},fx);
await page.getByRole('button',{name:'+ Add linked source',exact:true}).click();await page.locator('#sourceCatalogSearch').fill('Digital');await page.locator('#sourceCatalogList button:enabled').click();
assert(await page.getByText('Allocation',{exact:true}).count());
assert.equal(await page.evaluate(()=>cfg.assumptions.obs_exposures.at(-1).fee_streams[0].cost.params.factor_path),undefined);
await page.getByRole('button',{name:'+ Add linked source',exact:true}).click();await page.locator('#sourceCatalogSearch').fill('Other');await page.locator('#sourceCatalogList button:enabled').click();
const allocations=page.locator('input[onchange*="linked_sources"]');assert.equal(await allocations.count(),2);await allocations.nth(1).fill('25');await allocations.nth(1).dispatchEvent('change');
assert.equal(await page.evaluate(()=>cfg.assumptions.obs_exposures.at(-1).fee_streams[0].cost.params.linked_sources[1].share),.25);
await page.locator('.spend-links').screenshot({path:'/tmp/r462-spend-links.png'});
const layout=await page.locator('.spend-source').first().evaluate(el=>{const row=el.getBoundingClientRect(),name=el.querySelector('.spend-source-name').getBoundingClientRect(),input=el.querySelector('input').getBoundingClientRect(),button=el.querySelector('button'),color=getComputedStyle(button).color;return {row:row.width,name:name.width,input:input.width,gap:input.left-name.right,color,overflow:el.scrollWidth>el.clientWidth}});
assert(layout.name>150);assert(layout.input<=110);assert(layout.gap>=10);assert(!layout.overflow);assert.notEqual(layout.color,'rgb(205, 205, 202)');
await page.evaluate(()=>{const preview=document.createElement('div');preview.id='spendNarrowPreview';preview.className='lfx-st';preview.style='position:fixed;inset:0;z-index:999999;background:white;padding:20px;width:380px;box-sizing:content-box';preview.innerHTML='<div class="lfx-sted"><div style="container-type:inline-size;width:360px"><div class="st-body">'+document.querySelector('.spend-links').outerHTML+'</div></div></div>';document.body.appendChild(preview)});
const narrow=page.locator('#spendNarrowPreview .spend-links');assert.equal(await narrow.evaluate(el=>el.scrollWidth>el.clientWidth),false);
await narrow.screenshot({path:'/tmp/r462-spend-links-narrow.png'});
await page.evaluate(()=>document.getElementById('spendNarrowPreview').remove());
await page.getByRole('button',{name:'Remove link',exact:true}).nth(1).click();assert.equal(await page.locator('input[onchange*="linked_sources"]').count(),1);
await page.getByRole('button',{name:'Remove link',exact:true}).click();assert(await page.getByText('Product cost ($000s)',{exact:true}).count());
assert.deepEqual(errors,[]);console.log('PASS linked-spend UI: catalog, amount replacement, two sources, allocation, removal, entered fallback; no browser errors');
}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
