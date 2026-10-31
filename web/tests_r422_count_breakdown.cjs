// r422: weighted count breakdown band table — inline flat values, value tags that open the Series editor beneath the row,
// a remainder band, the share check (first period and every period), scale-to-100%, and results on the right.
const {chromium}=require('playwright'),fs=require('fs'),assert=require('assert'),{execFileSync}=require('child_process');
(async()=>{
const fx=JSON.parse(execFileSync('python3',['-c',`import json
from foundry.v2.count_breakdown_fixture import config
from foundry.v2.run_q import run_v2
c=config();print(json.dumps({'cfg':c,'result':run_v2(c)}))`],{encoding:'utf8',maxBuffer:1<<28}));
const html=fs.readFileSync('web/console_v2.html','utf8').replace('<script src="/web/rates_workspace.js"></script>','<script>'+fs.readFileSync('web/rates_workspace.js','utf8')+'</script>').replace('<head>','<head><script>window.V3=true;window.V31=true;</script>').replace(/renderTabs\(\);\nwhoami\(\)\.then[^\n]+/,'');
const browser=await chromium.launch({executablePath:process.env.FOUNDRY_CHROMIUM_PATH,args:['--no-sandbox','--disable-gpu','--single-process','--no-zygote'],headless:true});
try{
const page=await browser.newPage({viewport:{width:1600,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));page.setDefaultTimeout(15000);
await page.route('**/*',r=>r.fulfill({status:200,json:{}}));await page.goto('http://foundry.test');await page.setContent(html);
await page.evaluate(f=>{cfg=f.cfg;lastRes=f.result;window._runs=0;refresh=()=>{window._runs++;};scheduleAutosave=()=>{};document.body.classList.add('insp-closed');renderTabs();setTab('products');
  window._prdSel=cfg.assumptions.obs_exposures[2];window._prdView='product';window._prdTab='streams';window._stSelObj=cfg.assumptions.obs_exposures[2].fee_streams[5];window._stTab='activity';renderContent();},fx);
const A=page.locator('.count-authoring');const comps=()=>page.evaluate(()=>cfg.assumptions.obs_exposures[2].fee_streams[5].driver.params.count_multiplier_spec.components);
// 1. One row per band, flat values inline, totals and results.
assert.strictEqual(await A.locator('.fcb-t tbody tr:not(.fcb-tot)').count(),4);
assert.strictEqual(await A.locator('.fcb-tag',{hasText:'FLAT'}).count(),8);
assert(/100\.00%/.test(await A.locator('.fcb-tot').innerText())&&/12\.456/.test(await A.locator('.fcb-tot').innerText()));
assert(/count = Enabled accounts × Σ/.test(await A.locator('.count-equation').innerText()));
assert.strictEqual(await A.locator('.fcb-ro').count(),0,'no duplicate sidebar');
const explain=A.locator('.fcb-explain');assert((await explain.getAttribute('open'))===null,'explanation starts closed');
await explain.locator('summary').click();
const want=await page.evaluate(()=>lastRes.count_breakdowns[0].quantity[11].toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2}));
assert((await explain.innerText()).includes(want),'engine count in optional explanation');
assert.strictEqual(await explain.locator('.fcb-explain-contributions b').count(),4);
await explain.locator('summary').click();
// 2. Editing a flat share inline; the check catches 99% and Scale restores 100%.
const s1=A.locator('input[aria-label="Band 1 share (%)"]');await s1.fill('72.5415');await s1.press('Tab');await page.waitForTimeout(50);
assert(Math.abs((await comps())[0].weight_spec.value-0.725415)<1e-12);
assert(/Shares total 99\.00% in the first period/.test(await A.locator('.fcb-alert').innerText()));
assert(await page.evaluate(()=>window._runs)>=1);
await A.locator('.fcb-act',{hasText:'Scale shares to 100%'}).click();
const tot=(await comps()).reduce((a,c)=>a+c.weight_spec.value,0);assert(Math.abs(tot-1)<1e-7,'scaled');
assert.strictEqual(await A.locator('.fcb-alert').count(),0);
// 3. A tag opens the Series editor beneath the row; Growth; then band 1 takes the remainder.
await A.locator('.fcb-tag[aria-label="Share path for band 2: FLAT"]').click();
assert.strictEqual(await A.locator('.fcb-edr').count(),1);
assert.deepStrictEqual(await A.locator('.fcb-ed .count-path-options button').allInnerTexts(),['Flat','Growth','Explicit schedule','Remainder']);
await A.locator('.fcb-ed .count-path-options button',{hasText:'Growth'}).click();
assert.strictEqual((await comps())[1].weight_spec.trajectory,'growth');
assert(/GROWTH/.test(await A.locator('.fcb-t tbody tr').nth(1).innerText()));
await A.locator('.fcb-tag[aria-label="Share path for band 1: FLAT"]').click();
await A.locator('.fcb-ed .count-path-options button',{hasText:'Remainder'}).click();
assert.deepStrictEqual((await comps())[0].weight_spec,{source:'remainder'});
assert(/REMAINDER/.test(await A.locator('.fcb-t tbody tr').first().innerText()));
assert(/100% less every other band/.test(await A.locator('.fcb-ed').innerText()));
await A.locator('.fcb-ed .fcb-close').click();
await A.locator('.fcb-tag[aria-label="Share path for band 3: FLAT"]').click();
assert(await A.locator('.fcb-ed .count-path-options button',{hasText:'Remainder'}).isDisabled(),'only one remainder band');
await A.locator('.fcb-ed .fcb-close').click();
// 4. Leaving the remainder keeps the share it had.
await A.locator('.fcb-tag[aria-label="Share path for band 1: REMAINDER"]').click();
const before=await page.evaluate(()=>{const c=cfg.assumptions.obs_exposures[2].fee_streams[5].driver.params.count_multiplier_spec.components;return 1-c.slice(2).reduce((a,x)=>a+x.weight_spec.value,0)-0.192687;});
await A.locator('.fcb-ed .count-path-options button',{hasText:'Flat'}).click();
const c0=(await comps())[0].weight_spec;assert.strictEqual(c0.trajectory,'flat');assert(Math.abs(c0.value-before)<1e-6,'flat value = former remainder share');
// 5. Every-period check: a later month off 100% is named.
await page.evaluate(()=>{const r=lastRes.count_breakdowns[0];r.total_share=r.total_share.map((v,t)=>t>=23?1.021:1);const c=cfg.assumptions.obs_exposures[2].fee_streams[5].driver.params.count_multiplier_spec.components;c.forEach((x,k)=>{x.weight_spec={source:'entered',trajectory:k===1?'growth':'flat',value:[0.735415,0.192687,0.048006,0.023892][k],base:0.192687,unit:'share',growth_spec:{rate:0.1,period:'year',method:'step',anchor:'model_year'}};});_fcbOpenKey=null;renderContent();});
assert(/Shares total 102\.10% in M24/.test(await A.locator('.fcb-alert').innerText()));
// 6. Switching method keeps both drafts.
await A.locator('.fcb-seg button',{hasText:'Single multiplier'}).click();
assert.strictEqual(await A.locator('input[aria-label="Count multiplier"]').count(),1);
await A.locator('.fcb-seg button',{hasText:'Weighted breakdown'}).click();
assert.strictEqual((await comps()).length,4);
// 7. Containment.
for(const width of [1440,1100]){await page.setViewportSize({width,height:1000});
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),width+' no page scroll');
  assert(await A.locator('.fcb-scroll').evaluate(el=>el.scrollWidth<=el.clientWidth+1),'no band-table horizontal scrollbar');}
assert.deepStrictEqual(errors,[]);
console.log('PASS r422 count breakdown: band table, inline flat values, tags open the Series editor beneath the row, remainder band (one only, reversible), first-period and every-period share checks, scale to 100%, results on the right, method switch keeps drafts, containment');
}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
