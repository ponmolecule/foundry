const {chromium}=require('playwright'),fs=require('fs'),assert=require('assert'),{execFileSync,spawnSync}=require('child_process');
(async()=>{
 const c=JSON.parse(execFileSync('python3',['-c',`import json
from foundry.v2.tests_rates_workspace import config,workspace
c=config();c['assumptions']['n_periods']=60
w=workspace(c);w['indices']['effr']={'source':'schedule','schedule':{'points':[{'date':str(2028+i)+'-01-01','rate':v/100} for i,v in enumerate([3.9,3.6,3.3,3.3,3.3])],'label':'Model Fed Funds assumptions','units':'percent','input_cadence':'annual','interpolation':'step','extension':'hold'}}
c['assumptions']['deposit_products'][0].update(rate_type='float',index='effr',index_spread=0,deposit_beta=.5)
print(json.dumps(c))`],{encoding:'utf8'}));
 const html=fs.readFileSync('web/console_v2.html','utf8').replace(/renderTabs\(\);\nwhoami\(\)\.then[^\n]+/,'').replace('<script src="/web/rates_workspace.js"></script>','<script>'+fs.readFileSync('web/rates_workspace.js','utf8')+'</script>').replace('<link rel="stylesheet" href="/web/rates_workspace.css">','<style>'+fs.readFileSync('web/rates_workspace.css','utf8')+'</style>');
 const browser=await chromium.launch({executablePath:process.env.FOUNDRY_CHROMIUM_PATH,args:['--no-sandbox','--disable-gpu','--single-process','--no-zygote'],headless:true});
 try{
 const page=await browser.newPage({viewport:{width:1440,height:1100}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/*',r=>{if(r.request().url().endsWith('/api/v31/rates/preview')){const p=spawnSync('python3',['-c','import json,sys;from foundry.v2.rates_workspace import preview;print(json.dumps(preview(json.load(sys.stdin)["config"])))'],{input:r.request().postData(),encoding:'utf8'});return r.fulfill({status:p.status===0?200:422,body:p.status===0?p.stdout:JSON.stringify({detail:p.stderr}),contentType:'application/json'});}return r.fulfill({json:{}});});
 await page.goto('http://foundry.test');await page.setContent(html);
 await page.evaluate(c=>{cfg=c;window.rateSaves=0;window.rateRuns=0;scheduleAutosave=()=>window.rateSaves++;refresh=()=>window.rateRuns++;renderGlobals=()=>{};document.getElementById('content').innerHTML='<div id="rwsWorkspace"></div>';rwsRender();window.savedConfig=JSON.stringify(cfg);},c);
 const root=page.locator('#rwsWorkspace'),status=root.locator('[data-rws-state]'),panel=root.locator('[data-rws-panel="schedule:effr"]'),apply=root.locator('[data-rws-apply]');
 assert((await status.innerText()).includes('Applied — no pending'));assert.strictEqual(await root.locator('textarea').count(),0);assert(!(await panel.evaluate(e=>e.open)));assert(await apply.isDisabled());
 await panel.locator('summary').click();assert.deepStrictEqual(await panel.locator('tbody tr td:nth-child(2)').allTextContents(),['3.9%','3.6%','3.3%','3.3%','3.3%']);
 await root.locator('[data-rws-preview]').click();await page.waitForFunction(()=>rwsResult&&!rwsBusy);assert(await apply.isDisabled());
 assert.deepStrictEqual(await page.evaluate(()=>[0,12,24].map(i=>rwsResult.native[i].effr)),[.039,3.6/100,3.3/100]);
 assert.strictEqual(await page.evaluate(()=>JSON.stringify(cfg)),await page.evaluate(()=>window.savedConfig));
 // Reloading the serialized engagement resets view caches without changing the applied data.
 await page.evaluate(()=>{cfg=JSON.parse(JSON.stringify(cfg));document.getElementById('rwsWorkspace').innerHTML='';rwsRender();});assert((await status.innerText()).includes('Applied — no pending'));assert(!(await panel.evaluate(e=>e.open)));assert.strictEqual(await root.locator('textarea').count(),0);assert(await apply.isDisabled());
 await panel.locator('summary').click();await panel.getByRole('button',{name:'Edit / replace schedule',exact:true}).click();
 assert.strictEqual(await root.locator('#rwsStart').inputValue(),'2028-01-01');assert((await root.locator('#rwsPaste').inputValue()).includes('2029-01-01\t3.6'));
 await root.locator('#rwsPaste').fill('3.85\t3.6\t3.3\t3.3\t3.3');assert((await status.innerText()).includes('not loaded'));assert(await apply.isDisabled());assert(await root.locator('[data-rws-preview]').isDisabled());
 await root.getByRole('button',{name:'SOFR',exact:true}).click();await root.getByRole('button',{name:'EFFR',exact:true}).click();assert.strictEqual(await root.locator('#rwsPaste').inputValue(),'3.85\t3.6\t3.3\t3.3\t3.3');assert((await status.innerText()).includes('not loaded'));assert.strictEqual(await page.evaluate(()=>JSON.stringify(cfg)),await page.evaluate(()=>window.savedConfig));
 await root.getByRole('button',{name:'Load (replace) & preview',exact:true}).click();await page.waitForFunction(()=>rwsResult&&!rwsBusy);assert((await status.innerText()).includes('not applied'));assert(await apply.isEnabled());assert.strictEqual(await root.locator('textarea').count(),0);assert(!(await panel.evaluate(e=>e.open)));
 await apply.click();assert((await status.innerText()).includes('Applied — no pending'));assert(await apply.isDisabled());assert(!(await panel.evaluate(e=>e.open)));assert.strictEqual(await page.evaluate(()=>window.rateSaves),1);await page.evaluate(()=>rwsApply());assert.strictEqual(await page.evaluate(()=>window.rateSaves),1);
 const applied=await page.evaluate(()=>JSON.stringify(cfg));const result=JSON.parse(execFileSync('python3',['-c','import json,sys;from foundry.v2.engine_q_a import run_pf_a;c=json.load(sys.stdin);p=next(x for x in run_pf_a(c)["products"] if x["family"]=="deposit");print(json.dumps([p["rateQ"][i] for i in [0,12,24]]))'],{input:applied,encoding:'utf8'}));assert.deepStrictEqual(result,[1.925,1.8000000000000003,1.6500000000000001]);
 // Stable formatting must not round-trip into a different stored percentage.
 assert(await page.evaluate(()=>[.039,3.6/100,3.3/100,.0123456789012345,-.0000000123456789].every(r=>Number(rwsRateText(r,'percent'))/100===r)));
 await page.evaluate(()=>rwsSource('effr','derived'));assert((await status.innerText()).includes('not applied'));await root.locator('[data-rws-discard]').click();assert((await status.innerText()).includes('Applied — no pending'));assert.strictEqual(await page.evaluate(()=>JSON.stringify(cfg)),applied);
 // Editing a paste while a preview is pending invalidates the response and Apply permission.
 await page.evaluate(async()=>{const originalFetch=fetch;let release;fetch=()=>new Promise(r=>release=r);const pending=rwsPreview();rwsEdit('effr');document.getElementById('rwsPaste').value='3.7';rwsEditorInput('effr');release({ok:true,json:async()=>({monthly:[],native:[]})});await pending;fetch=originalFetch;});
 assert((await status.innerText()).includes('not loaded'));assert(await apply.isDisabled());assert.strictEqual(await page.evaluate(()=>JSON.stringify(cfg)),applied);await root.getByRole('button',{name:'Cancel edit',exact:true}).click();
 for(const width of [1440,1024,768]){await page.setViewportSize({width,height:1100});for(const e of await root.locator('input,select,textarea,button').all()){const b=await e.boundingBox();if(b)assert(b.x>=0&&b.x+b.width<=width+1,'rate control overflow at '+width);}}
 await page.setViewportSize({width:1440,height:1100});await root.screenshot({path:'/tmp/r382-rates-applied.png'});
 await page.evaluate(()=>{cfg=JSON.parse(JSON.stringify(cfg));delete cfg.assumptions.rates_workspace;rwsRender();});assert((await status.innerText()).includes('Saved curves active'));assert.strictEqual(await root.locator('textarea').count(),0);assert(await apply.isDisabled());
 assert.deepStrictEqual(errors,[]);console.log('PASS applied/read-only state, clean percentages, real backend preview, navigation and JSON reload, unloaded buffers, stale response rejection, engagement isolation, Apply guard, discard, downstream deposit yields, and 1440/1024/768 containment');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
