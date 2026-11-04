// r466: Fixed assets Formula / level as one component table (opening position, components with level and
// depreciation per row, roll-forward). Presentation only: the stored config and engine are unchanged.
const {chromium}=require('playwright'),fs=require('fs'),assert=require('assert'),{execFileSync}=require('child_process');
const fixture=mode=>JSON.parse(execFileSync('python3',['-c',`import json,sys
from foundry.v2.run_q import run_v2
c=json.load(open('foundry/fixtures/universal_template_bank.json'))
sp=lambda v,p=None:{**{'source':'entered','trajectory':'flat','value':v},**({'period':p} if p else {})}
fl={'level_basis':'gross','opening_level':56000,'opening_accumulated_depreciation':2700,'base_name':'Base asset level','base_spec':sp(0),
 'components':[{'component_id':'fa-tech','name':'Office equipment / technology','driver_spec':{'source':'link','link':{'kind':'workforce_role_count','series_id':'wf-count-ops-universal','aggregation':'end'}},
   'lag_months':1,'initial_driver':0,'driver_divisor':1,'driver_rounding':'none','multiplier_spec':sp(1000),'depreciation_rate_spec':sp(1/3,'year')}],
 'depreciation':{'kind':'component_rates','base_rate_spec':sp(0,'year')}}
if '${mode}'=='ok':
  fl['base_spec']=sp(50000);fl['components'][0]['initial_driver']=6;fl['depreciation']['base_rate_spec']=sp(1/7,'year')
c['assumptions']['fixed_assets']={'mode':'formula_level','formula_level':fl,'assets':[]}
print(json.dumps({'cfg':c,'result':run_v2(c)}))`],{encoding:'utf8',maxBuffer:1<<28}));
(async()=>{
const html=fs.readFileSync('web/console_v2.html','utf8').replace('<script src="/web/rates_workspace.js"></script>','<script>'+fs.readFileSync('web/rates_workspace.js','utf8')+'</script>').replace('<head>','<head><script>window.V3=true;window.V31=true;</script>').replace(/renderTabs\(\);\nwhoami\(\)\.then[^\n]+/,'');
const browser=await chromium.launch({executablePath:process.env.FOUNDRY_CHROMIUM_PATH,args:['--no-sandbox','--disable-gpu','--single-process','--no-zygote'],headless:true});
try{
const page=await browser.newPage({viewport:{width:1440,height:1100}}),errors=[];page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>d.dismiss());page.setDefaultTimeout(15000);
await page.route('**/*',r=>r.fulfill({status:200,json:{}}));await page.goto('http://foundry.test');await page.setContent(html);
const load=fx=>page.evaluate(f=>{cfg=normalizeCfg(f.cfg);lastRes=f.result;lastErrs=[];refresh=()=>{};scheduleAutosave=()=>{};window._cfgModule='cap';window._faCompOpen=null;window._faPathEditor=null;renderTabs();setTab('config');window._cfgSectionOpen=window._cfgSectionOpen||{};window._cfgSectionOpen.fixedassets=true;renderContent();},fx);
const FL=()=>page.evaluate(()=>JSON.parse(JSON.stringify(cfg.assumptions.fixed_assets.formula_level)));
const num=async sel=>Number((await page.locator(sel).innerText()).replace(/,/g,''));
const A=await (async()=>{const fx=fixture('comp');await load(fx);return fx.result.fixed_assets;})();
// 1. One table: base + one component, then a total. The old stacked groups are gone.
const x=page.locator('[data-fa-formula]');assert.strictEqual(await x.count(),1);
assert.strictEqual(await page.locator('#fixedassets-editor .capital-formula-group').count(),0,'old stacked groups removed');
assert.strictEqual(await page.locator('.fxa-t tr.fxa-r').count(),2);
assert(await page.locator('#fixedassets-editor').evaluate(e=>getComputedStyle(e).gridColumnStart==='1'&&getComputedStyle(e).gridColumnEnd==='-1'),'editor spans the row');
// 2. Values reconcile with the engine payload.
assert.strictEqual(await num('[data-engine-preview="fa-lv-tot"]'),Math.round(A.gross[12]*10)/10);
const depTot=A.accumulated_depreciation[12]-A.accumulated_depreciation[0]+A.formula_level.accumulated_depreciation_relief.slice(1,13).reduce((s,v)=>s+v,0);
assert.strictEqual(await num('[data-engine-preview="fa-dp-tot"]'),Math.round(depTot*10)/10);
const comp=A.formula_level.components[0];
assert.strictEqual(await num('[data-engine-preview="fa-dp-0"]'),Math.round(comp.depreciation.slice(0,12).reduce((s,v)=>s+v,0)/1000*10)/10,'component depreciation is shown in $000s');
// 3. Roll-forward foots exactly as displayed.
const rf=(await page.locator('[data-engine-preview="fxa-rf"] .fxa-v').allInnerTexts()).map(t=>Number(t.split('\n')[0].replace(/,/g,'')));
assert.strictEqual(rf.length,10);
assert(Math.abs(rf[0]+rf[1]-rf[2]-rf[3])<0.11,'gross foots: '+rf.slice(0,4));
assert(Math.abs(rf[4]+rf[5]-rf[6]-rf[7])<0.11,'accumulated depreciation foots: '+rf.slice(4,8));
assert(Math.abs(rf[3]-rf[7]-rf[9])<0.11,'net = gross - accumulated');
// 4. The M1 disposal check names the gap without prescribing a number.
const chk=await page.locator('[data-engine-preview="fxa-chk"]').innerText();
assert(/M1 level is 0\.0 against an opening book of 56\.0/.test(chk)&&/Base asset level/.test(chk)&&/Headcount before M1/.test(chk),chk);
assert(!/Set to/.test(chk),'no prescribed fix');
// 5. Precision: a rate shown as 33.33 keeps 1/3 unless really edited.
const rate=page.getByRole('textbox',{name:'Office equipment / technology depreciation rate',exact:true});
assert.strictEqual(await rate.inputValue(),'33.33');
assert.strictEqual(await page.locator('.fxa-sub',{hasText:'3.0-year life'}).count(),1);
await rate.focus();assert.strictEqual(await rate.inputValue(),'33.3333333333333');
await rate.press('End');await rate.type(' ');await rate.press('Tab');await page.waitForTimeout(80);
assert.strictEqual((await FL()).components[0].depreciation_rate_spec.value,1/3,'incidental edit keeps full precision');
await page.getByRole('textbox',{name:'Office equipment / technology depreciation rate',exact:true}).fill('25');await page.keyboard.press('Tab');await page.waitForTimeout(80);
assert.strictEqual((await FL()).components[0].depreciation_rate_spec.value,0.25);
// 6. Path tag opens the series editor (with rate period) under its row.
await page.getByRole('button',{name:'Edit Office equipment / technology depreciation rate path'}).click();
assert.strictEqual(await page.locator('.fxa-edr .sec-managed-series').count(),1);
assert(await page.locator('.fxa-edr').innerText().then(t=>/Rate period/.test(t)));
await page.locator('.fxa-edr .fxa-done').click();assert.strictEqual(await page.locator('.fxa-edr').count(),0);
// 7. Component editor: driver, timing, multiplier, optional grouping, equation.
await page.getByRole('button',{name:'Edit Office equipment / technology driver'}).click();
const ed=page.locator('.fxa-edr');assert.strictEqual(await ed.count(),1);
assert(/Level in month t = Operations at t − 1 mo × \$1\.0k · M12 = 6 × \$1\.0k = 6\.0/.test(await ed.locator('.fxa-eq').innerText()),await ed.locator('.fxa-eq').innerText());
assert.strictEqual(await ed.getByLabel('Driver units per group').count(),0,'grouping hidden until asked');
await ed.getByLabel('Lag (months)').fill('2');await ed.getByLabel('Lag (months)').press('Tab');await page.waitForTimeout(80);
assert.strictEqual((await FL()).components[0].lag_months,2);
await page.locator('.fxa-edr').getByLabel('Count before M1').fill('6');await page.locator('.fxa-edr').getByLabel('Count before M1').press('Tab');await page.waitForTimeout(80);
assert.strictEqual((await FL()).components[0].initial_driver,6);
await page.getByRole('button',{name:'Add grouping'}).click();
await page.locator('.fxa-edr').getByLabel('Driver units per group').fill('3');await page.locator('.fxa-edr').getByLabel('Driver units per group').press('Tab');await page.waitForTimeout(80);
await page.locator('.fxa-edr').getByLabel('Round groups').selectOption('ceil');await page.waitForTimeout(80);
let f=await FL();assert.strictEqual(f.components[0].driver_divisor,3);assert.strictEqual(f.components[0].driver_rounding,'ceil');
assert(/2-month lag · groups of 3, rounded up/.test(await page.locator('.fxa-r.on .fxa-sub').first().innerText()));
const mult=page.getByRole('textbox',{name:'Office equipment / technology multiplier',exact:true});
await mult.fill('1.5');await mult.press('Tab');await page.waitForTimeout(80);
assert.strictEqual((await FL()).components[0].multiplier_spec.value,1500);
// 8. Method buttons write the existing fields; Net is unavailable with component rates.
const net=page.getByRole('radio',{name:'Net PP&E target'});assert(await net.isDisabled());
await page.getByRole('radio',{name:'One rate on total'}).click();
f=await FL();assert.strictEqual(f.depreciation.kind,'rate_of_level');
assert(!(await page.getByRole('radio',{name:'Net PP&E target'}).isDisabled()));
assert.strictEqual(await page.getByRole('textbox',{name:'Depreciation rate on total',exact:true}).count(),1);
await page.getByRole('radio',{name:'Entered amount'}).click();assert.strictEqual((await FL()).depreciation.kind,'entered');
await page.locator('.fxa-tot .fxa-tag').click();assert.strictEqual(await page.locator('.fxa-edr .sec-managed-series').count(),1,'entered amount editor opens');
await page.getByRole('radio',{name:'Net PP&E target'}).click();assert.strictEqual((await FL()).level_basis,'net');
assert(/^Net PP&E/.test(await page.locator('.fxa-open .fxa-o small').first().textContent()),'net basis leads with Net PP&E');
// 9. Names and removal.
const bn=page.getByRole('textbox',{name:'Base component name'});await bn.fill('Furniture & fixtures');await bn.press('Tab');await page.waitForTimeout(80);
assert.strictEqual((await FL()).base_name,'Furniture & fixtures');
await page.getByRole('button',{name:'Remove Office equipment / technology'}).click();assert.strictEqual((await FL()).components.length,0);
// 10. Attributed opening book: no check; base + component depreciation equals the total.
await load(fixture('ok'));
assert.strictEqual((await page.locator('[data-engine-preview="fxa-chk"]').innerText()).trim(),'');
const b0=await num('[data-engine-preview="fa-dp-base"]'),c0=await num('[data-engine-preview="fa-dp-0"]'),t0=await num('[data-engine-preview="fa-dp-tot"]');
assert(Math.abs(b0+c0-t0)<0.11,[b0,c0,t0].join(' '));
// 11. Preview keys are unique so refreshConfigPreviews updates the right cells.
const keys=await page.$$eval('[data-fa-formula] [data-engine-preview]',a=>a.map(e=>e.getAttribute('data-engine-preview')));
assert.strictEqual(new Set(keys).size,keys.length,keys.join(','));
assert.deepStrictEqual(errors,[]);
console.log('r466 fixed assets formula table: 11 checks passed');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exit(1);});
