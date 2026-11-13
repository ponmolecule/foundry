// r505: one page pattern for every Configuration module, and a Stress Testing rail in the shared side-menu style.
// Every module: band with the rail name and purpose, status line, at most four key figures, a numbered section menu
// with one section open (or the module's own restyled menu), one footer. Rendering leaves the configuration alone,
// sections switch what is shown, and controls inside a section still write their fields.
const {chromium}=require('playwright'),fs=require('fs'),assert=require('assert'),{execFileSync}=require('child_process');
(async()=>{
const fx=JSON.parse(execFileSync('python3',['-c',`import json
from foundry.v2.run_q import run_v2
c=json.load(open('foundry/fixtures/universal_template_bank.json'))
print(json.dumps({'cfg':c,'result':run_v2(c)}))`],{encoding:'utf8',maxBuffer:1<<28}));
const html=fs.readFileSync('web/console_v2.html','utf8').replace('<link rel="stylesheet" href="/web/rates_workspace.css">','<style>'+fs.readFileSync('web/rates_workspace.css','utf8')+'</style>').replace('<script src="/web/rates_workspace.js"></script>','<script>'+fs.readFileSync('web/rates_workspace.js','utf8')+'</script>').replace('<head>','<head><script>window.V3=true;window.V31=true;</script>').replace(/renderTabs\(\);\nwhoami\(\)\.then[^\n]+/,'');
const browser=await chromium.launch({executablePath:process.env.FOUNDRY_CHROMIUM_PATH,args:['--no-sandbox','--disable-gpu','--single-process','--no-zygote'],headless:true});
try{
const page=await browser.newPage({viewport:{width:1500,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>d.dismiss());page.setDefaultTimeout(15000);
await page.route('**/*',r=>r.fulfill({status:200,json:{}}));await page.goto('http://foundry.test');await page.setContent(html);
await page.evaluate(f=>{cfg=normalizeCfg(f.cfg);lastRes=f.result;refresh=()=>{};scheduleAutosave=()=>{};document.body.classList.add('insp-closed');renderTabs();setTab('config');},fx);
const settle=()=>page.waitForTimeout(120);
const mod=async m=>{await page.evaluate(m=>cfgSelectModule(m),m);await settle();};
const NAMES={rates:'Rates & Curves',cap:'Capital & pre-opening',sec:'Securities & AOCI',income:'Other income',nie:'Operating expense',cac:'Customer acquisition',tax:'Tax detail',cecl:'Credit regime'};
const MENU={rates:5,cap:4,income:1,nie:3,cecl:1};
for(const m of Object.keys(NAMES))await mod(m);
const c0=await page.evaluate(()=>JSON.stringify(cfg));
for(const m of Object.keys(NAMES)){await mod(m);
  const f=await page.evaluate(m=>{const c=document.getElementById('card-'+m),v=e=>!!e&&e.offsetParent!==null;const head=c.querySelector(':scope>.cardhead');
    return {title:(c.querySelector(':scope>.cardhead .cfgx-bt .ct')||{}).textContent,purpose:!!(c.querySelector(':scope>.cardhead .cfgx-bt .cd')||{}).textContent,headH:head?Math.round(head.getBoundingClientRect().height):0,
      status:v(c.querySelector(':scope>.cfgx-status')),tiles:c.querySelectorAll(':scope>.cfgx-tiles .cfgx-tile, :scope>.cfgx-tiles .cfg-kpi').length,
      native:c.classList.contains('cfgx-native'),menu:c.querySelectorAll(':scope>.cfgx-menu .cfgx-si').length,on:c.querySelectorAll(':scope>.cfgx-menu .cfgx-si.on').length,
      sh:v(c.querySelector('.cfgx-sh')),foot:v(c.querySelector(':scope>.cfgx-foot')),collapse:c.querySelectorAll(':scope>.cardhead .nie-section-toggle').length};},m);
  assert.strictEqual(f.title,NAMES[m],m+' band names the module as the rail does');
  assert(f.purpose&&f.status&&f.foot&&f.collapse===0,m+' purpose, status line, footer, no header collapse '+JSON.stringify(f));
  assert(f.headH>=70&&f.headH<=110,m+' header band height '+f.headH);
  if(m!=='cac')assert(f.tiles>=1&&f.tiles<=4,m+' one to four key figures '+f.tiles);
  if(MENU[m]){assert.strictEqual(f.menu,MENU[m],m+' section menu items');assert(f.on===1&&f.sh,m+' one section open with its header');}
  if(m==='tax')assert(f.menu>=1&&f.on===1,'tax sections');
  if(m==='sec'||m==='cac')assert(f.native,m+' keeps its own menu, restyled');
}
const heights=new Set();for(const m of Object.keys(NAMES)){await mod(m);heights.add(await page.evaluate(m=>Math.round(document.querySelector('#card-'+m+'>.cardhead').getBoundingClientRect().height),m));}
assert(heights.size<=2,'header bands share one height '+[...heights]);
for(const m of Object.keys(NAMES))await mod(m);
assert.strictEqual(await page.evaluate(()=>JSON.stringify(cfg)),c0,'rendering and framing leave the configuration alone');
assert.strictEqual(await page.evaluate(()=>document.querySelectorAll('.cfg-subnav').length),0,'no section list under the rail row');
// Capital: one section at a time; controls inside still write their fields
await mod('cap');
const shown=()=>page.evaluate(()=>({raise:document.querySelector('#card-cap .fxs-cap-raise').offsetParent!==null,fa:document.querySelector('#fixedassets-editor').offsetParent!==null,pre:document.querySelector('#preopening-editor').offsetParent!==null}));
await page.evaluate(()=>cfgxSection('cap','raises'));await settle();
assert.deepStrictEqual(await shown(),{raise:true,fa:false,pre:false},'raises open alone');
await page.locator('#card-cap .cfgx-si',{hasText:'Fixed assets'}).click();await settle();
assert.deepStrictEqual(await shown(),{raise:false,fa:true,pre:false},'menu opens fixed assets');
assert.strictEqual(await page.evaluate(()=>document.querySelector('#card-cap .cfgx-sh h2').textContent),'Fixed assets / CAPEX','section header follows the menu');
await page.evaluate(()=>cfgxSection('cap','raises'));await settle();
const amt=page.locator('#card-cap .crow.fxs-cap-raise input').first();await amt.fill('12,345');await amt.press('Tab');await settle();
assert.strictEqual(await page.evaluate(()=>cfg.assumptions.capital_raises[0].amount),12345000,'raise amount still writes its field');
// Rates: index sections switch the authored index
await mod('rates');await page.locator('#card-rates .cfgx-si',{hasText:'SOFR'}).click();await settle();
assert.strictEqual(await page.evaluate(()=>rwsIndex),'sofr','SOFR section authors SOFR');
assert(await page.evaluate(()=>document.querySelector('#card-rates .cfgx-sh h2').textContent==='SOFR'&&document.querySelectorAll('#card-rates .rws-panel:not(.cfgx-off)').length===1),'one rates panel shown, headed SOFR');
await page.locator('#card-rates .cfgx-si',{hasText:'Effective index paths'}).click();await settle();
assert.strictEqual(await page.evaluate(()=>document.querySelector('#card-rates .cfgx-si.on b').textContent),'Effective index paths');
// Operating expense: menu replaces the tab strip and drives the same tabs
await mod('nie');await page.locator('#card-nie .cfgx-si',{hasText:'Expense categories'}).click();await settle();
assert.strictEqual(await page.evaluate(()=>document.getElementById('card-nie').getAttribute('data-nie-tab')),'categories','menu drives the tab');
assert.strictEqual(await page.evaluate(()=>document.querySelectorAll('#card-nie .cfg-subtabs').length),0,'tab strip replaced by the menu');
assert(await page.evaluate(()=>!!document.querySelector('#card-nie .cfgx-status .nie-mode')),'Simple/Detailed in the status line');
// Section choice persists across a re-render
await page.evaluate(()=>renderContent());await settle();
assert.strictEqual(await page.evaluate(()=>document.querySelector('#card-nie .cfgx-si.on b').textContent),'Expense categories','section kept across render');
// Stress Testing rail: shared side-menu look
await page.evaluate(()=>setTab('stress'));await settle();
const r=await page.evaluate(()=>{const on=document.querySelector('.st-rail .st-ri.on'),mi=on&&on.querySelector('.mi'),cs=x=>getComputedStyle(x);
  return {head:(document.querySelector('.st-rail .st-rhead')||{}).textContent,card:!!document.querySelector('.st-rail .st-rcard'),icons:document.querySelectorAll('.st-rail .st-ri .mi').length,items:document.querySelectorAll('.st-rail .st-ri').length,
    selBg:cs(on).backgroundColor,miBg:cs(mi).backgroundColor,bar:getComputedStyle(on,'::before').backgroundColor};});
assert(r.head==='Stress Testing'&&r.card&&r.icons===r.items&&r.items>=6,'rail heading, card and icon squares '+JSON.stringify(r));
assert(r.selBg==='rgb(245, 236, 221)'&&r.miBg==='rgb(44, 44, 44)'&&r.bar==='rgb(223, 179, 103)','selected item like the Configuration rail '+JSON.stringify(r));
assert.deepStrictEqual(errors,[]);
console.log('PASS r505 configuration pattern: band, status, figures, numbered menu with one section open, footer on all eight modules; config untouched; sections switch and controls still write; Stress Testing rail matches');
}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
