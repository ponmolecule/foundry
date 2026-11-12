// r490: (1) Securities Target % with a Schedule (or Growth) takes its own full-width row instead of stretching the
// third grid column; Flat stays inline. (2) Changing a schedule's cadence never relabels its values: it converts
// when the resolved path is unchanged, otherwise keeps the old values aside and leaves the new cadence empty and flagged.
const {chromium}=require('playwright'),fs=require('fs'),assert=require('assert'),{execFileSync}=require('child_process');
(async()=>{
const data=JSON.parse(execFileSync('python3',['-c',"import json;from foundry.v2.tests_r412_securities_cash_targets import CashTargets;c=CashTargets().config();c['assumptions']['n_periods']=60;c['assumptions']['periods_per_year']=12;print(json.dumps(c))"],{encoding:'utf8'}));
const html=fs.readFileSync('web/console_v2.html','utf8').replace('<head>','<head><script>window.V31=true;window.V3=true;</script>').replace(/renderTabs\(\);\nwhoami\(\)\.then[^\n]+/,'');
const browser=await chromium.launch({executablePath:process.env.FOUNDRY_CHROMIUM_PATH,args:['--no-sandbox','--disable-gpu','--single-process','--no-zygote'],headless:true});
try{const page=await browser.newPage({viewport:{width:1500,height:1100}}),errors=[];page.setDefaultTimeout(8000);page.on('pageerror',e=>errors.push(e.message));
await page.route('**/*',r=>{const p=new URL(r.request().url()).pathname;if(p==='/web/rates_workspace.js')return r.fulfill({contentType:'text/javascript',body:fs.readFileSync('web/rates_workspace.js','utf8')});if(p==='/web/rates_workspace.css')return r.fulfill({contentType:'text/css',body:fs.readFileSync('web/rates_workspace.css','utf8')});return r.fulfill({json:{}});});
await page.goto('http://foundry.test');await page.setContent(html);
await page.evaluate(c=>{cfg=c;refresh=()=>{};currentTab='config';lastRes=null;lastErrs=[];window._cfgModule='sec';window._cfgSectionOpen={secaoci:true};window._fsxActive='s5';window._fsxOpen={s5:true};document.body.classList.add('insp-closed');renderContent();},data);
const geo=()=>page.evaluate(()=>{const g=document.querySelector('.fsx-target'),t=g.querySelector('.fsx-tgt'),f=[...g.querySelectorAll(':scope>.sec-managed-field')].pop(),sel=t.querySelector('.sec-managed-series-row select'),r=x=>x.getBoundingClientRect();
 return {gw:r(g).width,tw:r(t).width,ttop:r(t).top,fbottom:r(f).bottom,ftop:r(f).top,sel:sel.getBoundingClientRect().width,selFits:sel.scrollWidth<=sel.clientWidth+1};});
// 1. Layout
let g=await geo();
assert(g.tw<g.gw*0.5&&Math.abs(g.ttop-g.ftop)<40,'Flat stays inline beside timing '+JSON.stringify(g));
await page.evaluate(()=>{_managedSecPortfolios()[0].target_ratio_spec={source:'entered',trajectory:'explicit',cadence:'month',values:Array(60).fill(0.3)};renderContent();});
g=await geo();
assert(g.tw>g.gw-4,'Schedule spans the full row '+JSON.stringify(g));assert(g.ttop>=g.fbottom-1,'Schedule sits below timing');assert(g.sel>=100,'trajectory select not truncated');
await page.locator('.fsx-tgt button:has-text("View / edit schedule")').click();
g=await page.evaluate(()=>{const t=document.querySelector('.fsx-tgt'),cad=t.querySelector('select[onchange^="secSeriesCadence"]'),load=[...t.querySelectorAll('button')].find(b=>/Load/.test(b.textContent)),pv=t.querySelector('.explicit-preview');return {cad:cad.getBoundingClientRect().width,cadFits:cad.scrollWidth<=cad.clientWidth+1,loadBottom:load.getBoundingClientRect().bottom,pvTop:pv.getBoundingClientRect().top};});
assert(g.cad>=100,'cadence select readable');assert(g.pvTop>=g.loadBottom-1,'preview below Load / Clear '+JSON.stringify(g));
// 2. Cadence change: constant months collapse to years with an unchanged path.
const spec=()=>page.evaluate(()=>JSON.parse(JSON.stringify(_managedSecPortfolios()[0].target_ratio_spec)));
const note=()=>page.evaluate(()=>(document.querySelector('.fsx-tgt .series-recadence-note')||{}).textContent||'');
await page.locator('.fsx-tgt select[onchange^="secSeriesCadence"]').selectOption('year');
let s=await spec();assert.deepStrictEqual([s.cadence,s.values],['year',[0.3,0.3,0.3,0.3,0.3]]);
assert.strictEqual(await note(),'Converted 60 month values to 5 year values. The path is unchanged.');
assert(!(await page.evaluate(()=>!!document.querySelector('.fsx-tgt .eps-warn'))),'no length warning after conversion');
// Years back to months repeat each value: 60 again.
await page.locator('.fsx-tgt select[onchange^="secSeriesCadence"]').selectOption('month');s=await spec();assert.strictEqual(s.values.length,60);assert(s.values.every(v=>v===0.3));
// Varying months cannot become years: nothing relabelled, nothing zero-filled, old values restorable.
const vary=Array.from({length:60},(_,i)=>+(0.3+0.001*i).toFixed(6));
await page.evaluate(v=>{_managedSecPortfolios()[0].target_ratio_spec={source:'entered',trajectory:'explicit',cadence:'month',values:v};renderContent();},vary);
await page.locator('.fsx-tgt select[onchange^="secSeriesCadence"]').selectOption('year');
s=await spec();assert.deepStrictEqual([s.cadence,s.values],['year',[]],'left empty, not relabelled or zero-filled');
assert.strictEqual(await note(),'The 60 month values change within a year, so they cannot become year values without a rule. Enter year values, or switch back to Month to restore them.');
await page.locator('.fsx-tgt select[onchange^="secSeriesCadence"]').selectOption('month');
s=await spec();assert.deepStrictEqual(s.values,vary,'switching back restores the month values');
// Pure rule checks.
const rule=await page.evaluate(()=>{const run=(sp,v)=>{_seriesRecadence(sp,v);return {c:sp.cadence,n:sp.values.length,v:sp.values.slice(0,3),r:sp.resolution||null};};
 return {
  q2m:run({cadence:'quarter',values:[.1,.2,.3]},'month'),
  y2q:run({cadence:'year',values:[1,2]},'quarter'),
  smooth:run({cadence:'year',resolution:'smooth',values:[1,2,3,4,5]},'month'),
  blank:run({cadence:'month',values:[1,1,null,1,1,1,1,1,1,1,1,1]},'year'),
  partial:run({cadence:'month',values:Array(14).fill(1)},'year'),
  ye:run({cadence:'year',year_end_targets:true,values:[1,2]},'month'),
  empty:run({cadence:'month',values:[]},'year'),
  inert:run({cadence:'month',resolution:'smooth',values:Array(24).fill(2)},'year')};});
assert.deepStrictEqual(rule.q2m,{c:'month',n:9,v:[.1,.1,.1],r:null});
assert.deepStrictEqual(rule.y2q,{c:'quarter',n:8,v:[1,1,1],r:null});
['smooth','blank','partial','ye'].forEach(k=>assert.strictEqual(rule[k].n,0,k+' not converted'));
assert.deepStrictEqual(rule.empty,{c:'year',n:0,v:[],r:null});
assert.deepStrictEqual(rule.inert,{c:'year',n:2,v:[2,2],r:'step'},'an inert smooth flag becomes step so the path is unchanged');
// An empty schedule still seeds as before; a failed conversion does not.
const seed=await page.evaluate(()=>{const a={cadence:'month',values:[]};_seriesRecadence(a,'year');_seedSeriesIfEmpty(a,0);const b={cadence:'month',values:[1,2,3,4,5,6,7,8,9,10,11,12]};_seriesRecadence(b,'year');_seedSeriesIfEmpty(b,0);return [a.values.length,b.values.length];});
assert.deepStrictEqual(seed,[5,0]);
assert.deepStrictEqual(errors,[]);
console.log('PASS r490 target schedule: full-width schedule row, readable selects, preview under actions; cadence change converts exactly or keeps values aside, never relabels or zero-fills');
}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
