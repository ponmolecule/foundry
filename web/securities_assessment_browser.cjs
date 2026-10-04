const {chromium}=require('playwright'),fs=require('fs'),path=require('path'),assert=require('assert'),{execFileSync}=require('child_process');
const repo=path.resolve(__dirname,'..');
(async()=>{
const html=fs.readFileSync(path.join(repo,'web/console_v2.html'),'utf8').replace('renderTabs();\nwhoami().then(u=>{ paintWho(); if(u){ boot(); } else { currentTab = "welcome"; renderContent(); } });','');
const config=JSON.parse(fs.readFileSync(path.join(repo,'foundry/fixtures/universal_template_bank.json'),'utf8'));
const b=await chromium.launch({executablePath:process.env.FOUNDRY_CHROMIUM_PATH,args:['--no-sandbox','--disable-gpu','--single-process','--no-zygote'],headless:true});const p=await b.newPage({viewport:{width:1440,height:1100}}),errors=[];p.on('pageerror',e=>errors.push(e.message));await p.route('**/*',r=>r.fulfill({status:200,body:'{}'}));await p.goto('http://foundry.test');await p.setContent(html);
await p.evaluate(c=>{cfg=c;refresh=()=>{};scheduleAutosave=()=>{};currentTab='config';window._cfgSectionOpen={secaoci:true,nie:true};const mp=cfg.assumptions.managed_securities_portfolios[0];cfg.assumptions.managed_securities_portfolios=[mp];mp.sleeves=[mp.sleeves[0]];delete mp.sleeves[0].risk_weight;delete cfg.assumptions.nie_detail.fdic_bp_ann;delete cfg.assumptions.securities_yield;_renderContentBody=()=>{document.getElementById('content').innerHTML=structuresSectionsHtml();};renderContent();},config);
const table=p.locator('table').filter({has:p.locator('th').getByText('Risk wt',{exact:true})});const rw=p.locator('.sec-managed-field').filter({has:p.locator('label').getByText('Standardized risk weight',{exact:true})}).locator('select');
assert.strictEqual(await table.locator('tbody tr td').nth(2).textContent(),'20%');assert.strictEqual(await rw.inputValue(),'0.2');
await rw.selectOption('0',{force:true});assert.strictEqual(await table.locator('tbody tr td').nth(2).textContent(),'0%');assert.strictEqual(await rw.inputValue(),'0');
await rw.selectOption('0.5',{force:true});assert.strictEqual(await table.locator('tbody tr td').nth(2).textContent(),'50%');
assert.strictEqual(await p.locator('.nie-assess-item').filter({has:p.getByText('FDIC assessment',{exact:true})}).locator('input').inputValue(),'0.0');
assert.strictEqual(await p.locator('.crow').filter({hasText:/^Residual securities yield/}).locator('input').inputValue(),'0.0');
assert.strictEqual(await p.evaluate(()=>TEMPLATE.assumptions.securities_yield),0);
await p.evaluate(()=>{cfg.assumptions.nie_detail.fdic_bp_ann=7;cfg.assumptions.securities_yield=.031;renderContent();});
assert.strictEqual(await p.locator('.nie-assess-item').filter({has:p.getByText('FDIC assessment',{exact:true})}).locator('input').inputValue(),'7.0');assert.strictEqual(await p.locator('.crow').filter({hasText:/^Residual securities yield/}).locator('input').inputValue(),'3.1');assert.deepStrictEqual(errors,[]);
console.log('PASS risk weight missing/0/50 table-editor agreement and immediate updates; zero defaults, explicit saved FDIC/yield preserved');await b.close();
})().catch(e=>{console.error(e);process.exit(1)});
