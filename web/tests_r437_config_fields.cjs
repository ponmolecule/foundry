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
// 1. Rendering every module leaves the configuration alone (after one warm-up pass).
const mods=await page.evaluate(()=>[...document.querySelectorAll('.cfg-mod[data-cfg-mod]')].map(e=>e.getAttribute('data-cfg-mod')));
for(const m of mods)await mod(m);const c0=await page.evaluate(()=>JSON.stringify(cfg));for(const m of mods)await mod(m);
assert.strictEqual(await page.evaluate(()=>JSON.stringify(cfg)),c0,'rendering mutated the configuration');
// 2. Workforce population: one label column; Count and Compensation carry their path buttons.
await mod('nie');const W=vis('.cfg-md-detail .fxs-wf');assert.strictEqual(await W.count(),1,'population on the field system');
const labs=await W.locator('.fxs-cfgrow>.fxs-cl').evaluateAll(ls=>ls.map(l=>({t:l.textContent,r:Math.round(l.getBoundingClientRect().right)})));
assert(labs.length>=6&&new Set(labs.map(l=>l.r)).size===1,'labels on one edge '+JSON.stringify(labs));
for(const t of ['Count','Compensation','Amount basis','Active from'])assert(labs.some(l=>l.t===t),t+' row');
const role=()=>page.evaluate(()=>JSON.parse(JSON.stringify(cfg.assumptions.nie_detail.workforce.roles[0])));
const cRow=W.locator('.fxs-cfgrow',{has:page.locator('.fxs-cl',{hasText:/^Count$/})});
assert.deepStrictEqual(await cRow.locator('.fxs-seg button').allInnerTexts(),['Flat','Growth','Schedule']);
await cRow.locator('.fxs-seg button',{hasText:'Growth'}).click();await settle();
assert.strictEqual((await role()).count_spec.trajectory,'growth','count path written');
assert.strictEqual(await vis('.cfg-md-detail .fxs-wf .fxs-cfgrow .fxs-cl').filter({hasText:'Count growth'}).count(),1,'growth line under the count');
const pRow=vis('.cfg-md-detail .fxs-wf .fxs-cfgrow').filter({has:page.locator('.fxs-cl',{hasText:/^Compensation$/})});
assert.deepStrictEqual(await pRow.locator('.fxs-seg button').allInnerTexts(),['Flat','Growth','Schedule']);
const name=vis('.cfg-md-detail .fxs-wf input.wf-role-name');await name.fill('Operations team');await name.press('Tab');await settle();
assert.strictEqual((await role()).role,'Operations team','name still edits the role');
// 3. Expense category: Category, Amount (path, value, period) and Growth rows.
await page.locator('.cfg-subtab',{hasText:'Expense categories'}).click();await settle();
const C=vis('.cfg-md-detail .opex-item-card.fxs-cfg');assert.strictEqual(await C.count(),1);
assert.deepStrictEqual(await C.locator('.fxs-cfgrow>.fxs-cl').allInnerTexts().then(a=>a.slice(0,3)),['Category','Amount','Growth']);
const cat=()=>page.evaluate(()=>JSON.parse(JSON.stringify(cfg.assumptions.nie_detail.categories[0])));
await C.locator('.fxs-cfgrow',{has:page.locator('.fxs-cl',{hasText:'Amount'})}).locator('.fxs-seg button',{hasText:'Flat'}).click();await settle();
assert.strictEqual((await cat()).flow_spec.trajectory,'flat','amount path written');
assert.strictEqual(await vis('.cfg-md-detail .opex-item-card .fxs-cfgrow .fxs-cl').filter({hasText:/^Growth$/}).count(),0,'flat amount has no growth row');
// 4. Capital raises and borrowings as tables; inputs keep editing their records.
await mod('cap');const B=vis('#card-cap .fxs-cap-h.fxs-cap-borrow');assert.strictEqual(await B.count(),1);
assert.deepStrictEqual((await B.locator('span').allInnerTexts()).slice(0,5),['Borrowing','Month','Amount ($000s)','Rate (%)','Term (qtrs)']);
const br=await page.evaluate(()=>{const r=document.querySelector('#card-cap .crow.fxs-cap-borrow');const box=r.getBoundingClientRect(),card=r.closest('.ccols>div').getBoundingClientRect();return {inside:[...r.children].filter(e=>e.offsetParent).every(e=>e.getBoundingClientRect().right<=card.right+1),h:box.height};});
assert(br.inside&&br.h<40,'borrowing row on one line inside its card '+JSON.stringify(br));
// 5. Other income line on the label column, amount with its period.
await mod('income');const add=page.locator('#card-income button',{hasText:'+ Add income line'});if(await add.count())await add.click();await settle();
const I=vis('#card-income .fxs-cfg');assert((await I.count())>=1,'income line');
const il=await I.first().locator('.fxs-cfgrow>.fxs-cl').allInnerTexts();assert(il.includes('Name')&&il.some(t=>/amount/i.test(t)),'income rows '+il);
assert.deepStrictEqual(errors,[]);
console.log('r437 configuration field system: ok');
}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
