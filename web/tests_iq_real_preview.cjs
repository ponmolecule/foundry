const fs=require('fs'),{execFileSync}=require('child_process'),path=require('path'),assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{
const output=process.env.FOUNDRY_SCREENSHOT_DIR||require('os').tmpdir();fs.mkdirSync(output,{recursive:true});
const browser=await chromium.launch({executablePath:process.env.FOUNDRY_CHROMIUM||undefined,headless:true,args:['--no-sandbox','--disable-dev-shm-usage','--disable-gpu']});
const page=await browser.newPage({viewport:{width:1600,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
let html=fs.readFileSync(__dirname+'/console_v2.html','utf8').replace(/renderTabs\(\);\s*whoami\(\)\.then\([\s\S]*?<\/script>/,'renderTabs();</script>');html=html.replace('</head>','<script>window.V31=true;window.BUILD="r201IQ";</script></head>');
await page.route('**/*',r=>r.request().url()==='http://foundry.test/'?r.fulfill({contentType:'text/html',body:html}):r.abort());await page.goto('http://foundry.test/');
const payload=JSON.parse(execFileSync(process.env.PYTHON||'python3',['-c',`import json
from foundry.v2.tests_population_expense_observables import fixture
from foundry.v2.run_q import run_v2
c=fixture();w=c['assumptions']['nie_detail']['workforce'];w['roles'][0]['count']=1
w['roles'][1]['compensation_spec']={'source':'entered','trajectory':'explicit','period':'month','cadence':'month','amount_basis':'total','values':[37500]*36,'extend':'hold'}
w['roles'][2]={'series_id':'platform','role':'Platform team','count':140,'hire_period':13,'annual_comp':500000,'compensation_basis':'total','compensation_period':'month'}
w['roles']=[w['roles'][2],w['roles'][0],w['roles'][1]]
c['proposed_bank']='Example Bank';c['scenario_name']='Base'
print(json.dumps({'config':c,'results':run_v2(c)}))`],{encoding:'utf8'}));const {config,results}=payload;
await page.evaluate(({config,results})=>{cfg=config;lastRes=results;refresh=()=>{};renderGlobals();syncBankLabel();currentTab='config';renderTabs();renderContent();_iqSelectSection('card-nie');_iqSelectItem('iq-items-workforce',1);},{config,results});
assert.equal(await page.locator('[data-iq-metric=workforce]').innerText(),'325');assert.equal(await page.locator('#iq-items-workforce [data-iq-item]:visible [data-iq-population-expense]').innerText(),'287.5');
assert.match(await page.locator('#iq-items-workforce [data-iq-item]:visible .iq-schedule-preview').innerText(),/M36/);
await page.screenshot({path:path.join(output,'r201IQ-workforce.png'),fullPage:true});
await page.evaluate(()=>{cfg.assumptions.nie_detail.categories=[{series_id:'technology',name:'Technology',flow_spec:{trajectory:'explicit',period:'month',values:[100000,110000,120000],extend:'hold'}}];renderContent();_iqSelectSection('card-nie');document.querySelector('.iq-expense-tabs button:nth-child(2)').click();nieCatAddFormulaDriver(0);nieCatAddPiecewise(0);});
await page.screenshot({path:path.join(output,'r201IQ-expenses.png'),fullPage:true});
for(const width of [1600,1280,1024,768]){
await page.setViewportSize({width,height:1000});await page.locator('#iq-items-expenses details').evaluateAll(ds=>ds.forEach(d=>d.open=true));assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'expanded expense overflow '+width);
}
await page.setViewportSize({width:1600,height:1000});await page.screenshot({path:path.join(output,'r201IQ-advanced-expenses.png'),fullPage:true});
await page.evaluate(()=>{cfg.assumptions.cac_feeds={growth:{beginning_customers:1200,beginning_auc:0,attrition_rate:0,channels:[{name:'Customer funnel',method:'spend_cac',params:{spend:100000,cac:1000,avg_auc_per_customer:0}}]}};_cfgSectionOpen.customeracq=true;renderContent();_iqSelectSection('card-cac');});await page.screenshot({path:path.join(output,'r201IQ-acquisition.png'),fullPage:true});for(const key of await page.evaluate(()=>TAB_DEFS.map(x=>x[0]))){
 await page.evaluate(k=>{currentTab=k;renderTabs();renderContent();},key);
 assert.deepEqual(await page.locator('#tabs > .tab').allTextContents(),await page.evaluate(()=>TAB_DEFS.map(x=>x[1])));
 const blueSurfaces=await page.locator('body *').evaluateAll(es=>es.filter(e=>{const r=e.getBoundingClientRect();if(r.width<150||r.height<30||!r.width||!r.height)return false;const c=getComputedStyle(e).backgroundColor.match(/[\d.]+/g)||[];return c.length>=3&&(c.length<4||Number(c[3])>.7)&&Number(c[2])>Number(c[0])+12&&Number(c[2])>=Number(c[1])-2;}).map(e=>e.tagName+'.'+e.className));
 assert.deepEqual(blueSurfaces,[],'blue surfaces in '+key);
 if(['welcome','products','bs','is','overview'].includes(key))await page.screenshot({path:path.join(output,'r201IQ-'+key+'.png'),fullPage:true});
}
assert.deepEqual(errors,[]);console.log('PASS real engine preview: M1 325, selected expense 287.5; M36 schedule endpoint; expanded expense settings at 4 widths; no JS errors.');await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
