const {chromium}=require('playwright'),fs=require('fs'),assert=require('assert'),{execFileSync}=require('child_process');
(async()=>{
const cases=JSON.parse(execFileSync('python',['-c',`import json,copy
from foundry.v2.tests_r408_product_formulas import config
from foundry.v2.product_formula_costs import move_formula
from foundry.v2.run_q import run_v2
out=[]
for ppy in (12,4):
 for collection,offset,family in [('obs_exposures',0,'obs'),('deposit_products',2000,'deposit'),('lending_products',1000,'lending')]:
  c=config(ppy)
  if not c['assumptions'].get(collection):
   from foundry.v2.tests_fee_quantity_links import fixture
   c['assumptions'][collection]=copy.deepcopy(fixture()['assumptions'][collection])
  i=len(c['assumptions'][collection])-1
  c=move_formula(c,collection,i,'agreement','fraud')
  c=move_formula(c,collection,i,'agreement','participation')
  r=run_v2(c)
  out.append(dict(cfg=c,result=r,collection=collection,index=i,fi=offset+i,family=family,ppy=ppy))
print(json.dumps(out))`],{encoding:'utf8',maxBuffer:1<<28}));
const html=fs.readFileSync('web/console_v2.html','utf8').replace('<script src="/web/rates_workspace.js"></script>','<script>'+fs.readFileSync('web/rates_workspace.js','utf8')+'</script>').replace('<head>','<head><script>window.V3=true;window.V31=true;</script>').replace(/renderTabs\(\);\nwhoami\(\)\.then[^\n]+/,'');
const browser=await chromium.launch({executablePath:process.env.FOUNDRY_CHROMIUM_PATH,args:['--no-sandbox'],headless:true});
try{
 const page=await browser.newPage({viewport:{width:1500,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/*',r=>r.fulfill({status:200,json:{}}));await page.goto('http://foundry.test');await page.setContent(html);
 for(const fx of cases){
  await page.evaluate(f=>{cfg=normalizeCfg(f.cfg);lastRes=f.result;lastErrs=[];refresh=()=>{};scheduleAutosave=()=>{};window._stTab='costs';window.SNAPSHOT=false;const p=cfg.assumptions[f.collection][f.index];window._stSelObj=p.fee_streams[p.fee_streams.length-2];document.getElementById('content').innerHTML=_feeStreamsSectionHtml(f.family,p,'assumptions.'+f.collection+'.'+f.index,f.fi);_calculatedInputs=JSON.stringify(cfg);_calculationState='idle';},fx);
  const link=page.locator('.st-body .product-formula-numbers .result-numbers-link').filter({visible:true});assert.equal(await link.count(),1);
  if(fx.family==='obs'&&fx.ppy===12)await page.screenshot({path:'/tmp/r460-formula-numbers.png',fullPage:true});
  const before=await page.evaluate(()=>JSON.stringify(cfg));
  await link.click();const dialog=page.getByRole('dialog',{name:'Period values'});await dialog.waitFor({state:'visible'});
  const data=await page.evaluate(()=>document.getElementById('result-numbers-dialog')._resultNumbers);
  const streams=fx.cfg.assumptions[fx.collection][fx.index].fee_streams,st=streams[streams.length-2],expected=fx.result.fee_stream_economics.series[st.quantity_series_id].fee_product_cost.map(x=>x/1000);
  assert.deepStrictEqual(data.rows[0].values,expected);assert.equal(data.rows[0].unit,'$000s');assert.equal(data.periodTag,fx.ppy===12?'M':'Q');assert.equal(data.rows[0].name,st.name);
  await page.evaluate(()=>{window._copied=null;Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:async t=>{window._copied=t;}}});});
  const copy=dialog.getByRole('button',{name:'Copy table for Excel',exact:true});await copy.click();assert((await page.evaluate(()=>window._copied)).includes(fx.ppy===12?'M1':'Q1'));
  assert.equal(await page.evaluate(()=>JSON.stringify(cfg)),before,'Numbers is read-only');
  await page.evaluate(()=>{cfg.assumptions.n_periods+=1;updateCalculationStatus();});assert(await copy.isDisabled(),'stale snapshot copy is disabled');
  await dialog.getByRole('button',{name:'Close period values'}).click();
  await page.evaluate(f=>{cfg.assumptions.n_periods-=1;const st=cfg.assumptions[f.collection][f.index].fee_streams.at(-2),rec=lastRes.fee_stream_economics.series[st.quantity_series_id];rec.fee_product_cost=rec.fee_product_cost.map(()=>0);_calculatedInputs=JSON.stringify(cfg);refreshLfxLive();},fx);
  const zero=JSON.parse(await link.getAttribute('data-result-numbers'));assert(zero.rows[0].values.every(x=>x===0),'refresh uses new engine capture, including zeros');
 }
 assert.deepStrictEqual(errors,[]);console.log('PASS formula Numbers: three product families, monthly/quarterly, exact engine expense, units, copy, stale protection, refresh, zero values, unchanged inputs');
}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
