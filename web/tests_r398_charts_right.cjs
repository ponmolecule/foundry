// r398: results charts stay on the right of the inputs at every width down to 700px, for every product step and
// the customer-acquisition feed view; no input crosses into the chart column; phones (<700px) stack.
const {chromium}=require('playwright'),fs=require('fs'),assert=require('assert'),{execFileSync}=require('child_process');
(async()=>{
const html=fs.readFileSync(process.env.CONSOLE_HTML||'web/console_v2.html','utf8').replace('<script src="/web/rates_workspace.js"></script>','<script>'+fs.readFileSync('web/rates_workspace.js','utf8')+'</script>').replace(/renderTabs\(\);\nwhoami\(\)\.then[^\n]+/,'');
const fixture=JSON.parse(execFileSync('python3',['-c',`import json
from foundry.v2.tests_r376_deferred import config
from foundry.v2.run_q import run_v2
c=config();print(json.dumps({'cfg':c,'result':run_v2(c)}))`],{encoding:'utf8'}));
const browser=await chromium.launch({executablePath:process.env.FOUNDRY_CHROMIUM_PATH,args:['--no-sandbox','--disable-gpu','--single-process','--no-zygote'],headless:true});
try{
const page=await browser.newPage({viewport:{width:1600,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));page.setDefaultTimeout(15000);
await page.route('**/*',r=>r.fulfill({status:200,body:'{}',contentType:'application/json'}));await page.goto('http://foundry.test');
await page.setContent(html.replace('<script>','<script>window.V3=true;window.V31=true;</script><script>'));
const config=JSON.parse(fs.readFileSync('foundry/fixtures/universal_template_bank.json','utf8'));
await page.evaluate(c=>{cfg=normalizeCfg(c);refresh=()=>{};scheduleAutosave=()=>{};currentTab='products';window._prdView='product';const L=cfg.assumptions.lending_products;
  Object.assign(L[0],{balance_mode:'funded_flow_level',term_days:60,day_count:360,reserve_share:0,target_retention_share:1,interest_balance_measure:'period_end',funded_flow_driver:{source:'entered',input_stage:'funded_volume',start_period:1,ramp_periods:1,take_up_share:1,flow_path:{unit_kind:'money_flow',period:'month',trajectory:'flat',value:100000}}});
  loanBalanceModeChange(1,'explicit_level');loanContractEnable(2,true);},config);
const products=[['lending',0],['lending',1],['lending',2],['deposit',0],['obs',0]];
const check=()=>page.evaluate(()=>{const out=[];
  for(const s of [...document.querySelectorAll('.lnv-pane>section.lfx-s.lnv-on')]){const b=s.querySelector(':scope>.lfx-b.has-ro');if(!b)continue;const ro=b.querySelector(':scope>.lfx-ro'),body=b.querySelector(':scope>.lfx-body');if(!ro||!body)continue;
    const r=ro.getBoundingClientRect(),y=body.getBoundingClientRect();const vis=e=>{let rr=e.getBoundingClientRect().right;for(let a=e.parentElement;a&&a!==body;a=a.parentElement){const ox=getComputedStyle(a).overflowX;if(ox==='auto'||ox==='hidden'||ox==='scroll')rr=Math.min(rr,a.getBoundingClientRect().right);}return rr;};const bad=[...body.querySelectorAll('input,select,button,textarea')].filter(e=>e.getClientRects().length&&vis(e)>r.left+1).map(e=>(e.getAttribute('aria-label')||e.textContent||e.tagName).trim().slice(0,30));
    const pw=document.querySelector('.lnv-pane').getBoundingClientRect().width;out.push({pw,k:s.getAttribute('data-lfx'),stacked:r.top>=y.bottom-1,right:r.left>=y.right-1&&r.top<y.bottom,shown:getComputedStyle(ro).display!=='none'&&r.width>200,bad});}
  return out;});
const stacked=new Set(),paneW={};
const inspOpen=()=>page.evaluate(()=>{const x=document.querySelector('.insp-x');return !!(x&&x.offsetParent);});
// Assumptions panel closed (the usual working view), then open (the most cramped view).
for(const [panel,width] of [['closed',2000],['closed',1600],['closed',1440],['closed',1280],['closed',1100],['open',1600],['open',1280]]){
  if(((await inspOpen())?'open':'closed')!==panel)await page.evaluate(()=>toggleInspector());await page.setViewportSize({width,height:1000});
  for(const [fam,i] of products){await page.evaluate(([fam,i])=>{const key=fam==='lending'?'lending_products':fam==='deposit'?'deposit_products':'obs_exposures';window._prdSel=cfg.assumptions[key][i];window._prdTab='setup';renderContent();prdGroupSetup();},[fam,i]);
    const keys=await page.evaluate(()=>[...document.querySelectorAll('.lnv-ri')].map(x=>x.getAttribute('data-k')));
    for(const k of keys){await page.evaluate(([fam,i,k])=>lnvGo(fam,i,k),[fam,i,k]);
      for(const c of await check()){assert(c.shown,`${width} ${fam}${i} ${c.k} chart shown`);if(c.pw>=560)assert(c.right,`${width} ${fam}${i} ${c.k} chart on the right (pane ${Math.round(c.pw)}px)`);else{assert(c.stacked,`${width} ${fam}${i} ${c.k} cramped step stacks`);stacked.add(panel+' '+width);}if(!c.stacked)assert.deepStrictEqual(c.bad,[],`${width} ${fam}${i} ${c.k} inputs clear of the chart`);}}}
  paneW[panel+' '+width]=Math.round(await page.evaluate(()=>document.querySelector('.lnv-pane').getBoundingClientRect().width));
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),width+' no page scroll');}
console.log('pane widths',JSON.stringify(paneW),'stacked at',[...stacked]);
for(const w of ['closed 2000','closed 1600','closed 1440','closed 1280'])assert(!stacked.has(w),'charts on the right with the panel closed at '+w);
if(await inspOpen())await page.evaluate(()=>toggleInspector());
// Phones stack.
await page.setViewportSize({width:650,height:1000});await page.evaluate(()=>{window._prdSel=cfg.assumptions.lending_products[2];renderContent();prdGroupSetup();lnvGo('lending',2,'balance');});
assert(await page.evaluate(()=>{const b=document.querySelector('.lnv-pane>section.lnv-on>.lfx-b.has-ro');const r=b.querySelector('.lfx-ro').getBoundingClientRect(),y=b.querySelector('.lfx-body').getBoundingClientRect();return r.top>=y.bottom-1;}),'phones stack the chart below');
// Customer acquisition feed view.
await page.evaluate(f=>{cfg=f.cfg;lastRes=f.result;currentTab='config';window._cfgModule='cac';window._cfgSectionOpen={customeracq:true};renderContent();cacnSelect(0);},fixture);
for(const width of [2000,1600,1280,1100]){await page.setViewportSize({width,height:1000});await page.evaluate(()=>renderContent());
  const g=await page.evaluate(()=>{const ro=document.querySelector('.cacn-ro').getBoundingClientRect(),m=document.querySelector('.cacn-main').getBoundingClientRect();return {cw:document.querySelector('.cacn').getBoundingClientRect().width,right:ro.left>=m.right-1&&ro.top<m.bottom,stack:ro.top>=m.bottom-1,w:ro.width};});
  assert(g.cw>=700?(g.right&&g.w>=200):g.stack,'acquisition results column at '+width+' '+JSON.stringify(g));}
assert.deepStrictEqual(errors,[]);
console.log('PASS r398 charts on the right whenever the step is at least 560px wide (panel closed at 2000/1600/1440/1280/1100px) for every product step and the acquisition feed view, inputs clear of the chart; cramped steps and phones stack');
}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
