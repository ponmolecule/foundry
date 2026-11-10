// r475: schedule previews (compact strip and expanded grid) keep every number on one line, size columns to the
// longest full-precision value, drop inner strip cells on narrow containers, and copy values at full precision.
const {chromium}=require('playwright'),fs=require('fs'),assert=require('assert');
(async()=>{
const html=fs.readFileSync('web/console_v2.html','utf8').replace('<script src="/web/rates_workspace.js"></script>','<script>'+fs.readFileSync('web/rates_workspace.js','utf8')+'</script>').replace('<head>','<head><script>window.V3=true;window.V31=true;</script>').replace(/renderTabs\(\);\nwhoami\(\)\.then[^\n]+/,'');
const fx=JSON.parse(fs.readFileSync('foundry/fixtures/universal_template_bank.json','utf8'));
const browser=await chromium.launch({executablePath:process.env.FOUNDRY_CHROMIUM_PATH,args:['--no-sandbox','--disable-gpu','--single-process','--no-zygote'],headless:true});
try{
const ctx=await browser.newContext({viewport:{width:1440,height:3600}});await ctx.grantPermissions(['clipboard-read','clipboard-write'],{origin:'http://foundry.test'});
const page=await ctx.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>d.dismiss());page.setDefaultTimeout(15000);
await page.route('**/*',r=>r.fulfill({status:200,json:{}}));await page.goto('http://foundry.test');await page.setContent(html);
const VALS=[];{let x=547174.65167;for(let t=0;t<60;t++){VALS.push(Math.round(x*1e5)/1e5*1000);x=x*(t<2?1.49:1.021)+[0.12345,0.98761,0.5][t%3];}}
// In situ: Interest-bearing balances, term source entered as a 60-month schedule.
const load=(w,cad)=>page.evaluate(([f,vals,cad])=>{cfg=normalizeCfg(f);cfg.assumptions.n_periods=60;lastRes=null;lastErrs=[];refresh=()=>{};scheduleAutosave=()=>{};window._cfgModule='sec';window._fsxOpen={s2:true};renderTabs();setTab('config');
 bcAdd();const m=cfg.assumptions.balance_components_model,i=m.components.length-1,c=m.components[i];c.treatment='earning_asset';
 c.terms[0].source_spec={source:'entered',trajectory:'explicit',cadence:cad,values:cad==='quarter'?vals.slice(0,20):vals,extend:'hold',resolution:'step'};
 window._faSeriesExplicitOpen['assumptions.balance_components_model.components.'+i+'.terms.0.source_spec']=true;renderContent();fsxGo('s2');
 document.querySelectorAll('.bc-editor details.fk-card').forEach(d=>d.open=true);const d=[...document.querySelectorAll('.bc-editor .fk-drawer details.explicit-preview')].find(e=>e.offsetParent);d.open=true;},[fx,VALS,cad]);
const metrics=()=>page.evaluate(()=>{const d=[...document.querySelectorAll('.bc-editor .fk-drawer')].find(e=>e.offsetParent),p=d.querySelector('details.explicit-preview');
 const line=e=>{const r=e.getBoundingClientRect(),lh=parseFloat(getComputedStyle(e).lineHeight)||16;return {w:r.width,h:r.height,lh,sw:e.scrollWidth,cw:e.clientWidth};};
 const vis=e=>getComputedStyle(e).display!=='none';
 return {drawer:d.getBoundingClientRect().width,
  strip:[...p.querySelectorAll('.eps-c:not(.eps-gap)')].filter(vis).map(c=>({cls:c.className,title:c.title,b:line(c.querySelector('b')),cell:line(c),text:c.querySelector('b').textContent})),
  grid:[...p.querySelectorAll('.explicit-preview-value')].map(line),
  values:[...p.querySelectorAll('.explicit-preview-value')].map(e=>e.textContent),
  copy:p.querySelector('.eps-copy').getAttribute('data-copy'),
  chip:(d.closest('.fk-r,.fk-term-b')||document).querySelector('.fk-spark em')?.textContent||[...document.querySelectorAll('.bc-editor .fk-spark em')].find(e=>e.offsetParent)?.textContent};});
await load(1440,'month');let m=await metrics();
// 1. Expanded grid: full precision, one line per value, no clipping.
assert.strictEqual(m.values[0],'547,174.65167');
assert.strictEqual(m.values.length,60);
m.grid.forEach((g,i)=>{assert(g.h<g.lh*1.6,'value '+i+' wraps: '+JSON.stringify(g));assert(g.sw<=g.cw+1,'value '+i+' clipped');});
// 2. Compact strip: no overlap or clipping; display-rounded with the full value on hover.
assert(m.strip.length>=4,'wide drawer shows at least first two and last two: '+m.strip.length);
m.strip.forEach(c=>{assert(c.b.sw<=c.b.cw+1&&c.b.h<c.b.lh*1.6,'strip cell squeezed: '+c.text);});
assert.strictEqual(m.strip[0].text,'547,174.65');assert.strictEqual(m.strip[0].title,'M1: 547,174.65167');
assert(/^60 mo · 547,174\.65 → /.test(m.chip),m.chip);
// 3. Copy: full precision, one value per line, no separators; the button writes the clipboard.
assert.strictEqual(m.copy.split('\n').length,60);assert.strictEqual(m.copy.split('\n')[0],'547174.65167');
assert.strictEqual(m.copy.split('\n')[2],m.values[2].replace(/,/g,''));
// The test origin is not a secure context, so the console takes its execCommand fallback; capture what it copies.
await page.evaluate(()=>{window.__copied=null;document.execCommand=c=>{if(c==='copy')window.__copied=document.activeElement&&document.activeElement.value;return true;};});
const btn=page.locator('.bc-editor .fk-drawer .eps-copy').first();await btn.click();
assert.strictEqual(await page.evaluate(()=>window.__copied),m.copy);
assert.strictEqual(await btn.textContent(),'Copied');
// 4. Responsive: a narrow page puts the drawer under the label and drops inner strip cells.
await page.setViewportSize({width:900,height:3600});await load(900,'month');m=await metrics();
assert(m.drawer>300,'drawer is full width on narrow pages: '+m.drawer);
assert.deepStrictEqual(m.strip.map(c=>c.cls.trim()).sort(),['eps-c eps-h1','eps-c eps-t1'].sort());
m.grid.forEach((g,i)=>assert(g.h<g.lh*1.6&&g.sw<=g.cw+1,'narrow value '+i+' wraps'));
// 5. Container widths drive the strip: 6 cells wide, 4 cells medium, 2 cells narrow.
const counts=await page.evaluate(vals=>{const out=[];for(const w of [700,480,320]){const host=document.createElement('div');host.style.cssText='width:'+w+'px;display:flex';host.className='cfgwrap';host.innerHTML=_explicitPreviewHtml(vals.map(v=>v/1000),v=>fmtComma(v),'month');document.body.appendChild(host);
 out.push([...host.querySelectorAll('.eps-c:not(.eps-gap)')].filter(e=>getComputedStyle(e).display!=='none').length);host.remove();}return out;},VALS);
assert.deepStrictEqual(counts,[6,4,2],'strip cells by width');
// 6. Quarterly schedules behave the same.
await page.setViewportSize({width:1440,height:3600});await load(1440,'quarter');m=await metrics();
assert.strictEqual(m.values.length,20);m.grid.forEach((g,i)=>assert(g.h<g.lh*1.6&&g.sw<=g.cw+1,'quarter value '+i+' wraps'));
assert.deepStrictEqual(errors,[]);
console.log('r475 schedule preview: 6 checks passed');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exit(1);});
