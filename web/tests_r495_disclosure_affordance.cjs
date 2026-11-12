// r495: every plain disclosure in the workspace looks openable (bordered control, chevron that turns when open);
// section headers get a chevron box; row names that open an editor read as links. Custom disclosures keep theirs.
const {chromium}=require('playwright'),fs=require('fs'),assert=require('assert'),cp=require('child_process');
(async()=>{
const tax=JSON.parse(cp.execFileSync('python3',['-c','import json;from foundry.v2.tests_tax_blocks import setup;print(json.dumps(setup()))'],{encoding:'utf8'}));
const html=fs.readFileSync('web/console_v2.html','utf8').replace('<head>','<head><script>window.V31=true;window.V3=true;</script>').replace(/renderTabs\(\);\nwhoami\(\)\.then[^\n]+/,'');
const browser=await chromium.launch({executablePath:process.env.FOUNDRY_CHROMIUM_PATH,args:['--no-sandbox','--disable-gpu','--single-process','--no-zygote'],headless:true});
try{const page=await browser.newPage({viewport:{width:1300,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
await page.route('**/*',r=>r.fulfill({json:{}}));await page.goto('http://foundry.test');await page.setContent(html);
await page.evaluate(c=>{cfg=c;refresh=()=>{};document.getElementById('content').innerHTML='<div id="t">'+externalTaxHtml()+
 '<details class="fk-card"><summary>Factor card</summary></details><details class="explicit-preview"><summary>Preview</summary></details>'+
 '<table class="capital-input-table"><tr><td><button class="capital-input-pick">Asset</button></td></tr></table></div>';},tax);
const st=(sel,pseudo)=>page.evaluate(([sel,pseudo])=>{const e=document.querySelector(sel);if(!e)return null;const c=getComputedStyle(e,pseudo||null);return {border:c.borderTopStyle+' '+c.borderTopWidth+' '+c.borderTopColor,bg:c.backgroundColor,content:c.content,w:c.width,transform:c.transform,fw:c.fontWeight,list:c.listStyleType,display:c.display,color:c.color};},[sel,pseudo]);
const notes='#t details.tax-notes>summary';
let s=await st(notes);assert.strictEqual(s.border,'solid 1px rgb(196, 196, 196)','plain disclosure is a bordered control');assert.strictEqual(s.fw,'600');assert.strictEqual(s.color,'rgb(44, 44, 44)');assert.strictEqual(s.display,'inline-flex');
let b=await st(notes,'::before');assert.strictEqual(b.content,'""');assert.strictEqual(b.w,'6px','chevron drawn');
const closedT=b.transform;await page.evaluate(()=>document.querySelector('#t details.tax-notes').open=true);await page.waitForTimeout(250);
assert.notStrictEqual((await st(notes,'::before')).transform,closedT,'chevron turns when open');
assert.strictEqual((await st(notes)).bg,'rgb(245, 236, 221)','open state is tinted');
const sec='#t details.tax-section>summary';b=await st(sec,'::before');assert.strictEqual(b.w,'20px','section header has a chevron box');assert(/url\(/.test((await page.evaluate(s=>getComputedStyle(document.querySelector(s),'::before').backgroundImage,sec))));
assert.strictEqual((await st(sec)).border.split(' ')[0],'none','section header itself is not boxed');
// custom disclosures untouched
assert.strictEqual((await st('#t details.fk-card>summary')).border.split(' ')[0],'none','factor cards keep their own design');
assert.strictEqual((await st('#t details.explicit-preview>summary')).border.split(' ')[0],'none','schedule previews keep their own design');
// row editor names
const pick=await st('#t .capital-input-pick','::after');assert.strictEqual(pick.w,'16px','row editor chevron box');
assert.strictEqual(await page.evaluate(()=>getComputedStyle(document.querySelector('#t .capital-input-pick')).textDecorationLine),'underline');
// keyboard: summaries remain focusable and toggle with Enter
const openN=()=>page.evaluate(()=>document.querySelectorAll('#t details[open]').length);const n0=await openN();
await page.focus('#t details.tax-section:not([open])>summary');await page.keyboard.press('Enter');
assert.strictEqual(await openN(),n0+1,'Enter opens a section');
assert.deepStrictEqual(errors,[]);
console.log('PASS r495 disclosures: bordered chevron controls with open state, section chevron boxes, row-editor links; custom disclosures unchanged; keyboard toggle');
}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
