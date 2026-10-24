// r393: customer acquisition edits through a feed rail. All feeds compares every feed; a feed shows its settings band,
// a channel results table and, while editing, the existing channel driver editor inline beneath the table.
const {chromium}=require('playwright'),fs=require('fs'),assert=require('assert'),{execFileSync}=require('child_process');
(async()=>{
const fixture=JSON.parse(execFileSync('python3',['-c',`import json,copy
from foundry.v2.tests_r376_deferred import config
from foundry.v2.run_q import run_v2
c=config();c['assumptions']['cac_feeds']['Advances']=copy.deepcopy(c['assumptions']['cac_feeds']['Practices']);f=c['assumptions']['cac_feeds']['Advances'];f['series_id']='advance-auc';f['customer_count_series_id']='advance-customers'
r=run_v2(c);print(json.dumps({'cfg':c,'result':r}))`],{encoding:'utf8'}));
const html=fs.readFileSync('web/console_v2.html','utf8').replace('<script src="/web/rates_workspace.js"></script>','<script>'+fs.readFileSync('web/rates_workspace.js','utf8')+'</script>').replace('<head>','<head><script>window.V3=true;window.V31=true;</script>').replace(/renderTabs\(\);\nwhoami\(\)\.then[^\n]+/,'');
const browser=await chromium.launch({executablePath:process.env.FOUNDRY_CHROMIUM_PATH,args:['--no-sandbox','--disable-gpu','--single-process','--no-zygote'],headless:true});
try{
const page=await browser.newPage({viewport:{width:1600,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>d.accept());page.setDefaultTimeout(15000);
await page.route('**/*',r=>r.fulfill({status:200,json:{}}));await page.goto('http://foundry.test');await page.setContent(html);
await page.evaluate(f=>{cfg=f.cfg;lastRes=f.result;currentTab='config';window._cfgModule='cac';window._cfgSectionOpen={customeracq:true};refresh=()=>{};scheduleAutosave=()=>{};renderContent();},fixture);
const root=page.locator('#card-cac');
const st=()=>page.evaluate(()=>{const c=document.querySelector('#card-cac');return {rail:[...c.querySelectorAll('.cacn-ri')].map(x=>x.querySelector('.t').textContent),on:c.querySelector('.cacn-ri.on .t')?.textContent,
  rows:c.querySelectorAll('.cacn-ws.all .cacn-t tbody tr').length,chRows:c.querySelectorAll('.cacn-ch tbody tr').length,editing:c.querySelectorAll('.cacn-ch tr.sel').length,editor:!!c.querySelector('.cacn-main>.cacn-editor'),
  setOpen:!!c.querySelector('.cacn-set:not([hidden])'),wsH:c.querySelector('.cacn-ws').offsetHeight,visibleDisclosures:[...c.querySelectorAll('details.cac-feed-disclosure')].filter(d=>d.offsetParent).length,strip:c.querySelector('.cacn-es')?.innerText||''};});
// 1. Two feeds open on All feeds: one comparison row per feed, engine figures in the strip, old disclosures out of view.
let s=await st();const F=await page.evaluate(()=>Object.keys(cfg.assumptions.cac_feeds));
assert.deepStrictEqual(s.rail,['All feeds',...F]);assert.strictEqual(s.on,'All feeds');assert.strictEqual(s.rows,F.length);assert.strictEqual(s.visibleDisclosures,0,'feed disclosures are replaced by the rail');
assert(/FEEDS · CHANNELS/.test(s.strip)&&/\d/.test(s.strip),'engine strip');
const y1=await page.evaluate(fn=>lastRes.customer_acquisition[fn].annual[0].end_cust,F[0]);
assert((await root.locator('.cacn-t tbody tr').first().innerText()).includes(Number(y1).toLocaleString('en-US',{maximumFractionDigits:0})),'comparison reads engine customers');
const browseH=s.wsH;
// 2. Selecting a feed (row or rail) shows its band, channel table and results column; settings stay closed.
await root.locator('.cacn-t tbody tr').first().click();s=await st();assert.strictEqual(s.on,F[0]);
const chN=await page.evaluate(fn=>cfg.assumptions.cac_feeds[fn].channels.length,F[0]);assert.strictEqual(s.chRows,chN);assert.strictEqual(s.setOpen,false);assert.strictEqual(s.editor,false);
assert(await root.locator('.cacn-band').isVisible()&&await root.locator('.cacn-ro').isVisible(),'band and results column');
assert(s.wsH>=browseH-1,'workspace keeps its height while browsing');
// 3. Feed settings open in place and hold the existing controls; edits use the existing handlers.
await root.locator('.cacn-band .cacn-btn').click();s=await st();assert(s.setOpen);
const nm=root.locator('.cacn-set input[aria-label="Opening customers"]');await nm.fill('1234');await nm.dispatchEvent('change');
assert.strictEqual(await page.evaluate(fn=>cfg.assumptions.cac_feeds[fn].beginning_customers,F[0]),1234);
await root.locator('.cacn-band .cacn-btn').click();assert.strictEqual((await st()).setOpen,false);
// 4. Edit opens the channel's driver editor beneath the table; the table stays and marks the row.
await root.locator('.cacn-ch tbody tr').nth(0).locator('.cacn-lnk').click();s=await st();
assert(s.editor&&s.editing===1&&s.chRows===chN,'inline editor beneath the summary table');
assert((await root.locator('.cacn-ch tr.sel').innerText()).includes('EDITING'));
assert(s.wsH>=browseH-1,'workspace grows (never shrinks) while editing');
const ch0=await page.evaluate(fn=>cfg.assumptions.cac_feeds[fn].channels[0].name,F[0]);
assert((await root.locator('.cacn-editor .cfg-md-head').innerText()).includes(ch0),'editor is the selected channel');
assert(/NEW CUSTOMERS \/ MONTH/.test(await root.locator('.cacn-ro').innerText()),'results column follows the channel');
if(chN>1){await root.locator('.cacn-ch tbody tr').nth(1).locator('.cacn-lnk').click();const ch1=await page.evaluate(fn=>cfg.assumptions.cac_feeds[fn].channels[1].name,F[0]);assert((await root.locator('.cacn-editor .cfg-md-head').innerText()).includes(ch1),'switching channel');}
await root.locator('.cacn-done .cacn-btn').click();s=await st();assert(!s.editor&&s.editing===0,'Done closes the editor');
// 5. Results refresh in place: inputs stay mounted, figures update.
await root.locator('.cacn-band .cacn-btn').click();
await page.evaluate(()=>{window._held=document.querySelector('.cacn-set input[aria-label="Feed name"]');refreshConfigPreviews();});
assert(await page.evaluate(()=>window._held&&window._held===document.querySelector('.cacn-set input[aria-label="Feed name"]')),'inputs stay mounted across refresh');
// 6. Keyboard moves between feeds; rename keeps the selection; Create feed selects the new feed with settings open.
await root.locator('.cacn-ri.on').focus();await page.keyboard.press('ArrowDown');assert.strictEqual((await st()).on,F[1]);
await page.evaluate(fn=>renameCacFeed(fn,'Renamed feed'),F[1]);assert.strictEqual((await st()).on,'Renamed feed');
await root.locator('.cacn-add').click();s=await st();assert.strictEqual(s.rail.length,F.length+2);assert.strictEqual(s.on,s.rail[s.rail.length-1]);assert(s.setOpen,'new feed opens its settings');
// 7. Containment at three widths.
for(const width of [1440,1024,768]){await page.setViewportSize({width,height:1100});
  const bad=await page.evaluate(()=>{const r=document.querySelector('#card-cac').getBoundingClientRect();return [...document.querySelectorAll('#card-cac input,#card-cac select,#card-cac button')].filter(e=>e.getClientRects().length).filter(e=>{const b=e.getBoundingClientRect();return b.left<r.left-2||b.right>r.right+2}).map(e=>e.outerHTML.slice(0,100));});
  assert.deepStrictEqual(bad,[],width+' containment');assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),width+' no page scroll');}
assert.deepStrictEqual(errors,[]);
console.log('PASS r393 acquisition layout: feed rail, all-feeds comparison from engine figures, feed band with settings in place, channel table with inline editor beneath, results column follows the channel, mounted inputs across refresh, keyboard, rename, create, containment');
}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
