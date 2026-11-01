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
for(const [basis,kind] of [['transaction','pct_of_throughput_opex'],['transaction','per_unit'],['account','per_account'],['flat','periodic_amount_opex'],['transaction','pct_of_revenue_opex']]){
 for(const trajectory of ['flat','growth','explicit_schedule']){
  await page.evaluate(([basis,kind,trajectory])=>{const st=cfg.assumptions.obs_exposures[2].fee_streams[0];st.basis=basis;st.cost={kind,params:{pct:.002,cost_per_unit:2,cost_per_account:2,amount:100,period:'month',factor_path:{trajectory,value:.002,period:'year',resolution:'step',growth_spec:{rate:.03},schedule:{1:.002,2:.003}}}};},[basis,kind,trajectory]);
  await open(0,'costs');await settle();
  const labels=await page.locator('.st-sec[data-st="costs"] .fld>label:visible').allTextContents();
  const pathControl=page.locator('.st-sec[data-st="costs"] select[onchange*="_feeCostFactorTrajectory"]');
  assert.strictEqual(await pathControl.count(),1);
  const path=labels.indexOf('Cost path'),resolution=labels.indexOf('Resolution');
  if(path<0){assert.strictEqual(await page.locator('.st-sec[data-st="costs"] .fxs-pathval .fxs-path').count(),1,'path beside value');}
  const value=labels.findIndex(x=>/^(Starting cost|Cost \(|Starting product cost|Product cost \(|Cost rate)/.test(x));
  if(value>=0&&path>=0)assert(path<value,'path before value '+JSON.stringify(labels));
  const growth=labels.findIndex(x=>x.startsWith('Growth (%'));
  if(trajectory==='growth')assert(growth>=0&&resolution>growth,'resolution after growth '+JSON.stringify(labels));
  if(trajectory==='flat')assert(resolution===-1,'no flat resolution');
  if(trajectory==='explicit_schedule'&&resolution>=0)assert(resolution>labels.indexOf('Schedule period'),'resolution after cadence');
 }
}
await page.evaluate(()=>{const st=cfg.assumptions.obs_exposures[2].fee_streams[0];st.cost.kind='pct_of_throughput_opex';st.cost.params.factor_path.trajectory='growth';});await open(0,'costs');await settle();
await page.screenshot({path:'/workspace/scratch/370303911165/r446-cost-order.png',fullPage:true});
assert.deepStrictEqual(errors,[]);console.log('PASS r446 cost field order: five cost types × three paths');
}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
