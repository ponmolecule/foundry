const {chromium}=require('playwright'),fs=require('fs'),assert=require('assert');
(async()=>{
 const html=fs.readFileSync('web/console_v2.html','utf8').replace(/renderTabs\(\);\nwhoami\(\)\.then[^\n]+/,'');
 const fixture=JSON.parse(require('child_process').execFileSync('python3',['-c',`
import json
from foundry.v2.tests_opex_extensions import base_cfg
from foundry.v2.run_q import run_v2
c=base_cfg();c['assumptions']['capital_raises']=[]
c['assumptions']['nie_detail']['categories']=[{'name':'Insurance','flow_spec':{'trajectory':'flat','value':350000,'period':'year'},'settlement':{'mode':'annual','first_payment_period':1}}]
r=run_v2(c)
assert r['financials']['bs']['prepaidOpex'][1] == 320.83
assert r['financials']['bs']['prepaidOpex'][12] == 0
print(json.dumps({'cfg':c,'result':r}))
`],{encoding:'utf8'}));
 const browser=await chromium.launch({executablePath:process.env.FOUNDRY_CHROMIUM_PATH,args:['--no-sandbox','--disable-gpu','--single-process','--no-zygote'],headless:true});
 try{
 const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));await page.route('**/*',r=>r.fulfill({status:200,json:{}}));await page.goto('http://foundry.test');await page.setContent(html);
 await page.evaluate(f=>{cfg=f.cfg;lastRes=f.result;currentTab='bs';renderContent();},fixture);
 const row=page.locator('tr').filter({has:page.locator('td').filter({hasText:/^Prepaid Operating Expenses$/})});assert.strictEqual(await row.count(),1);assert((await row.innerText()).includes('321'));
 await page.screenshot({path:'/tmp/r375-prepaid.png',fullPage:true});
 await page.evaluate(()=>{lastRes.financials.bs.prepaidOpex.fill(0);renderContent();});assert.strictEqual(await row.count(),0);
 await page.evaluate(()=>{delete lastRes.financials.bs.prepaidOpex;renderContent();});assert.strictEqual(await row.count(),0);assert.deepStrictEqual(errors,[]);
 console.log('PASS engine-produced prepaid row, $000s formatting, hidden zero/absent series, no browser errors');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
