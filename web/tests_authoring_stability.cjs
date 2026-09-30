const assert=require('node:assert/strict');
const fs=require('node:fs');
const {chromium}=require('playwright');
const html=fs.readFileSync(__dirname+'/console_v2.html','utf8');
const start=html.indexOf('let _renderedAuthoringTab=');
const end=html.indexOf('function _renderContentBody(){',start);
const shared=html.slice(start,end);
const input=html.slice(html.indexOf('function _seriesExplicitValues('),html.indexOf('function _feeParseExplicitValues('));
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.FOUNDRY_CHROMIUM||undefined,args:["--no-sandbox"]});
 try{
 const page=await browser.newPage({viewport:{width:900,height:600}});
 await page.setContent('<style>body{margin:0}textarea{width:400px;height:90px}</style><div id="content"></div>');
 await page.addScriptTag({content:`let currentTab='config',cfg={};let output='Before';let mode='open';
 function esc(x){return String(x)}
 function editor(){return '<div style="height:900px"></div><div data-engine-preview="summary">'+output+'</div><div data-paste-surface="draft"><textarea id="draft" oninput="_seriesExplicitPasteInput(\\'draft\\')"></textarea><button id="draft_load" disabled>Load (replace)</button><button id="clear">Clear</button></div><input data-focus="ordinary" value="12345"><div style="height:1000px"></div>';}
 function _renderContentBody(){document.getElementById('content').innerHTML=editor();document.getElementById('draft_load').onclick=()=>renderContent();document.getElementById('clear').onclick=()=>renderContent();}
 function structuresSectionsHtml(){return editor();}function restoreCardSelects(){}function _decoratePasteSurfaces(){}
 ${input}\n${shared}\nrenderContent();`});
 await page.locator('#draft').fill('100\t200\t300');
 await page.evaluate(()=>{const ta=document.getElementById('draft');ta.setSelectionRange(4,7);window.scrollTo(0,700);window.original=ta;});
 const before=await page.evaluate(()=>({y:scrollY,text:original.value,start:original.selectionStart,end:original.selectionEnd}));
 await page.evaluate(()=>{output='After';refreshConfigPreviews();});
 assert.deepEqual(await page.evaluate(()=>({y:scrollY,text:original.value,start:original.selectionStart,end:original.selectionEnd})),before);
 assert.equal(await page.evaluate(()=>original===document.getElementById('draft')),true);
 assert.equal(await page.locator('[data-engine-preview]').textContent(),'After');
 await page.evaluate(()=>renderContent());
 assert.deepEqual(await page.evaluate(()=>({y:scrollY,text:document.getElementById('draft').value,start:document.getElementById('draft').selectionStart,end:document.getElementById('draft').selectionEnd})),before);
 assert.equal(await page.evaluate(()=>document.activeElement.id),'draft');
 assert.equal(await page.locator('#draft_load').isEnabled(),true);
 await page.locator('#draft_load').click();
 assert.equal(await page.locator('#draft').inputValue(),'');
 assert.equal(await page.locator('#draft_load').isEnabled(),false);
 await page.locator('#draft').fill('10\t20');await page.locator('#clear').click();
 assert.equal(await page.locator('#draft').inputValue(),'');
 await page.locator('#draft').fill('40\t50');
 await page.evaluate(()=>{cfg={};renderContent();});
 assert.equal(await page.locator('#draft').inputValue(),'');
 await page.locator('[data-focus]').focus();
 await page.evaluate(()=>{document.activeElement.setSelectionRange(2,3);renderContent();});
 assert.deepEqual(await page.evaluate(()=>[document.activeElement.selectionStart,document.activeElement.selectionEnd]),[2,3]);
 console.log('Browser checks passed: mounted preview, draft, caret, focus, scroll, Load/Clear, engagement isolation.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
