// r507: entry-tab layout. Stress Testing has no page-wide band: a full-height rail with its heading, and a black band for the
// open view in the content column. Product content starts 32px after the rail and fills the width. Every Configuration section
// menu, Securities & AOCI included, sits in Product's menu card; a selected Workforce role still opens its detail on the right.
const {chromium}=require('playwright'),fs=require('fs'),assert=require('assert'),{execFileSync}=require('child_process');
(async()=>{
const fx=JSON.parse(execFileSync('python3',['-c',`import json
from foundry.v2.run_q import run_v2
c=json.load(open('foundry/fixtures/universal_template_bank.json'))
print(json.dumps({'cfg':c,'result':run_v2(c)}))`],{encoding:'utf8',maxBuffer:1<<28}));
const html=fs.readFileSync('web/console_v2.html','utf8').replace('<link rel="stylesheet" href="/web/rates_workspace.css">','<style>'+fs.readFileSync('web/rates_workspace.css','utf8')+'</style>').replace('<script src="/web/rates_workspace.js"></script>','<script>'+fs.readFileSync('web/rates_workspace.js','utf8')+'</script>').replace('<head>','<head><script>window.V3=true;window.V31=true;</script>').replace(/renderTabs\(\);\nwhoami\(\)\.then[^\n]+/,'');
const browser=await chromium.launch({executablePath:process.env.FOUNDRY_CHROMIUM_PATH,args:['--no-sandbox','--disable-gpu','--single-process','--no-zygote'],headless:true});
try{
const page=await browser.newPage({viewport:{width:1600,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>d.dismiss());page.setDefaultTimeout(15000);
await page.route('**/*',r=>r.fulfill({status:200,json:{}}));await page.goto('http://foundry.test');await page.setContent(html);
await page.evaluate(f=>{cfg=normalizeCfg(f.cfg);lastRes=f.result;refresh=()=>{};scheduleAutosave=()=>{};document.body.classList.add('insp-closed');renderTabs();setTab('config');},fx);
for(const W of [1600,2200]){await page.setViewportSize({width:W,height:1000});
const settle=()=>page.waitForTimeout(150);
// Stress Testing
await page.evaluate(()=>{setTab('stress');stView('scenarios');});await settle();
const st=await page.evaluate(()=>{const R=e=>e.getBoundingClientRect(),rail=document.querySelector('.st-rail'),band=document.querySelector('.st-vband'),cr=document.querySelector('.st-stage>.pg-crumb');
  return {wide:document.querySelectorAll('#content .st-band, #content>.pg-band').length,head:(rail.querySelector('.st-rhead')||{}).textContent,railL:Math.round(R(rail).left),railH:Math.round(R(rail).height),railR:Math.round(R(rail).right),
    bandL:Math.round(R(band).left),title:band.querySelector('h1').textContent,acts:band.querySelectorAll('.st-vact button').length,inStage:!!band.closest('.st-stage'),crumb:cr&&cr.textContent,bg:getComputedStyle(band).backgroundColor,vh:document.querySelectorAll('.st-vh').length};});
assert.strictEqual(st.wide,0,'no page-wide band on Stress Testing');
assert(st.head==='Stress Testing'&&st.railL===0&&st.railH>=800,'full-height rail with its heading '+JSON.stringify(st));
assert(st.inStage&&st.title==='Scenarios'&&st.acts===2&&st.bandL-st.railR===32&&st.vh===0,'view band beside the rail with the view actions '+JSON.stringify(st));
assert(st.bg==='rgb(44, 44, 44)'&&/Stress Testing.*Scenarios/.test(st.crumb),'black band and breadcrumb '+JSON.stringify(st));
await page.evaluate(()=>stView('results'));await settle();
assert.strictEqual(await page.evaluate(()=>document.querySelector('.st-vband h1').textContent),'Results','band follows the view');
// Product
await page.evaluate(()=>{setTab('products');prdSelect('lending',0);});await settle();
const pr=await page.evaluate(()=>{const nav=document.querySelector('.prd-nav').getBoundingClientRect(),c=document.querySelector('.prd-stage .lfx'),r=c.getBoundingClientRect();return {gap:Math.round(r.left-nav.right),right:Math.round(innerWidth-r.right),w:Math.round(r.width)};});
assert(pr.gap>=31&&pr.gap<=33,W+' product content 32px after the rail '+JSON.stringify(pr));
assert(pr.w>=Math.min(1880,W-300-64-6)-2,W+' product content fills the width '+JSON.stringify(pr));
// Configuration: Product's menu card on every numbered-menu module
await page.evaluate(()=>setTab('config'));await settle();
for(const m of ['rates','cap','income','nie','tax','cecl']){await page.evaluate(m=>cfgSelectModule(m),m);await settle();
  const c=await page.evaluate(m=>{const card=document.getElementById('card-'+m),on=card.querySelector('.cfgx-menu .cfgx-si.on'),b=getComputedStyle(card,'::before'),a=getComputedStyle(card,'::after'),o=getComputedStyle(on);
    return {card:b.backgroundColor,col:a.backgroundColor,edge:o.borderLeftColor,sel:o.backgroundColor};},m);
  assert(c.card==='rgb(255, 255, 255)'&&c.col==='rgb(250, 250, 248)'&&c.edge==='rgb(201, 160, 78)'&&c.sel==='rgb(44, 44, 44)',m+' Product menu card '+JSON.stringify(c));}
// the section sits inside the card, beside the menu
await page.evaluate(()=>cfgSelectModule('nie'));await settle();
const box=await page.evaluate(()=>{const card=document.getElementById('card-nie'),menu=card.querySelector('.cfgx-menu').getBoundingClientRect(),sh=card.querySelector('.cfgx-sh').getBoundingClientRect();return {gap:Math.round(sh.left-menu.right),top:Math.round(sh.top-menu.top)};});
assert(box.gap===24&&box.top>=0&&box.top<=40,'section header inside the card beside the menu '+JSON.stringify(box));
// Workforce: selecting a role keeps its detail; on a wide screen it sits to the right of the table
await page.evaluate(()=>wfSelect(1));await settle();
const wf=await page.evaluate(()=>{const l=document.querySelector('#card-nie .cfg-md-list'),d=document.querySelector('#card-nie .cfg-md-detail');return {has:!!d&&d.offsetParent!==null,right:!!(l&&d)&&d.getBoundingClientRect().left>=l.getBoundingClientRect().right-1};});
assert(wf.has,'role detail shown');if(W>=2200)assert(wf.right,'role detail to the right of the table on a wide screen');
// Securities & AOCI: same card, a second line under each menu item
await page.evaluate(()=>cfgSelectModule('sec'));await settle();
const sc=await page.evaluate(()=>{const f=document.querySelector('#card-sec .fsx-focused'),its=[...f.querySelectorAll('.fsx-rail .fsx-it')],on=f.querySelector('.fsx-it.on'),cs=getComputedStyle(f);
  return {bg:cs.backgroundColor,border:cs.borderTopColor,n:its.length,subs:its.map(a=>(a.querySelector('small')||{}).textContent||''),edge:getComputedStyle(on).borderLeftColor};});
assert(sc.bg==='rgb(255, 255, 255)'&&sc.border==='rgb(227, 225, 220)'&&sc.edge==='rgb(201, 160, 78)','Securities in the Product menu card '+JSON.stringify(sc));
assert(sc.n===6&&sc.subs.every(Boolean)&&!sc.subs.some(x=>/undefined|NaN/.test(x)),'every Securities item has a second line '+JSON.stringify(sc.subs));
assert(sc.subs[0].startsWith('Hold in cash'),'funding line reads the policy '+sc.subs[0]);
// the line follows an edit
const fl=page.locator('#fsx-s1 .crow input').first();const v0=await fl.inputValue();
await page.evaluate(()=>{const i=document.querySelector('#fsx-s1 .crow input');i.value='7.5';i.dispatchEvent(new Event('change',{bubbles:true}));});await page.waitForTimeout(80);
await page.evaluate(v=>{const i=document.querySelector('#fsx-s1 .crow input');i.value=v;i.dispatchEvent(new Event('change',{bubbles:true}));},v0);
}
assert.deepStrictEqual(errors,[]);
console.log('PASS r507 entry-tab layout: Stress Testing rail and view band without a page-wide band, Product 32px from the rail and full width, Product menu card on every Configuration module with Workforce role detail kept, Securities menu lines');
}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
