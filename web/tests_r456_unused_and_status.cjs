// r437: Configuration editors on the field system: workforce populations and expense categories on one label column
// with each path beside its value (segmented, driving the existing selects), other income lines, and capital raises /
// borrowings as small tables. Rendering leaves the configuration alone; every control still writes its own field.
const {chromium}=require('playwright'),fs=require('fs'),assert=require('assert'),{execFileSync}=require('child_process');
(async()=>{
const fx=JSON.parse(execFileSync('python3',['-c',`import json
from foundry.v2.run_q import run_v2
c=json.load(open('foundry/fixtures/universal_template_bank.json'))
print(json.dumps({'cfg':c,'result':run_v2(c)}))`],{encoding:'utf8',maxBuffer:1<<28}));
const html=fs.readFileSync('web/console_v2.html','utf8').replace('<script src="/web/rates_workspace.js"></script>','<script>'+fs.readFileSync('web/rates_workspace.js','utf8')+'</script>').replace('<head>','<head><script>window.V3=true;window.V31=true;</script>').replace(/renderTabs\(\);\nwhoami\(\)\.then[^\n]+/,'');
const browser=await chromium.launch({executablePath:process.env.FOUNDRY_CHROMIUM_PATH,args:['--no-sandbox','--disable-gpu','--single-process','--no-zygote'],headless:true});
try{
const page=await browser.newPage({viewport:{width:1600,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>d.dismiss());page.setDefaultTimeout(15000);
await page.route('**/*',r=>r.fulfill({status:200,json:{}}));await page.goto('http://foundry.test');await page.setContent(html);
await page.evaluate(f=>{cfg=normalizeCfg(f.cfg);lastRes=f.result;refresh=()=>{};scheduleAutosave=()=>{};document.body.classList.add('insp-closed');renderTabs();setTab('config');},fx);
const settle=()=>page.waitForTimeout(100);
const mod=async m=>{await page.evaluate(m=>document.querySelector('.cfg-mod[data-cfg-mod="'+m+'"]').click(),m);await settle();};
const vis=sel=>page.locator(sel).filter({visible:true});


await page.evaluate(()=>{
 const p=cfg.assumptions.lending_products[0];
 document.getElementById('content').innerHTML='<div id="loan-test"></div>';
 renderContent=()=>{const host=document.getElementById('loan-test');host.innerHTML=prodCardHtml('lending',0);const card=host.firstElementChild;card.dataset.fam='lending';card.dataset.i='0';card.querySelector('.fields').classList.remove('hidden');lfgDecorate(card);};renderContent();
});
await page.getByRole('group',{name:'Unused commitment reserve',exact:true}).getByRole('button',{name:'On',exact:true}).click();
assert.equal(await page.evaluate(()=>cfg.assumptions.lending_products[0].unused_commitment_reserve.utilization_spec.value),1);
// Operate the actual Series controls by their saved field paths, preserving precision.
const util=page.locator('input[onchange*="utilization_spec"]');
const loss=page.locator('input[onchange*="lifetime_loss_rate_spec"]');
await util.fill('40');await util.press('Tab');
await loss.fill('0.4083333');await loss.press('Tab');
assert.equal(await page.evaluate(()=>cfg.assumptions.lending_products[0].unused_commitment_reserve.utilization_spec.value),.4);
assert(Math.abs(await page.evaluate(()=>cfg.assumptions.lending_products[0].unused_commitment_reserve.lifetime_loss_rate_spec.value)-.004083333)<1e-12);
assert(await page.evaluate(()=>{const s=JSON.stringify(cfg);cfg=normalizeCfg(JSON.parse(s));return JSON.stringify(cfg)===s;}));
await page.screenshot({path:'/workspace/scratch/370303911165/r456-unused-controls.png',fullPage:true});
// A completed run, a new edit, and an already-open Numbers snapshot.
await page.evaluate(()=>{
 _calculatedInputs=JSON.stringify(cfg);_calculationState='complete';updateCalculationStatus();
 const p={co:[1,2],alll:[10,20],provision:[11,12],unusedCommitmentReserve:[0,3,4],unusedCommitmentProvision:[3,1],totalCommitment:[100,200],unusedCommitment:[60,120]};
 document.getElementById('loan-test').innerHTML=_resultNumbersLink(_resultPanelSeries(p,'credit','', 'lending'),false);
});
assert.equal(await page.locator('#calculation-state').innerText(),'Up to date');
await page.getByRole('button',{name:'View period numbers and copy for Excel'}).click();
assert(await page.getByRole('button',{name:'Copy table for Excel'}).isEnabled());
assert(await page.getByText('Unused commitment provision / (release)',{exact:false}).count());
await page.evaluate(()=>{cfg.assumptions.lending_products[0].reserve_rate_pct_bal=.006;_calculationState='pending';updateCalculationStatus();});
assert.equal(await page.locator('#calculation-state').innerText(),'Calculating…');
assert(await page.getByRole('button',{name:'Copy table for Excel'}).isDisabled());
await page.evaluate(()=>{_calculatedInputs=JSON.stringify(cfg);_calculationState='complete';updateCalculationStatus();});
assert.equal(await page.locator('#calculation-state').innerText(),'Up to date');
assert(await page.getByRole('button',{name:'Copy table for Excel'}).isDisabled(),'old snapshot remains blocked after new run');
await page.getByRole('button',{name:'Close period values'}).click();
await page.evaluate(()=>{document.getElementById('loan-test').innerHTML=_resultNumbersLink([{name:'New result',unit:'$000s',values:[4,5]}],false);});
await page.getByRole('button',{name:'View period numbers and copy for Excel'}).click();
assert(await page.getByRole('button',{name:'Copy table for Excel'}).isEnabled());
await page.evaluate(()=>{_calculationState='failed';updateCalculationStatus();});
assert.equal(await page.locator('#calculation-state').innerText(),'Failed');
assert(await page.getByRole('button',{name:'Copy table for Excel'}).isDisabled());
await page.getByRole('button',{name:'Close period values'}).click();
// Exercise actual request lifecycle and late-result rejection with a delayed response.
await page.evaluate(()=>{currentTab='products';renderContent=()=>{};paintChrome=()=>{};refreshProductValidation=()=>{};refreshProductStats=()=>{};refreshFeeCustomerCountPreviews=()=>{};refreshStreamFigures=()=>{};refreshLsrcLive=()=>{};loadSourceCatalog=async()=>{};syncModules=()=>{};});
let deliver;
await page.route('**/api/v2/preview',async r=>{await new Promise(ok=>deliver=ok);await r.fulfill({status:200,json:fx.result});});
await page.evaluate(()=>{window.pendingRun=_previewInner();});
await page.waitForFunction(()=>_calculationState==='running');
await page.evaluate(()=>{cfg.assumptions.lending_products[0].reserve_rate_pct_bal=.007;_calculationState='pending';updateCalculationStatus();window.lastBefore=lastRes;});
deliver();await page.evaluate(()=>pendingRun);
assert(await page.evaluate(()=>lastRes===lastBefore),'obsolete response cannot publish');
assert.equal(await page.locator('#calculation-state').innerText(),'Calculating…');
await page.unroute('**/api/v2/preview');await page.route('**/api/v2/preview',r=>r.fulfill({status:200,json:fx.result}));
await page.evaluate(()=>_previewInner());
assert.equal(await page.locator('#calculation-state').innerText(),'Up to date');
assert.deepStrictEqual(errors,[]);console.log('PASS r456 decorated reserve controls, full precision, persistence, result rows, pending/current/failed states, stale snapshot copy blocking, late request rejection and recovery');
}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
