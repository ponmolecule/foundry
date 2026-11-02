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
await mod('nie');
await page.evaluate(()=>{const w=cfg.assumptions.nie_detail.workforce;w.default_salary_growth_spec={rate:.026,period:'year',method:'step',anchor:'hire_anniversary'};const r=w.roles[0];delete r.compensation_spec;delete r.salary_growth_spec;renderContent();});
const role=()=>page.evaluate(()=>JSON.parse(JSON.stringify(cfg.assumptions.nie_detail.workforce.roles[0])));
const comp=()=>page.locator('.cfg-md-detail .fxs-wf .fxs-cfgrow').filter({has:page.locator('.fxs-cl',{hasText:/^Compensation$/})});
assert.deepStrictEqual(await comp().locator('.fxs-seg button').allInnerTexts(),['Flat','Growth','Schedule']);
assert.strictEqual(await comp().locator('button.on').innerText(),'Growth');
const source=()=>page.getByLabel('Compensation growth source');
assert.strictEqual(await source().inputValue(),'default');
const before=await role();await page.evaluate(()=>renderContent());assert.deepStrictEqual(await role(),before,'render preserves inherited configuration');
await source().selectOption('override');assert.strictEqual((await role()).salary_growth_spec.rate,.026);
const rate=()=>page.locator('.cfg-md-detail .fxs-wf input[title="Growth rate for the selected assumption period"]').last();
await rate().fill('0');await rate().press('Tab');assert.strictEqual((await role()).salary_growth_spec.rate,0,'explicit zero is an override');
await source().selectOption('default');assert.strictEqual((await role()).salary_growth_spec,undefined);
await source().selectOption('override');await rate().fill('');await rate().press('Tab');assert.strictEqual((await role()).salary_growth_spec,undefined,'blank restores inheritance');
await comp().locator('.fxs-seg button').filter({hasText:/^Flat$/}).click();assert.strictEqual((await role()).compensation_spec.trajectory,'flat');
await comp().locator('.fxs-seg button').filter({hasText:/^Growth$/}).click();assert.strictEqual((await role()).compensation_spec,undefined);assert.strictEqual(await source().inputValue(),'default');
// Existing independent growth is displayed and retained, not migrated during rendering.
await page.evaluate(()=>{const r=cfg.assumptions.nie_detail.workforce.roles[0];r.compensation_spec={source:'entered',trajectory:'growth',base:125000,period:'year',amount_basis:'per_unit',growth_spec:{rate:.07,period:'year',method:'step',anchor:'hire_anniversary'}};renderContent();});
const old=await role();assert.strictEqual(await source().inputValue(),'override');await page.evaluate(()=>renderContent());assert.deepStrictEqual(await role(),old);
await source().selectOption('default');assert.strictEqual((await role()).compensation_spec,undefined);assert.strictEqual((await role()).salary_growth_spec,undefined);
assert.deepStrictEqual(errors,[]);console.log('PASS r451 workforce inheritance, override, explicit zero, blank, flat and saved growth');
}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
