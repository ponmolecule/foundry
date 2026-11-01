// r434: the field system on product setup steps (lending, deposits, off-balance-sheet) and the customer-acquisition
// channel editor and feed settings: one right-aligned label column, fields sized to content, path as segmented buttons
// driving the existing selects, captions lifted (not duplicated), narrow steps stack, and rendering leaves the config alone.
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
await page.evaluate(f=>{cfg=normalizeCfg(f.cfg);lastRes=f.result;window._runs=0;refresh=()=>{window._runs++;};scheduleAutosave=()=>{};document.body.classList.add('insp-closed');renderTabs();setTab('products');},fx);

await page.evaluate(()=>{const p=cfg.assumptions.lending_products.find(p=>p.repayment_profile);window._prdSel=p;window._prdView='product';window._prdTab='setup';renderContent();prdGroupSetup();});
await page.locator('.lnv-ri').nth(1).click();await page.waitForTimeout(100);
const row=page.locator('section.lnv-on .loan-profile-loss-rate');
assert.strictEqual(await row.count(),1);
const label=row.locator(':scope>label'),value=row.locator('input[aria-label="Annual loss rate"]');
assert.strictEqual(await label.innerText(),'Annual loss rate');
assert.strictEqual(await value.count(),1);
const box=await label.boundingBox(),vb=await value.boundingBox();assert(vb.y>=box.y-20&&vb.y-(box.y+box.height)<65,'label stays local to rate (beside or stacked)');   // r443: narrow panels stack consistently
assert.strictEqual(await page.locator('section.lnv-on').getByText('Annual loss rate',{exact:true}).count(),1,'label appears once');
const before=await page.evaluate(()=>JSON.stringify(cfg));
await page.evaluate(()=>renderContent());await page.waitForTimeout(80);
assert.strictEqual(await page.evaluate(()=>JSON.stringify(cfg)),before,'redraw does not mutate config');
await row.locator('input[aria-label="Annual loss rate"]').fill('4');await row.locator('input[aria-label="Annual loss rate"]').press('Tab');
assert.strictEqual(await page.evaluate(()=>window._prdSel.repayment_profile.loss_rate_spec.value),.04);
await page.screenshot({path:'/workspace/scratch/370303911165/r442-loss-label.png',fullPage:true});
// Lifetime basis uses its own accurate local label.
await page.evaluate(()=>{const i=cfg.assumptions.lending_products.indexOf(window._prdSel);loanRepaymentLossBasis(i,'cohort_volume');});
await page.waitForTimeout(80);
assert.strictEqual(await row.locator(':scope>label').innerText(),'Lifetime loss at funding');
assert.strictEqual(await row.locator('input[aria-label="Lifetime loss at funding"]').count(),1);
assert.deepStrictEqual(errors,[]);console.log('r442 profile loss label: ok');
}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
