// r394: Reference. Search with synonyms and a best answer, subjects, A–Z, coverage, full control entries,
// contextual help beside documented controls, and opening a control on its screen. Read-only throughout.
const {chromium}=require('playwright'),fs=require('fs'),assert=require('assert'),{execFileSync}=require('child_process');
(async()=>{
const fixture=JSON.parse(execFileSync('python3',['-c',`import json
from foundry.v2.tests_r376_deferred import config
from foundry.v2.run_q import run_v2
c=config();print(json.dumps({'cfg':c,'result':run_v2(c)}))`],{encoding:'utf8'}));
const html=fs.readFileSync('web/console_v2.html','utf8').replace('<script src="/web/rates_workspace.js"></script>','<script>'+fs.readFileSync('web/rates_workspace.js','utf8')+'</script>').replace('<head>','<head><script>window.V3=true;window.V31=true;</script>').replace(/renderTabs\(\);\nwhoami\(\)\.then[^\n]+/,'');
const browser=await chromium.launch({executablePath:process.env.FOUNDRY_CHROMIUM_PATH,args:['--no-sandbox','--disable-gpu','--single-process','--no-zygote'],headless:true});
try{
const page=await browser.newPage({viewport:{width:1600,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));page.setDefaultTimeout(10000);
await page.route('**/*',r=>r.fulfill({status:200,json:{}}));await page.goto('http://foundry.test');await page.setContent(html);
await page.evaluate(f=>{cfg=f.cfg;lastRes=f.result;refresh=()=>{};scheduleAutosave=()=>{};window._base=JSON.stringify(cfg);setTab('index');},fixture);
// 1. Placement, views, catalog.
assert.deepStrictEqual(await page.evaluate(()=>TAB_DEFS.find(x=>x[0]==='index')),['index','Reference']);
assert.deepStrictEqual(await page.locator('.ref-views button').allTextContents(),['Search','Subjects','A–Z','Coverage']);
const n=await page.evaluate(()=>({full:REF_ENTRIES.length,opts:REF_ENTRIES.reduce((s,e)=>s+e.options.length,0),topics:FOUNDRY_INDEX.entries.length}));
assert(n.full>=50&&n.opts>=150,'full entries '+JSON.stringify(n));assert.strictEqual(n.topics,102,'topic explanations are kept');
// 2. Every full entry and every option renders; every topic renders.
await page.evaluate(()=>{for(const e of REF_ENTRIES){for(let i=0;i<e.options.length;i++){refOpen(e.id,i);const t=document.getElementById('ref-title');if(!t||t.textContent!==e.title)throw Error('entry '+e.id);if(!document.querySelector('.ref-o.on .ref-ob'))throw Error('option '+e.id+' '+i);}}
  for(const e of FOUNDRY_INDEX.entries){refOpen(e.id);if(document.getElementById('ref-title')?.textContent!==e.title)throw Error('topic '+e.id);}});
// 3. Search: synonyms read the query, a best answer leads, controls before topics.
const search=async q=>{await page.locator('#ref-q').fill(q);await page.locator('#ref-q').press('Enter');};
await search('balance authoring');
assert.strictEqual(await page.locator('.ref-it').first().locator('.tag').textContent(),'CONTROL');
assert(/Balance authoring/.test(await page.locator('.ref-best h3').innerText()));
assert(/Balance authoring · lending/.test(await page.locator('#ref-title').innerText()));
await search('CAC method');assert(/Acquisition channel method/.test(await page.locator('.ref-interp .syn').first().innerText()),'synonym read as');
assert(/Acquisition channel method/.test(await page.locator('#ref-title').innerText()));
await search('<img src=x onerror=alert(1)>');assert(await page.getByText('No matching controls or topics.').isVisible());assert.strictEqual(await page.locator('.ref-shell img').count(),0);
// 4. Subjects list the subject's controls, then its topics.
await page.evaluate(()=>refSubject('customers'));
const cacN=await page.evaluate(()=>REF_ENTRIES.filter(e=>e.subject==='Customer acquisition').length);
assert.strictEqual(await page.locator('.ref-list .ref-it .tag',{hasText:'CONTROL'}).count(),cacN);
// 5. Options expand one at a time and carry inputs, illustration and switch effects where the entry has them.
await page.evaluate(()=>refOpen('cac-channel-method',1));assert.strictEqual(await page.locator('.ref-o.on').count(),1);
assert(/Spend ÷ CAC/.test(await page.locator('.ref-o.on .ref-oh').innerText()));assert(await page.locator('.ref-o.on .ref-ill').isVisible());
await page.locator('.ref-oh').nth(2).click();assert(/FTEs × productivity/.test(await page.locator('.ref-o.on .ref-oh').innerText()));
// 6. A–Z and coverage.
await page.locator('.ref-views button',{hasText:'A–Z'}).click();assert(await page.getByRole('navigation',{name:'Alphabetical letters'}).isVisible());
await page.locator('.ref-letters button',{hasText:/^S$/}).click();const azFirst=await page.locator('.ref-azl button').first();assert(await azFirst.isVisible());await azFirst.click();assert(await page.locator('#ref-title').isVisible());
await page.locator('.ref-views button',{hasText:'Coverage'}).click();
assert.strictEqual(await page.locator('.ref-bar').count(),await page.evaluate(()=>REF_COVERAGE.areas.length));assert(await page.evaluate(()=>REF_COVERAGE.total>100));
// 7. Containment.
await page.locator('.ref-views button',{hasText:'Search'}).click();await page.evaluate(()=>refOpen('loan-balance-authoring',3));
for(const width of [1440,1024,768,390]){await page.setViewportSize({width,height:1000});for(const v of ['search','az','coverage']){await page.evaluate(v=>{window._ref.view=v;refRender();if(v==='search')refOpen('loan-balance-authoring',3);},v);
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),width+' '+v+' no page scroll');}}
await page.setViewportSize({width:1600,height:1000});
// 8. Read-only.
assert.strictEqual(await page.evaluate(()=>JSON.stringify(cfg)),await page.evaluate(()=>window._base),'Reference never changes the model');
// 9. Open in Foundry goes to the control's screen.
await page.evaluate(()=>refOpen('cac-attrition-path'));await page.locator('.ref-th .ref-btn.dk').click();
assert.strictEqual(await page.evaluate(()=>currentTab),'config');assert.strictEqual(await page.evaluate(()=>window._cfgModule),'cac');
// 10. Contextual help beside a documented control shows the current option, then opens the full entry.
await page.evaluate(()=>{window._cfgSectionOpen={customeracq:true};cacnSelect(0);cacnSettings();});
const q=page.locator('#card-cac .cac-within .ref-q').first();assert(await q.isVisible(),'help beside Path');
assert.strictEqual(await page.evaluate(()=>[...document.querySelectorAll('#card-cac .cac-within .l')].map(x=>x.textContent)[0]),'Path','label text is unchanged');
await q.click();assert(/Monthly flows/.test(await page.locator('.ref-pop>b').innerText()),'popover names the current option');
await page.keyboard.press('Escape');assert.strictEqual(await page.locator('.ref-pop').count(),0,'Escape closes help');
await q.click();await page.locator('.ref-pop .f button').click();
assert.strictEqual(await page.evaluate(()=>currentTab),'index');assert(/Attrition path/i.test(await page.locator('#ref-title').innerText()));
assert.deepStrictEqual(errors,[]);
console.log('PASS r394 Reference: placement, '+n.full+' full entries ('+n.opts+' options) and 102 topics render, synonym search with best answer, subjects, A–Z, coverage, containment 1440/1024/768/390, read-only, open in Foundry, contextual help');
}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
