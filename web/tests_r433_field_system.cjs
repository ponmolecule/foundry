// r433: field system in the fee-stream editor — one right-aligned label column, fields sized to content, path controls as
// segmented buttons that drive the underlying selects, participation share as a modifier row, schedules as period grids,
// results in the right-hand column, and rendering that leaves the configuration untouched.
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
  window._prdSel=cfg.assumptions.obs_exposures[2];window._prdView='product';window._prdTab='streams';},fx);
const open=(si,tab)=>page.evaluate(([si,tab])=>{window._stSelObj=cfg.assumptions.obs_exposures[2].fee_streams[si];window._stTab=tab;renderContent();},[si,tab]);
const S=si=>page.evaluate(si=>JSON.parse(JSON.stringify(cfg.assumptions.obs_exposures[2].fee_streams[si])),si);
const settle=()=>page.waitForTimeout(60);
// 1. Rendering every step of every stream leaves the configuration as it was (after the console's own load-time normalisation).
await open(0,'activity');const cfg0=await page.evaluate(()=>JSON.stringify(cfg));
for(const si of [0,1,2,3,4,5])for(const tab of ['activity','pricing','timing','costs'])await open(si,tab);
const diff=await page.evaluate(c0=>{const a=JSON.parse(c0),out=[];const walk=(x,y,p)=>{if(JSON.stringify(x)===JSON.stringify(y))return;if(x&&y&&typeof x==='object'&&typeof y==='object'){for(const k of new Set([...Object.keys(x),...Object.keys(y)]))walk(x[k],y[k],p+'.'+k);}else out.push(p);};walk(a,cfg,'cfg');return out;},cfg0);
assert.deepStrictEqual(diff,[],'rendering mutated the configuration');
// 2. Layout: labels share one right-aligned column; results sit to the right; the in-form copy is hidden.
await open(0,'activity');const B=page.locator('.lfx-sted .st-body');
const labs=await B.locator('.fld>label').evaluateAll(ls=>ls.filter(l=>l.offsetParent&&l.textContent.trim()).map(l=>({a:getComputedStyle(l).textAlign,r:Math.round(l.getBoundingClientRect().right)})));
assert(labs.length>=4,'labelled rows');assert(labs.every(l=>l.a==='right'),'labels right-aligned');
assert.strictEqual(new Set(labs.map(l=>l.r)).size,1,'labels end on one edge: '+JSON.stringify(labs));
const ro=await page.locator('.lfx-sted .lfx-ro').boundingBox(),body=await page.locator('.lfx-sted .lfx-body').boundingBox();
assert(ro&&ro.width>200&&ro.x>=body.x+body.width-1,'results column on the right');
assert.strictEqual(await page.locator('.lfx-sted .fee-stream-result-preview:visible').count(),0,'no duplicate results in the form');
// 3. Fields sized to content, not to the column.
// selects are fitted to their longest option by the console (inline min-width); everything else caps at 320px.
const widths=await B.locator('select:visible,input:visible:not(.fxs-cell)').evaluateAll(es=>es.map(e=>({t:e.tagName+(e.getAttribute('inputmode')||e.type||''),w:e.getBoundingClientRect().width,fit:parseFloat(e.style.minWidth)||0})));
assert(widths.every(x=>x.w<=Math.max(322,x.fit+1)),'no control wider than its content or 320px: '+JSON.stringify(widths));
assert.strictEqual(await B.locator('select.fxs-hid').evaluateAll(es=>es.filter(e=>e.getBoundingClientRect().width>2).length),0,'segment-driven selects take no room');
assert(widths.filter(x=>/decimal|number/.test(x.t)).every(x=>x.w<=152),'numbers ≤ 150px');
const hs=await B.locator('select:visible:not(.fxs-hid)').evaluateAll(es=>es.map(e=>Math.round(e.getBoundingClientRect().height)));
assert(hs.length&&hs.every(h=>h===32),'32px selects: '+hs);
// 4. The count schedule is a period grid; a cell writes its period key, blank removes it.
const G=B.locator('.fxs-sched[data-fxs-sched="level"]');assert.strictEqual(await G.count(),1,'level grid');
const cell=G.locator('input.fxs-cell').nth(1),k=(await cell.getAttribute('aria-label')).match(/(\d+)$/)[1];
await cell.fill('1,500');await cell.press('Tab');await settle();
let sch=(await S(0)).driver.params.level_schedule.schedule;assert.strictEqual(sch[k],1500,'cell '+k+' saved');
assert(await page.evaluate(()=>window._runs)>=1,'edit reruns');
const cell2=page.locator('.fxs-sched[data-fxs-sched="level"] input.fxs-cell').nth(1);assert.strictEqual(await cell2.inputValue(),'1,500');
assert(await cell2.evaluate(e=>e.classList.contains('set')));
await cell2.fill('');await cell2.press('Tab');await settle();
assert(!(k in (await S(0)).driver.params.level_schedule.schedule),'blank removes the key');
// 5. Path is a segmented control that drives the select; Flat puts the path beside the count.
const seg=B.locator('.fxs-seg[aria-label="Count path"]');assert.strictEqual(await seg.count(),1,'count path segments');
assert.deepStrictEqual(await seg.locator('button').allInnerTexts(),['Flat','Growth','Schedule']);
assert.strictEqual(await seg.locator('button.on').innerText(),'Schedule');
await seg.locator('button',{hasText:'Flat'}).click();await settle();
assert.strictEqual((await S(0)).driver.trajectory,'flat');
const row=B.locator('.fld.fxs-row');assert.strictEqual(await row.count(),1,'one count row');
assert.strictEqual(await row.locator('.fxs-seg button.on').innerText(),'Flat');
const rs=await row.locator('.fxs-seg').boundingBox(),ri=await row.locator('input').first().boundingBox();
assert(Math.abs(rs.y-ri.y)<4&&ri.x>rs.x,'value beside its path');
await row.locator('input').first().fill('1250');await row.locator('input').first().press('Tab');await settle();
assert.strictEqual((await S(0)).driver.params.base,1250);
// 6. Participation share: its own row; Schedule turns it into a monthly grid stored as shares.
await B.locator('button',{hasText:'+ Participation share'}).click();await settle();
const M=B.locator('.fld.fxs-mod');assert.strictEqual(await M.count(),1);
assert(/Participation share/.test(await M.locator(':scope>label').innerText()));
const mb=await M.boundingBox(),cb=await row.boundingBox();assert(mb.y>=cb.y+cb.height-1,'modifier sits under the count');
await M.locator('.fxs-seg button',{hasText:'Schedule'}).first().click();await settle();
assert.strictEqual((await S(0)).driver.params.share_spec.trajectory,'explicit');
const MG=page.locator('.lfx-sted .fxs-mod .fxs-sched');assert.strictEqual(await MG.count(),1,'share grid');
const c3=MG.locator('input.fxs-cell').nth(2);await c3.fill('75');await c3.press('Tab');await settle();
const sv=(await S(0)).driver.params.share_spec.values;assert(Math.abs(sv[2]-0.75)<1e-12,'stored as a share: '+JSON.stringify(sv));
const res=page.locator('.lfx-sted .fxs-mod .fxs-seg.fxs-res');if(await res.count()){await res.locator('button',{hasText:'Smooth'}).click();await settle();assert.strictEqual((await S(0)).driver.params.share_spec.resolution,'smooth');}
await page.locator('.lfx-sted .fxs-mod .fxs-link',{hasText:'Paste values'}).click();
assert(await page.locator('.lfx-sted .fxs-mod .fxs-paste textarea').isVisible(),'paste stays available');
await page.locator('.lfx-sted .fxs-mod .participation-remove').click();await settle();
assert(!('share_spec' in (await S(0)).driver.params),'removed');
// 7. Pricing: cadence segments drive the select.
await open(0,'pricing');const per=page.locator('.lfx-sted .st-body .fxs-seg.fxs-period').first();
if(await per.count()){const sel=per.locator('xpath=preceding-sibling::select[1]');const btn=per.locator('button:not(.on)').first(),txt=(await btn.innerText()).toLowerCase();
  await btn.click();await settle();await open(0,'pricing');
  assert.strictEqual(await page.locator('.lfx-sted .st-body .fxs-seg.fxs-period').first().locator('button.on').innerText(),txt[0].toUpperCase()+txt.slice(1));}
// 8. Narrow container stacks to one column.
await page.setViewportSize({width:560,height:1000});await open(1,'activity');
const nl=await page.locator('.lfx-sted .st-body .fld>label:visible').first().evaluate(l=>getComputedStyle(l).textAlign);assert.strictEqual(nl,'left');
assert.deepStrictEqual(errors,[]);
console.log('r433 field system: ok');
}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
