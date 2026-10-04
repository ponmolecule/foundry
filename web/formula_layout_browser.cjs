const {chromium}=require('playwright'),fs=require('fs'),path=require('path'),assert=require('assert'),{execFileSync}=require('child_process');
const repo=path.resolve(__dirname,'..');
(async()=>{
const html=fs.readFileSync(path.join(repo,'web/console_v2.html'),'utf8').replace('renderTabs();\nwhoami().then(u=>{ paintWho(); if(u){ boot(); } else { currentTab = "welcome"; renderContent(); } });','');
const config=JSON.parse(execFileSync('python3',['-c','import json;from foundry.v2.tests_source_catalog import setup;print(json.dumps(setup()))'],{cwd:repo}));
const browser=await chromium.launch({executablePath:process.env.FOUNDRY_CHROMIUM_PATH,args:['--no-sandbox','--disable-gpu','--single-process','--no-zygote'],headless:true});const page=await browser.newPage({viewport:{width:1920,height:1300}});let errors=[];page.on('pageerror',e=>errors.push(e.message));await page.route('**/*',r=>r.fulfill({status:200,body:'{}',contentType:'application/json'}));await page.goto('http://foundry.test');await page.setContent(html);
await page.evaluate(c=>{cfg=c;currentTab='products';refresh=()=>{};scheduleAutosave=()=>{};cfg.assumptions.nie_detail.categories[0].linked_components=[{driver:'formula_driver',name:'Linked assessment',factors:[{kind:'linked',source:'catalog_quantity',series_id:'deposit_pool.pool.retainedBalance',measure:'period_average',name:'Program deposits'},{kind:'entered',op:'multiply',name:'Rate',display:'percent',spec:{source:'entered',trajectory:'flat',value:.000001}}]}];_renderContentBody=()=>{document.getElementById('content').innerHTML='<div class="cfg-stage cfgwrap" style="width:100%;max-width:none"><div id="layoutHost" style="width:'+(window._layoutWidth||1350)+'px;max-width:100%">'+_opexFormulaDriverEditorHtml(0,0,cfg.assumptions.nie_detail.categories[0].linked_components[0])+'</div></div>'};renderContent();},config);
let cases=0;
for(const width of [1350,1100,1000,900,800,700,600,480,360])for(const growth of [false,true]){
 await page.evaluate(({width,growth})=>{const c=cfg.assumptions.nie_detail.categories[0].linked_components[0];c.factors[1].spec=growth?{source:'entered',trajectory:'growth',base:.000001,growth_spec:{rate:.05,period:'year',method:'step'}}:{source:'entered',trajectory:'flat',value:.000001};window._fxG={'0_0_1':growth};window._layoutWidth=width;renderContent();fitControls();}, {width,growth});
 assert.strictEqual(Math.round(await page.locator('#layoutHost').evaluate(e=>e.getBoundingClientRect().width)),width);
 const problems=await page.evaluate(()=>{
 const issues=[];
 for(const row of document.querySelectorAll('.fx-row')){
 const labels=[...row.children].filter(e=>e.classList.contains('fx-l')||e.classList.contains('fx-lab')||e.classList.contains('fx-gc'));
 for(const e of labels){const r=e.getBoundingClientRect();for(const input of e.querySelectorAll('input,select')){const b=input.getBoundingClientRect();if(b.left<r.left-1||b.right>r.right+1)issues.push('input outside its track');if(input.style.minWidth)issues.push('fitter added min-width');if(input.tagName==='SELECT'&&!input.closest('.fx-span')){const cs=getComputedStyle(input),longest=Math.max(...[...input.options].map(o=>_fitMeasure(input,o.text)));if(longest+parseFloat(cs.paddingLeft)+parseFloat(cs.paddingRight)+2>input.clientWidth+2)issues.push('clipped dropdown '+input.value+': '+input.clientWidth);}}
 const parent=row.getBoundingClientRect();if(r.right>parent.right-34+1)issues.push('field crowds remove button');}
 for(let i=0;i<labels.length;i++)for(let j=i+1;j<labels.length;j++){const a=labels[i].getBoundingClientRect(),b=labels[j].getBoundingClientRect();if(Math.min(a.right,b.right)-Math.max(a.left,b.left)>1&&Math.min(a.bottom,b.bottom)-Math.max(a.top,b.top)>1)issues.push('overlapping fields');}
 }
 return issues;
 });assert.deepStrictEqual(problems,[],`width=${width} growth=${growth}`);cases++;
 await page.locator('.fx-num input').fill('123456789.123');await page.locator('.fx-num input').dispatchEvent('input');assert.strictEqual(await page.locator('.fx-num input').evaluate(e=>e.style.minWidth),'');
}
await page.evaluate(()=>{window._layoutWidth=1100;const c=cfg.assumptions.nie_detail.categories[0].linked_components[0];c.factors[1].spec={source:'entered',trajectory:'flat',value:.000001};renderContent();});if(process.env.FOUNDRY_LAYOUT_SCREENSHOT)await page.screenshot({path:process.env.FOUNDRY_LAYOUT_SCREENSHOT});
assert.deepStrictEqual(errors,[]);console.log(`PASS ${cases} production formula layouts: 360–1350px, flat/growth, no overlap, contained inputs, readable dropdown options, typed-number fitting`);await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
