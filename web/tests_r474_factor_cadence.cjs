const {chromium}=require('playwright'),fs=require('fs'),assert=require('assert');
(async()=>{
const html=fs.readFileSync('web/console_v2.html','utf8').replace('renderTabs();\nwhoami().then(u=>{ paintWho(); if(u){ boot(); } else { currentTab = "welcome"; renderContent(); } });','');
const browser=await chromium.launch({executablePath:process.env.FOUNDRY_CHROMIUM_PATH||'/usr/bin/chromium',args:['--no-sandbox'],headless:true});
try{
 const page=await browser.newPage({viewport:{width:1450,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/*',r=>r.fulfill({status:200,json:{}}));await page.goto('http://foundry.test');await page.setContent(html);
 await page.evaluate(()=>{
  cfg={assumptions:{periods_per_year:12,n_periods:60,nie_detail:{categories:[{linked_components:[{driver:'formula_driver',component_id:'f',name:'Scheduled factor',factors:[{kind:'entered',name:'Monthly cost',periodized:true,spec:{trajectory:'flat',value:100,period:'month'}},{kind:'entered',name:'Multiplier',periodized:false,spec:{source:'entered',trajectory:'explicit',cadence:'month',values:Array(60).fill(1),resolution:'step'}}]}]}]}}};
  refresh=()=>{};scheduleAutosave=()=>{};_renderContentBody=()=>{document.getElementById('content').innerHTML=_opexFormulaDriverEditorHtml(0,0,cfg.assumptions.nie_detail.categories[0].linked_components[0]);};renderContent();
 });
 const before=await page.evaluate(()=>JSON.stringify(cfg));await page.evaluate(()=>renderContent());assert.equal(await page.evaluate(()=>JSON.stringify(cfg)),before,'render preserves authored input');
 const cadence=page.getByLabel('Formula factor schedule cadence');assert.equal(await cadence.inputValue(),'month');
 await cadence.selectOption('year');assert.equal(await page.getByLabel('Formula factor schedule resolution').inputValue(),'step');
 const paste=page.locator('#opexFormulaFactor_0_0_1');await paste.fill('1 1.02 1.036324 1.054977832 1.073967432976');await paste.dispatchEvent('input');await page.locator('#opexFormulaFactor_0_0_1_load').click();
 const factor=await page.evaluate(()=>cfg.assumptions.nie_detail.categories[0].linked_components[0].factors[1]);
 assert.equal(factor.spec.cadence,'year');assert.equal(factor.periodized,false);assert.equal(factor.spec.values.length,5);assert.equal(factor.spec.resolution,'step');
 await page.getByLabel('Formula factor schedule resolution').selectOption('smooth');assert.equal(await page.evaluate(()=>cfg.assumptions.nie_detail.categories[0].linked_components[0].factors[1].spec.resolution),'smooth');
 await page.getByLabel('Formula factor schedule resolution').selectOption('step');
 await page.screenshot({path:'/tmp/r474-factor-cadence.png',fullPage:true});
 // Periodized factors keep their natural flow period and get no separate cadence control.
 await page.evaluate(()=>{const f=cfg.assumptions.nie_detail.categories[0].linked_components[0].factors[1];f.periodized=true;f.spec={trajectory:'explicit',period:'year',values:[120,240,360,480,600]};renderContent();});
 assert.equal(await page.getByLabel('Formula factor schedule cadence').count(),0);
 assert((await page.locator('.fx-sub').innerText()).includes('Schedule per year'));
 assert.deepStrictEqual(errors,[]);console.log('PASS r474: cadence selection, paste, persistence, Hold/Interpolate, inert render and natural-period separation');
}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
