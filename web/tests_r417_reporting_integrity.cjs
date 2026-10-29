// r417: browsing the reporting view never changes the configuration; grouping gives products immutable IDs and
// membership follows them through renames; reconciliation cells show the largest underlying period difference
// (opposite monthly errors cannot cancel in an annual cell); official export stops while reporting does not reconcile.
const {chromium}=require('playwright'),fs=require('fs'),assert=require('assert'),{execFileSync}=require('child_process');
(async()=>{
const fixture=JSON.parse(execFileSync('python3',['-c',`import json
from foundry.v2.run_q import run_v2
c=json.load(open('foundry/fixtures/universal_template_bank.json'))
print(json.dumps({'cfg':c,'result':run_v2(c)}))`],{encoding:'utf8',maxBuffer:1<<28}));
const html=fs.readFileSync('web/console_v2.html','utf8').replace('<script src="/web/rates_workspace.js"></script>','<script>'+fs.readFileSync('web/rates_workspace.js','utf8')+'</script>').replace('<head>','<head><script>window.V3=true;window.V31=true;</script>').replace(/renderTabs\(\);\nwhoami\(\)\.then[^\n]+/,'');
const browser=await chromium.launch({executablePath:process.env.FOUNDRY_CHROMIUM_PATH,args:['--no-sandbox','--disable-gpu','--single-process','--no-zygote'],headless:true});
try{
const page=await browser.newPage({viewport:{width:1600,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));page.setDefaultTimeout(15000);
await page.route('**/*',r=>r.fulfill({status:200,json:{}}));await page.goto('http://foundry.test');await page.setContent(html);
await page.evaluate(f=>{cfg=f.cfg;lastRes=f.result;currentTab='detail';window._runs=0;refresh=()=>{window._runs++;};scheduleAutosave=()=>{window._runs++;};window._st=[];appStatus=(k,m)=>window._st.push([k,m]);renderContent();},fixture);
const C=page.locator('#content');
// 1. Browsing is read-only: an engagement without a manifest stays without one, through every reporting page.
const snap=()=>page.evaluate(()=>JSON.stringify(cfg));const before=await snap();
await C.locator('.rpt-bar button',{hasText:'By reporting entry'}).click();
assert(/None yet/.test(await C.locator('.rpt-man').innerText()));
await C.locator('.rpt-cov').click();await page.evaluate(()=>{rptRecMeasure(0);rptSetPPY(4);rptSetPPY(1);rptSetView('product');rptSetView('reporting');});
await page.evaluate(()=>{rptOpenDialog('create');});await page.evaluate(()=>rptCloseDialog());
assert.strictEqual(await snap(),before,'viewing, opening and cancelling a dialog change nothing');
assert.strictEqual(await page.evaluate(()=>'reporting_manifest' in cfg),false);
assert.strictEqual(await page.evaluate(()=>window._runs),0,'no rerun or autosave from browsing');
// 2. Creating a group is the explicit edit that gives its products immutable IDs; membership follows the ID.
await page.evaluate(()=>rptOpenDialog('create'));await C.locator('.rpt-dlg input[data-rpt-name]').fill('Operating Accounts');
await C.locator('.rpt-dlg .pk',{hasText:'Retail Demand'}).click();await C.locator('.rpt-dlg .pk',{hasText:'MMDA / Savings'}).click();
await C.locator('.rpt-dlg [data-rpt-confirm]').click();
const m=await page.evaluate(()=>({mem:cfg.reporting_manifest.reporting_products[0].members,ids:cfg.assumptions.deposit_products.slice(0,3).map(p=>p.product_id||null)}));
assert(m.ids[0]&&m.ids[1]&&!m.ids[2],'only the chosen products receive IDs');assert.notStrictEqual(m.ids[0],m.ids[1]);
assert.deepStrictEqual(m.mem.map(x=>[x.family,x.product_id,x.name]),[['deposit',m.ids[0],'Retail Demand'],['deposit',m.ids[1],'MMDA / Savings']]);
await page.evaluate(()=>renameProduct('deposit',0,'Operating — Lower Tier'));
const after=await page.evaluate(()=>cfg.reporting_manifest.reporting_products[0].members[0]);
assert.deepStrictEqual([after.product_id,after.name],[m.ids[0],'Operating — Lower Tier'],'rename keeps the ID and updates the label');
assert(await page.evaluate(()=>_rptOwner(_rptPKey('deposit',cfg.assumptions.deposit_products[0]))!==null),'still a member after rename');
// 3. Reconciliation cells: the largest underlying period difference, never a netted annual sum.
await page.evaluate(()=>{const V=lastRes.reporting;V.manifest=_rptNorm();const meas=V.reconciliation.measures.find(x=>x.class==='noninterest_expense');
  meas.diff_bank=meas.diff_bank.map(()=>0);meas.diff_bank[0]=5;meas.diff_bank[1]=-5;meas.ok=false;V.ok=false;V.reconciliation.ok=false;window._rptViewPPY=1;rptSelect('recon');});
const row=C.locator('.rpt-sch tbody tr.ln',{hasText:'Operating costs'});
const cells=await row.locator('td.n').allInnerTexts();
assert.strictEqual(cells[0],'5','Year 1 shows the largest monthly difference although the months net to zero');
assert(/0 ✓/.test(cells[1]),'other years clean');
assert(/does not reconcile/.test(await C.locator('.rpt-cov').innerText()));
// 4. Official export stops in the browser before reaching the server.
const blocked=await page.evaluate(()=>rptExportBlock());assert.strictEqual(blocked,true);
assert(await page.evaluate(()=>window._st.some(([k,m])=>k==='err'&&/not exported: reporting does not reconcile/.test(m))));
await page.evaluate(()=>{lastRes.reporting.ok=true;});assert.strictEqual(await page.evaluate(()=>rptExportBlock()),false);
assert.deepStrictEqual(errors,[]);
console.log('PASS r417 reporting integrity: read-only browsing, explicit IDs on grouping, membership follows IDs through rename, largest-period reconciliation cells, export block');
}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
