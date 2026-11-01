// r435: use of space and product schedules. Two ends of one range share a row; a path sits beside its value; loan-production
// and settings panels use the label column; product schedules are period grids whose cells store exactly what the existing
// paste path stores for the same numbers.
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
await page.evaluate(f=>{cfg=normalizeCfg(f.cfg);lastRes=f.result;refresh=()=>{};scheduleAutosave=()=>{};appStatus=()=>{};document.body.classList.add('insp-closed');renderTabs();setTab('products');},fx);
const settle=()=>page.waitForTimeout(80);
const KEY={lending:'lending_products',deposit:'deposit_products',obs:'obs_exposures'};
const open=(fam,i)=>page.evaluate(([k,i])=>{window._prdSel=cfg.assumptions[k][i];window._prdView='product';window._prdTab='setup';renderContent();prdGroupSetup();},[KEY[fam],i]);
const go=async k=>{await (await page.$$('.lnv-ri'))[k].click();await settle();};
// 1. Grid cells store exactly what paste stores, for every unit kind.
const eq=await page.evaluate(()=>{const out=[];const P='assumptions.lending_products.0._fxs_probe';
 const base={rate:[0.065,0.0675,0.07,0.071],money:[1250000,1300000,1400000],count:[12,14,15.5],dollars:[1500000,1550000],multiplier:[2500,2600],days:[30,45],multiple:[1.1,1.2]};
 for(const [kind,vals] of Object.entries(base)){
  const sc=kind==='rate'?100:(['multiple','count','dollars','days'].includes(kind)?1:0.001);
  for(const k of [2,vals.length+2]){
   setPath(P,{source:'entered',trajectory:'explicit',cadence:'year',resolution:'step',extend:'hold',values:vals.slice()});
   fxsFaSet(P,k,'7.25',kind);const viaGrid=JSON.parse(JSON.stringify(getPath(P).values));
   const shown=vals.map(v=>v*sc);while(shown.length<k-1)shown.push(shown[shown.length-1]);shown[k-1]=7.25;
   setPath(P,{source:'entered',trajectory:'explicit',cadence:'year',resolution:'step',extend:'hold',values:vals.slice()});
   const ta=document.createElement('textarea');ta.id='fxs_probe_ta';ta.value=shown.map(x=>String(x)).join('\n');document.body.appendChild(ta);faSeriesPaste(P,'fxs_probe_ta',kind);ta.remove();
   const viaPaste=JSON.parse(JSON.stringify(getPath(P).values));
   out.push({kind,k,ok:viaGrid.length===viaPaste.length&&viaGrid.every((v,i)=>Math.abs(v-viaPaste[i])<=1e-9*Math.max(1,Math.abs(v))),viaGrid,viaPaste});}}
 delete cfg.assumptions.lending_products[0]._fxs_probe;return out;});
for(const r of eq)assert(r.ok,`${r.kind} cell ${r.k}: grid ${JSON.stringify(r.viaGrid)} vs paste ${JSON.stringify(r.viaPaste)}`);
// 2. The yield schedule is a grid on the pricing step; a cell edit writes the yield.
await open('lending',0);await settle();await go(2);
const Y=page.locator('.lnv-pane section.lnv-on .fld.fxs-lifted');await Y.locator('.fxs-seg button',{hasText:'Schedule'}).click();await settle();await page.waitForTimeout(60);
const G=page.locator('.lnv-pane section.lnv-on .fxs-fagrid');assert.strictEqual(await G.count(),1,'yield grid');
assert.strictEqual(await page.locator('.lnv-pane section.lnv-on .sec-managed-explicit-closed, .lnv-pane section.lnv-on .sec-managed-explicit').count(),0,'old schedule panel replaced');
const yp=await G.getAttribute('data-fxs-path');const c2=G.locator('input.fxs-cell').nth(1);await c2.fill('7.25');await c2.press('Tab');await page.waitForTimeout(120);
const yv=await page.evaluate(p=>getPath(p).values,yp);assert(Math.abs(yv[1]-0.0725)<1e-12,'yield cell stored as a rate '+JSON.stringify(yv));
await page.locator('.lnv-pane section.lnv-on .fxs-fagrid .fxs-link',{hasText:'Paste values'}).click();
assert(await page.locator('.lnv-pane section.lnv-on .fxs-fagrid .fxs-paste textarea').isVisible(),'paste kept');
// 3. Deposit floating pricing: rate floor and cap share one row and still write their own fields.
let dep=-1;for(let i=0;i<6;i++){await open('deposit',i);await settle();await go(1);if(await page.locator('.lnv-pane section.lnv-on .fld label',{hasText:'Rate bounds'}).count()){dep=i;break;}}
assert(dep>=0,'a floating deposit shows Rate bounds');
const RB=page.locator('.lnv-pane section.lnv-on .fld',{has:page.locator(':scope>label',{hasText:'Rate bounds'})});
const ins=RB.locator('.fxs-pair input');assert.strictEqual(await ins.count(),2,'floor and cap inputs');
const b0=await ins.nth(0).boundingBox(),b1=await ins.nth(1).boundingBox();assert(Math.abs(b0.y-b1.y)<2&&b1.x>b0.x,'side by side');
assert.deepStrictEqual(await RB.locator('.fxs-pcap').allInnerTexts(),['Floor','Cap']);
assert.strictEqual(await page.locator('.lnv-pane section.lnv-on .fld:visible>label',{hasText:/^Rate (floor|cap)/}).count(),0,'old rows hidden');
const d0=await page.evaluate(i=>JSON.stringify(cfg.assumptions.deposit_products[i]),dep);await ins.nth(1).fill('4.5');await ins.nth(1).press('Tab');await settle();
const d1=await page.evaluate(i=>JSON.stringify(cfg.assumptions.deposit_products[i]),dep);assert(d1!==d0&&/0\.045|4\.5/.test(d1),'cap written');
// 4. Product settings panel: one label column.
await page.locator('text=Edit settings').click();await settle();
const sl=await page.locator('.fxs-drawer .lnv-dgrid label:visible').evaluateAll(ls=>ls.map(l=>Math.round(l.getBoundingClientRect().right)));
assert(sl.length>=2&&new Set(sl).size===1,'settings labels on one edge '+sl);await page.locator('.lnv-ps button',{hasText:'Done'}).click().catch(()=>{});
// 5. Fee-stream pricing: the fee path sits beside the fee, its period after it; timing start and end on one row.
await page.evaluate(()=>{window._prdSel=cfg.assumptions.obs_exposures[2];window._prdView='product';window._prdTab='streams';window._stSelObj=cfg.assumptions.obs_exposures[2].fee_streams[0];window._stTab='pricing';renderContent();});await settle();
const PV=page.locator('.lfx-sted .st-body .fld .fxs-pathval');assert.strictEqual(await PV.count(),1,'path beside value');
assert.strictEqual(await page.locator('.lfx-sted .st-body .fld:visible>label',{hasText:/^Fee path$/}).count(),0,'fee path row folded');
const s0=await page.evaluate(()=>cfg.assumptions.obs_exposures[2].fee_streams[0].pricing&&JSON.stringify(cfg.assumptions.obs_exposures[2].fee_streams[0]));
await PV.locator('.fxs-seg.fxs-path button',{hasText:'Growth'}).click();await settle();
assert.notStrictEqual(await page.evaluate(()=>JSON.stringify(cfg.assumptions.obs_exposures[2].fee_streams[0])),s0,'path still writes');
await page.evaluate(()=>{window._stTab='timing';renderContent();});await settle();
const RM=page.locator('.lfx-sted .st-body .fld',{has:page.locator(':scope>label',{hasText:'Revenue months'})});assert.strictEqual(await RM.locator('.fxs-pair input').count(),2,'start and end together');
assert.strictEqual(await RM.locator('.fxs-pair input').nth(1).getAttribute('placeholder'),'never');
// 6. Acquisition feed settings: opening customers and AUC as one opening book row.
await page.evaluate(()=>{currentTab='config';window._cfgModule='cac';window._cfgSectionOpen={customeracq:true};renderContent();});await settle();
const ri=page.locator('.cacn-ri:not(.all)').first();if(await ri.count())await ri.click();await settle();
await page.locator('text=Edit feed settings').click();await settle();
const OB=page.locator('.fxs-cacset .fxs-pairrow');assert.strictEqual(await OB.count(),1,'opening book row');
const oi=OB.locator('input');assert.strictEqual(await oi.count(),2);await oi.nth(0).fill('1200');await oi.nth(0).press('Tab');await settle();
assert.strictEqual(await page.evaluate(()=>+Object.values(cfg.assumptions.cac_feeds)[0].beginning_customers),1200,'opening customers written');
assert.deepStrictEqual(errors,[]);
console.log('r435 use of space and product schedules: ok');
}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
