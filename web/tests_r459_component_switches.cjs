const {chromium}=require('playwright'),fs=require('fs'),assert=require('assert'),{execFileSync}=require('child_process');
(async()=>{
const fx=JSON.parse(execFileSync('python',['-c',`import json
from foundry.v2.tests_fee_quantity_links import fixture
from foundry.v2.run_q import run_v2
c=fixture();print(json.dumps({'cfg':c,'result':run_v2(c)}))`],{encoding:'utf8',maxBuffer:1<<26}));
let html=fs.readFileSync('web/console_v2.html','utf8').replace('<script src="/web/rates_workspace.js"></script>','<script>'+fs.readFileSync('web/rates_workspace.js','utf8')+'</script>').replace('<head>','<head><script>window.V3=true;window.V31=true;</script>').replace(/renderTabs\(\);\nwhoami\(\)\.then[^\n]+/,'');
const browser=await chromium.launch({executablePath:process.env.FOUNDRY_CHROMIUM_PATH,args:['--no-sandbox'],headless:true});
try{
const page=await browser.newPage({viewport:{width:1600,height:1000}}),errors=[],dialogs=[];
page.on('pageerror',e=>errors.push(e.message));page.on('dialog',async d=>{dialogs.push(d.message());await d.accept();});
await page.route('**/*',r=>r.fulfill({status:200,json:{}}));await page.goto('http://foundry.test');await page.setContent(html);
await page.evaluate(f=>{cfg=normalizeCfg(f.cfg);lastRes=f.result;refresh=()=>{};scheduleAutosave=()=>{};document.body.classList.add('insp-closed');renderTabs();setTab('products');},fx);
await page.getByRole('button',{name:'Model inclusion',exact:false}).click();
assert(await page.locator('.sw-panel').innerText().then(t=>t.includes('Offering groups')));
const pidx=await page.evaluate(()=>swInventory().findIndex(r=>r.name==='Activity'&&r.kind==='obs_exposures'));
await page.evaluate(i=>swToggle(swInventory()[i].node),pidx);
assert(dialogs.some(x=>x.includes('Migrated')),'dependents listed before disabling source');
assert(await page.evaluate(()=>!swStates().rows.find(x=>x.name==='TPV').on));
const snapshot=await page.evaluate(()=>JSON.stringify(cfg));await page.evaluate(()=>renderContent());assert.equal(await page.evaluate(()=>JSON.stringify(cfg)),snapshot,'render is read-only');
await page.evaluate(i=>swToggle(swInventory()[i].node),pidx);
assert(await page.evaluate(()=>swStates().rows.find(x=>x.name==='TPV').on));
await page.getByLabel('New offering group').fill('Offering');await page.getByRole('button',{name:'Add group',exact:true}).click();
await page.evaluate(()=>{const r=swInventory().find(x=>x.name==='Activity'&&x.kind==='obs_exposures');swGroupMember(0,r.id,true);swGroupToggle(0);});
assert(await page.evaluate(()=>!swStates().rows.find(x=>x.name==='TPV').on));
await page.evaluate(()=>swGroupToggle(0));
await page.evaluate(()=>{const r=swInventory().find(x=>x.name==='TPV');swToggle(r.node);});
assert(await page.evaluate(()=>swStates().rows.find(x=>x.name==='Activity').on));
await page.evaluate(()=>{window._prdSel=cfg.assumptions.obs_exposures[1];window._prdView='product';window._prdTab='streams';renderContent();});
assert(await page.getByRole('switch',{name:'Include Activity',exact:true}).count());
assert(await page.getByRole('switch',{name:'Include TPV',exact:true}).count());
await page.screenshot({path:'/tmp/r459-switches-ui.png',fullPage:true});
assert.deepStrictEqual(errors,[]);console.log('PASS product/stream toggles, dependency preview, stable render, groups, restored state and browser errors');
}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
