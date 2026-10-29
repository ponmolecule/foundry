// r416: Product Detail reporting manifest. Whole-product membership, report lines from accounting classification with
// same-class overrides only, a business plan preview over the forecast horizon, reconciliation by measure and period,
// read-only authoring objects with Open editor → Products and a return link, and fee-stream direct cost labels.
const {chromium}=require('playwright'),fs=require('fs'),assert=require('assert'),{execFileSync}=require('child_process');
(async()=>{
const fixture=JSON.parse(execFileSync('python3',['-c',`import json
from foundry.v2.run_q import run_v2
c=json.load(open('foundry/fixtures/universal_template_bank.json'))
c['reporting_manifest']={'reporting_products':[{'id':'rp-oa','name':'Operating Accounts','members':[{'family':'deposit','name':'Retail Demand'},{'family':'deposit','name':'MMDA / Savings'},{'family':'obs','name':'Stream and pricing mechanics'}],'line_overrides':{}}]}
print(json.dumps({'cfg':c,'result':run_v2(c)}))`],{encoding:'utf8',maxBuffer:1<<28}));
const html=fs.readFileSync('web/console_v2.html','utf8').replace('<script src="/web/rates_workspace.js"></script>','<script>'+fs.readFileSync('web/rates_workspace.js','utf8')+'</script>').replace('<head>','<head><script>window.V3=true;window.V31=true;</script>').replace(/renderTabs\(\);\nwhoami\(\)\.then[^\n]+/,'');
const browser=await chromium.launch({executablePath:process.env.FOUNDRY_CHROMIUM_PATH,args:['--no-sandbox','--disable-gpu','--single-process','--no-zygote'],headless:true});
try{
const page=await browser.newPage({viewport:{width:1600,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>d.accept());page.setDefaultTimeout(15000);
await page.route('**/*',r=>r.fulfill({status:200,json:{}}));await page.goto('http://foundry.test');await page.setContent(html);
await page.evaluate(f=>{cfg=f.cfg;lastRes=f.result;currentTab='detail';window._runs=0;refresh=()=>{window._runs++;};scheduleAutosave=()=>{};renderContent();},fixture);
const C=page.locator('#content');
// 1. By product stays the default; grouped rows say where they are reported; schedules name fee-stream direct costs.
assert(await C.locator('.rpt-bar button.on').innerText()==='By product');
const tbl=await C.locator('.product-summary-table').innerText();
assert(/Retail Demand\s*in Operating Accounts/.test(tbl)&&!/Brokered\s*in /.test(tbl),'Reported in chip on grouped rows only');
const body=await C.innerText();
assert(!body.includes('→ overhead'),'no "→ overhead" label');
assert(body.includes('Fee-stream direct costs')&&body.includes('Total direct operating costs')&&body.includes('Operating costs · base'),'base, fee-stream and total direct operating costs');
// 2. Reporting view: manifest list, composition with whole products and report lines from accounting classification.
await C.locator('.rpt-bar button',{hasText:'By reporting entry'}).click();
assert.strictEqual(await C.locator('.rpt-me.on .t').innerText().then(t=>t.replace('REPORTING','').trim()),'Operating Accounts');
assert(/Reporting reconciles/.test(await C.locator('.rpt-cov').innerText()));
const comp=await C.locator('.rpt-card').first().innerText();
assert(/FOLLOWS PRODUCT/.test(comp)&&/Retail Demand/.test(comp)&&/Stream and pricing mechanics/.test(comp));
const nRes=await page.evaluate(()=>lastRes.reporting.results.filter(r=>r.destinations.includes('rp-oa')).length);
assert.strictEqual(await C.locator('.rpt-rl tbody tr').count(),nRes,'one report-line row per result');
assert(/0 overrides/.test(comp));
assert(/Earnings on deposits are not attributed/.test(comp),'unresolved earnings notice');
// 3. Overrides: other classes are refused; a new same-class line is stored for that result only.
const rid=await page.evaluate(()=>lastRes.reporting.results.find(r=>r.product==='deposit/Retail Demand'&&r.class==='noninterest_expense').id);
await page.evaluate(id=>rptOverrideOpen(id),rid);
assert(await C.locator('.rpt-menu .opt.off',{hasText:'Fee income'}).count()===1,'fee income offered only as not allowed');
await C.locator('.rpt-menu input[data-rpt-newline]').fill('Cost of funds');await C.locator('.rpt-menu .opt.new button').click();
assert(/Not allowed/.test(await C.locator('.rpt-menu .rpt-err').innerText()));
assert.deepStrictEqual(await page.evaluate(()=>cfg.reporting_manifest.reporting_products[0].line_overrides),{},'refused override is not saved');
await C.locator('.rpt-menu input[data-rpt-newline]').fill('Deposit servicing');await C.locator('.rpt-menu .opt.new button').click();
assert.deepStrictEqual(await page.evaluate(()=>cfg.reporting_manifest.reporting_products[0].line_overrides),{[rid]:'Deposit servicing'});
assert(await page.evaluate(()=>window._runs)>=1,'manifest change reruns the model');
assert(await C.locator('.rpt-pend').count()===1,'pending note until the rerun arrives');
await page.evaluate(id=>rptOverrideSet('rp-oa',id,null),rid);
assert.deepStrictEqual(await page.evaluate(()=>cfg.reporting_manifest.reporting_products[0].line_overrides),{},'default restores');
assert(await C.locator('.rpt-pend').count()===0);
// 4. Business plan preview: forecast horizon, cadence, details only on demand, one direct contribution.
await C.locator('.rpt-vt button',{hasText:'Business plan preview'}).click();
assert(/M1–M36/.test(await C.locator('.rpt-hz').innerText()));
const heads=await C.locator('.rpt-sch thead th').allInnerTexts();
assert.deepStrictEqual(heads.slice(1),['YEAR 1','YEAR 2','YEAR 3','HORIZON']);
await C.locator('.rpt-cad button',{hasText:'Quarter'}).click();
assert.strictEqual((await C.locator('.rpt-sch thead th').allInnerTexts()).length,14,'12 quarters + label + horizon');
await C.locator('.rpt-cad button',{hasText:'Year'}).click();
assert.strictEqual(await C.locator('.rpt-sch tr.mem').count(),0,'detail hidden until a line is opened');
const iAttr=await page.evaluate(()=>lastRes.reporting.entries.find(e=>e.id==='rp-oa').schedule.lines.findIndex(l=>l.label==='Attributable costs'));
await page.evaluate(i=>rptLine(i),iAttr);
assert(await C.locator('.rpt-sch tr.mem').count()>=2&&await C.locator('.rpt-drill').count()===1,'detail within subtotal and sources');
assert(/within subtotal/.test(await C.locator('.rpt-sch tr.mem').first().innerText()));
assert(/unresolved/.test(await C.locator('.rpt-sch tr.un').innerText()));
const dcShown=await C.locator('.rpt-sch tr.tot td').last().innerText();
const dcWant=await page.evaluate(()=>fmt0(lastRes.reporting.entries.find(e=>e.id==='rp-oa').schedule.direct_contribution.reduce((a,b)=>a+b,0)));
assert.strictEqual(dcShown,dcWant,'direct contribution horizon total');
// 5. Authoring objects: read-only; Open editor goes to the real editor with a return link.
await C.locator('.rpt-vt button',{hasText:'Authoring objects'}).click();
assert.strictEqual(await C.locator('.rpt-obj').count(),3);
assert.strictEqual(await C.locator('.rpt-card input,.rpt-card select').count(),0,'no financial inputs on reporting pages');
await C.locator('.rpt-obj',{hasText:'MMDA / Savings'}).locator('.rpt-go').click();
assert.strictEqual(await page.evaluate(()=>currentTab),'products');
assert.strictEqual(await page.evaluate(()=>window._prdSel&&window._prdSel.name),'MMDA / Savings');
assert(/Back to Operating Accounts/.test(await C.locator('.rpt-ret').innerText()));
await C.locator('.rpt-ret .rpt-go').click();
assert.strictEqual(await page.evaluate(()=>currentTab),'detail');assert.strictEqual(await page.evaluate(()=>window._pdView),'reporting');
assert.strictEqual(await C.locator('.rpt-ret').count(),0);
// 6. Reconciliation by measure and period, with coverage by result.
await C.locator('.rpt-cov').click();
assert(/Reporting reconciles/.test(await C.locator('.rpt-rc').innerText()));
const recRows=await C.locator('.rpt-sch tbody tr.ln').count();assert.strictEqual(recRows,7,'seven measures');
await C.locator('.rpt-sch tbody tr.ln',{hasText:'Operating costs'}).click();
const bu=await C.locator('.rpt-sch tr.bu').allInnerTexts();
assert(bu.some(t=>/Outside product contributions/.test(t))&&bu.some(t=>/^Difference/.test(t)));
assert(/0\s*omitted/.test(await C.locator('.rpt-cvs').innerText())&&/0\s*reported twice/.test(await C.locator('.rpt-cvs').innerText()));
// 7. Create: name checks, whole products, products in another reporting product unavailable.
await C.locator('.rpt-add').click();
await C.locator('.rpt-dlg [data-rpt-confirm]').click();
assert(/name/.test(await C.locator('.rpt-dlg .rpt-err').innerText()));
await C.locator('.rpt-dlg input[data-rpt-name]').fill('Brokered');await C.locator('.rpt-dlg [data-rpt-confirm]').click();
assert(/product already has this name/.test(await C.locator('.rpt-dlg .rpt-err').innerText()));
assert(await C.locator('.rpt-dlg .pk.dis',{hasText:'Retail Demand'}).isDisabled(),'owned product cannot be added twice');
await C.locator('.rpt-dlg input[data-rpt-name]').fill('Card Program');
await C.locator('.rpt-dlg .pk',{hasText:'Credit Card'}).click();await C.locator('.rpt-dlg .pk',{hasText:'Interchange / Durbin coverage'}).click();
await C.locator('.rpt-dlg [data-rpt-confirm]').click();
const man=await page.evaluate(()=>cfg.reporting_manifest.reporting_products.map(r=>[r.name,r.members.map(m=>m.family+'/'+m.name)]));
assert.deepStrictEqual(man[1],['Card Program',['lending/Credit Card','obs/Interchange / Durbin coverage']]);
assert.strictEqual(await C.locator('.rpt-dlg').count(),0);assert(/Card Program/.test(await C.locator('.rpt-me.on').innerText()));
// 8. Edit membership and delete: products, streams and assumptions are never touched.
const counts=()=>page.evaluate(()=>['lending_products','deposit_products','obs_exposures'].map(k=>cfg.assumptions[k].length+':'+cfg.assumptions[k].reduce((n,p)=>n+(p.fee_streams||[]).length,0)).join(','));
const before=await counts();
await page.evaluate(()=>rptOpenDialog('edit','rp-oa'));await C.locator('.rpt-dlg .pk.on',{hasText:'MMDA / Savings'}).click();await C.locator('.rpt-dlg [data-rpt-confirm]').click();
assert.deepStrictEqual(await page.evaluate(()=>cfg.reporting_manifest.reporting_products[0].members.map(m=>m.name)),['Retail Demand','Stream and pricing mechanics']);
await page.evaluate(()=>rptOpenDialog('delete','rp-oa'));
assert(/return to standalone entries/.test(await C.locator('.rpt-dlg').innerText()));
await page.keyboard.press('Escape');assert.strictEqual(await C.locator('.rpt-dlg').count(),0,'Escape closes');
await page.evaluate(()=>rptOpenDialog('delete','rp-oa'));await C.locator('.rpt-dlg [data-rpt-confirm]').click();
assert.deepStrictEqual(await page.evaluate(()=>cfg.reporting_manifest.reporting_products.map(r=>r.name)),['Card Program']);
assert.strictEqual(await counts(),before,'no product or stream removed');
// 9. Renaming or deleting a product keeps membership whole.
await page.evaluate(()=>{const i=cfg.assumptions.lending_products.findIndex(p=>p.name==='Credit Card');renameProduct('lending',i,'Charge Card Receivables');});
assert.deepStrictEqual(await page.evaluate(()=>cfg.reporting_manifest.reporting_products[0].members.map(m=>m.name)),['Charge Card Receivables','Interchange / Durbin coverage']);
await page.evaluate(()=>{window.feeConfirmDeletion=()=>true;const i=cfg.assumptions.lending_products.findIndex(p=>p.name==='Charge Card Receivables');delProduct('lending',i);});
assert.deepStrictEqual(await page.evaluate(()=>cfg.reporting_manifest.reporting_products[0].members.map(m=>m.name)),['Interchange / Durbin coverage']);
// 10. Containment.
await page.evaluate(()=>{lastRes=null;});await page.evaluate(f=>{lastRes=f.result;cfg=f.cfg;window._rptSel='rp-oa';window._rptTab='plan';renderContent();},fixture);
for(const width of [1440,1024,768]){await page.setViewportSize({width,height:1000});
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),width+' no page scroll');}
assert.deepStrictEqual(errors,[]);
console.log('PASS r416 reporting manifest: by-product default with Reported in, fee-stream direct cost labels, whole-product composition, report lines with same-class overrides only, pending rerun note, horizon preview with cadence and on-demand detail, read-only authoring objects with editor return link, reconciliation by measure and period with coverage, create/edit/delete without touching products, rename/delete follow-through, containment');
}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
