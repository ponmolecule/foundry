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
const KEY={lending:'lending_products',deposit:'deposit_products',obs:'obs_exposures'};
const open=(fam,i)=>page.evaluate(([k,i])=>{window._prdSel=cfg.assumptions[k][i];window._prdView='product';window._prdTab='setup';renderContent();prdGroupSetup();},[KEY[fam],i]);
const settle=()=>page.waitForTimeout(80);
const steps=async()=>(await page.$$('.lnv-ri')).length;
const go=async k=>{await (await page.$$('.lnv-ri'))[k].click();await settle();};
// 1. Rendering every step of every product leaves the configuration as it was.
// (one pass first: the console assigns stable source IDs the first time it sees each product; that is r432 behaviour)
const pass=async()=>{for(const fam of ['lending','deposit','obs']){const n=await page.evaluate(k=>cfg.assumptions[k].length,KEY[fam]);
 for(let i=0;i<n;i++){await open(fam,i);await settle();const s=await steps();for(let k=0;k<s;k++)await go(k);}}};
await pass();const cfg0=await page.evaluate(()=>JSON.stringify(cfg));await pass();
const diff=await page.evaluate(c0=>{const a=JSON.parse(c0),out=[];const walk=(x,y,p)=>{if(JSON.stringify(x)===JSON.stringify(y))return;if(x&&y&&typeof x==='object'&&typeof y==='object'){for(const k of new Set([...Object.keys(x),...Object.keys(y)]))walk(x[k],y[k],p+'.'+k);}else out.push(p+' '+JSON.stringify(x)+' -> '+JSON.stringify(y));};walk(a,cfg,'cfg');return out;},cfg0);
assert.deepStrictEqual(diff,[],'rendering mutated the configuration');
// 2. Lending balance: one right-aligned label column, amounts sized to content.
// r445: runoff is now in Structure & timing, leaving origination amount and growth in Balance.
await open('lending',0);await settle();await go(0);
const P=page.locator('.lnv-pane section.lnv-on .lfx-body.fxs-pane');assert.strictEqual(await P.count(),1,'field system on the step');
const labs=await P.locator('.fld>label:visible').evaluateAll(ls=>ls.map(l=>({a:(getComputedStyle(l).textAlign==='right'||getComputedStyle(l).justifyContent==='flex-end')?'right':getComputedStyle(l).textAlign+'/'+getComputedStyle(l).justifyContent,r:Math.round(l.getBoundingClientRect().right)})));
assert(labs.length>=2&&labs.every(l=>l.a==='right'),'right-aligned labels '+JSON.stringify(labs));assert.strictEqual(new Set(labs.map(l=>l.r)).size,1,'one label edge '+JSON.stringify(labs));
const iw=await P.locator('.lfx-in').evaluateAll(es=>es.map(e=>e.getBoundingClientRect().width));assert(iw.length&&iw.every(w=>w<=212),'amounts sized to content '+iw);
// 3. Lending pricing: yield caption lifted once; path segments drive the series select.
await go(2);const Y=page.locator('.lnv-pane section.lnv-on .fld.fxs-lifted');assert.strictEqual(await Y.count(),1,'yield row');
assert.strictEqual(await page.locator('.lnv-pane section.lnv-on').getByText('Yield (annual %)',{exact:true}).count(),1,'caption appears once');
const seg=Y.locator('.fxs-seg');assert.deepStrictEqual(await seg.locator('button').allInnerTexts(),['Flat','Growth','Schedule']);
const before=await page.evaluate(()=>JSON.stringify(cfg.assumptions.lending_products[0]));
await seg.locator('button',{hasText:'Growth'}).click();await settle();
const after=await page.evaluate(()=>JSON.stringify(cfg.assumptions.lending_products[0]));assert(after!==before&&/"growth"/.test(after),'path change written');
assert.strictEqual(await page.locator('.lnv-pane section.lnv-on .fld.fxs-lifted .fxs-seg button.on').innerText(),'Growth');
// 4. Deposit pricing: no control wider than its content or 320px; rate-type segments compact.
await open('deposit',0);await settle();await go(1);
const dw=await page.locator('.lnv-pane section.lnv-on .lfx-body input:visible,.lnv-pane section.lnv-on .lfx-body select:visible').evaluateAll(es=>es.map(e=>({w:e.getBoundingClientRect().width,fit:parseFloat(e.style.minWidth)||0})));
assert(dw.every(x=>x.w<=Math.max(322,x.fit+1)),'deposit controls sized '+JSON.stringify(dw));
const lseg=await page.locator('.lnv-pane section.lnv-on .lfx-seg').first().evaluate(e=>e.getBoundingClientRect().width);assert(lseg<360,'compact rate-type switch '+lseg);
// 5. Narrow step (Assumptions panel open): labels stack above their fields.
await page.setViewportSize({width:1100,height:1000});await page.evaluate(()=>{document.body.classList.remove('insp-closed');renderContent();prdGroupSetup();});await settle();
const bw=await page.locator('.lnv-pane section.lnv-on .lfx-body').evaluate(e=>e.getBoundingClientRect().width);
if(bw<=470){const al=await page.locator('.lnv-pane section.lnv-on .lfx-body .fld>label:visible').first().evaluate(l=>getComputedStyle(l).textAlign);assert.strictEqual(al,'left','stacked labels');}
await page.setViewportSize({width:1600,height:1000});await page.evaluate(()=>{document.body.classList.add('insp-closed');});
// 6. Acquisition channel editor: label column, remove in the header, path buttons write the driver spec.
await page.evaluate(()=>{currentTab='config';window._cfgModule='cac';window._cfgSectionOpen={customeracq:true};renderContent();});await settle();
const ri=page.locator('.cacn-ri:not(.all)').first();if(await ri.count())await ri.click();await settle();
await page.locator('text=Edit ›').first().click();await settle();
const E=page.locator('.cacn-editor.fxs-cac');assert.strictEqual(await E.count(),1,'channel editor');
const cl=await E.locator('.fxs-crow>.fxs-cl:visible').evaluateAll(ls=>ls.map(l=>Math.round(l.getBoundingClientRect().right)));
assert(cl.length>=4&&new Set(cl).size===1,'channel labels on one edge '+cl);
assert.strictEqual(await E.locator('.cfg-md-head .fxs-cac-rm').innerText(),'Remove channel');
const ch0=()=>page.evaluate(()=>{const F=Object.values(cfg.assumptions.cac_feeds)[0];return JSON.parse(JSON.stringify(F.channels[0]));});
const nameIn=E.locator('.fxs-crow input').first();await nameIn.fill('Affiliate network');await nameIn.press('Tab');await settle();
assert.strictEqual((await ch0()).name,'Affiliate network','name still edits the channel');
const segs=E.locator('.fxs-seg');assert((await segs.count())>=2,'path segments');
const flatRow=E.locator('.fxs-crow',{has:page.locator('.fxs-seg button.on',{hasText:'Flat'})}).last();
const lab=await flatRow.locator('.fxs-cl').innerText();
const c0=JSON.stringify(await ch0());await flatRow.locator('.fxs-seg button',{hasText:'Growth'}).click();await settle();
const c1=JSON.stringify(await ch0());assert(c1!==c0&&/"growth"/.test(c1),lab+' path written');
const er=await page.locator('.cacn-editor').evaluate(e=>{const r=e.getBoundingClientRect();return [...e.querySelectorAll('input,select,button')].filter(x=>x.offsetParent).filter(x=>x.getBoundingClientRect().right>r.right+1).map(x=>x.outerHTML.slice(0,60));});
assert.deepStrictEqual(er,[],'controls inside the editor');
// 7. Feed settings share the label column.
await page.locator('text=Edit feed settings').click();await settle();
const fs2=page.locator('.cacn-set.fxs-cacset');assert.strictEqual(await fs2.count(),1);
const fl=await fs2.locator('.wf-field>.wf-field-label').evaluateAll(ls=>ls.map(l=>getComputedStyle(l).textAlign));assert(fl.length>=3&&fl.every(a=>a==='right'));
assert.deepStrictEqual(errors,[]);
console.log('r434 field system on products and acquisition: ok');
}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
