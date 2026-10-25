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

await page.evaluate(f=>{cfg=f.cfg;lastRes=f.result;lastErrs=null;currentTab='is';refresh=()=>{};scheduleAutosave=()=>{};
 cfg.assumptions.n_periods=14;cfg.assumptions.periods_per_year=12;
 const series=Array.from({length:14},(_,i)=>i+1);for(const k of Object.keys(lastRes.financials.is))if(Array.isArray(lastRes.financials.is[k]))lastRes.financials.is[k]=series.slice();
 Object.assign(lastRes.financials.is,{loanInt:series.slice(),nii:series.slice(),pretax:series.slice(),tax:series.slice(),ni:series.slice(),dtaNet:series.map(x=>10*x),nol:series.map(x=>100-x),currentYearTaxLoss:series.map(x=>2*x),provDayOne:series.slice(),taxCurrent:series.slice()});
 lastRes.faithful={is_totals:{}};lastRes.presentation.derived={totalIntInc:series.slice(),totalIntExp:series.slice(),nie:series.slice()};lastRes.annual=null;lastRes.balance_components={components:[{name:'Component income',income_line:'interest',income:series.slice()}]};
 cfg=normalizeCfg(cfg);renderContent();LC.land('open','View test');window._originalCfg=JSON.stringify(cfg);window._originalRes=JSON.stringify(lastRes);},fixture);
const table=()=>page.locator('#content table.fin').first();
async function row(label){return (await table().locator('tr').filter({has:page.locator('td').filter({hasText:label})}).first().locator('td').allTextContents()).slice(2).map(x=>x.trim()===''?null:Number(x.replaceAll(',','')));}
assert.strictEqual(await table().locator('th').count(),17);assert.deepStrictEqual((await row('Interest Income: Loans')).slice(0,3),[1,2,3]);
await page.getByRole('button',{name:'Quarterly',exact:true}).click();assert.strictEqual(await table().locator('th').count(),8);assert.deepStrictEqual(await row('Interest Income: Loans'),[6,15,24,33,27,105]);assert((await table().locator('th').allTextContents()).includes('Q5 (partial)'));
assert.deepStrictEqual(await row('Memo: deferred tax assets'),[30,60,90,120,140,140]);assert.deepStrictEqual(await row('Memo: current tax-year'),[6,12,18,24,28,28]);
assert.deepStrictEqual(await row('of which: day-one provision'),[6,15,24,33,27,105]);assert.deepStrictEqual(await row('of which: Component income'),[6,15,24,33,27,105]);
await page.getByRole('button',{name:'Annual',exact:true}).click();assert.deepStrictEqual(await row('Interest Income: Loans'),[78,27,105]);assert((await table().locator('th').allTextContents()).includes('Year 2 (partial)'));assert.deepStrictEqual(await row('Memo: prior-year NOL'),[88,86,86]);
assert(await table().locator('td[title]').count()>0);await page.evaluate(()=>{if(JSON.stringify(cfg)!==window._originalCfg||JSON.stringify(lastRes)!==window._originalRes||LC.state()!=='CLEAN')throw Error('View mutated: cfg '+(JSON.stringify(cfg)!==window._originalCfg)+' result '+(JSON.stringify(lastRes)!==window._originalRes)+' state '+LC.state());});
// View uses native cadence when a finer previous choice cannot apply.
await page.evaluate(()=>{window._incomeViewPPY=12;cfg.assumptions.periods_per_year=4;renderContent();});assert.strictEqual(await page.getByRole('button',{name:'Monthly',exact:true}).count(),0);assert.strictEqual(await page.getByRole('button',{name:'Quarterly',exact:true}).getAttribute('aria-pressed'),'true');
await page.getByRole('button',{name:'Annual',exact:true}).click();assert.deepStrictEqual(await row('Interest Income: Loans'),[10,26,42,27,105]);
// Missing observations do not become invented zeroes, opening slots are not summed.
const unit=await page.evaluate(()=>{cfg.assumptions.periods_per_year=12;cfg.assumptions.n_periods=4;window._incomeViewPPY=4;const v=incomeStatementView();return {sum:incomeStatementValues([1000,1,2,3,4],v),missing:incomeStatementValues([1,null,3,4],v),end:incomeStatementValues([10,20,30,40],v,'end')};});assert.deepStrictEqual(unit,{sum:[6,4],missing:[null,4],end:[30,40]});
await page.evaluate(()=>{cfg.assumptions.periods_per_year=12;cfg.assumptions.n_periods=14;window._incomeViewPPY=4;renderContent();});
await page.evaluate(()=>applyInspector(false));await page.screenshot({path:'/tmp/r400-income-desktop.png',fullPage:false});await page.setViewportSize({width:390,height:844});await page.screenshot({path:'/tmp/r400-income-mobile.png',fullPage:false});assert(await page.locator('.is-viewcontrols').isVisible());
assert.deepStrictEqual(errors,[]);console.log('PASS monthly/quarterly/annual totals, partial periods, memo snapshots, component income, flow totals, missing data, opening slots, cadence fallback and no configuration/result mutation');
}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
