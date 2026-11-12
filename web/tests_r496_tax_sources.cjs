// r496: tax sources render as aligned rows (name, kind, value, identifier); an open source puts name, units, source,
// measure and identifier on one line above the value editor. No nested "Source identifier" disclosure.
const {chromium}=require('playwright'),fs=require('fs'),assert=require('assert'),cp=require('child_process');
(async()=>{
const tax=JSON.parse(cp.execFileSync('python3',['-c','import json;from foundry.v2.tests_tax_blocks import setup;print(json.dumps(setup()))'],{encoding:'utf8'}));
tax.assumptions.external_tax.inputs.push({id:'flag',name:'Tax-year start flag',unit:'scalar',source:'entered',amount_spec:{source:'entered',trajectory:'explicit',cadence:'month',values:Array.from({length:12},(_,i)=>i===0?1:0)}});
const html=fs.readFileSync('web/console_v2.html','utf8').replace('<head>','<head><script>window.V31=true;window.V3=true;</script>').replace(/renderTabs\(\);\nwhoami\(\)\.then[^\n]+/,'');
const browser=await chromium.launch({executablePath:process.env.FOUNDRY_CHROMIUM_PATH,args:['--no-sandbox','--disable-gpu','--single-process','--no-zygote'],headless:true});
try{const page=await browser.newPage({viewport:{width:1300,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
await page.route('**/*',r=>r.fulfill({json:{}}));await page.goto('http://foundry.test');await page.setContent(html);
await page.evaluate(c=>{cfg=c;refresh=()=>{};window._taxSourcesExpanded=true;window._taxSourceOpen={initial:true};document.getElementById('content').innerHTML='<div id="t" style="max-width:1100px">'+externalTaxHtml()+'</div>';},tax);
const rows=await page.evaluate(()=>[...document.querySelectorAll('#t details.tax-source>summary')].map(s=>({name:s.querySelector('.tax-source-name').textContent,kind:s.querySelector('.tax-source-kind').textContent,val:s.querySelector('.tax-source-val').textContent,id:s.querySelector('.tax-source-id').textContent,x:[...s.children].map(c=>Math.round(c.getBoundingClientRect().left))})));
const by=Object.fromEntries(rows.map(r=>[r.id,r]));
assert.deepStrictEqual([by.income.kind,by.income.val],['Period amount','1 $000s']);
assert.deepStrictEqual([by.initial.kind,by.initial.val],['Balance','1.6 $000s']);
assert.deepStrictEqual([by.retained.kind,by.retained.val],['Rate / factor','0.25']);
assert.deepStrictEqual([by.flag.kind,by.flag.val],['Rate / factor','Schedule · 12 month values']);
assert(rows.every(r=>JSON.stringify(r.x.slice(1,3))===JSON.stringify(rows[0].x.slice(1,3))),'name and kind columns align across rows '+JSON.stringify(rows.map(r=>r.x)));
const open=await page.evaluate(()=>{const d=document.querySelector('#t details.tax-source[open]'),g=d.querySelector('.tax-source-grid'),f=[...g.querySelectorAll(':scope>.et-field')];
 return {labels:f.map(x=>x.querySelector('span').textContent),tops:f.map(x=>Math.round(x.getBoundingClientRect().top)),nested:d.querySelectorAll('details').length,idText:d.textContent.includes('Source identifier'),foot:d.querySelector('.tax-source-foot').textContent,value:!!d.querySelector('.tax-source-value'),remove:!!d.querySelector('button.tax-source-remove')};});
assert.deepStrictEqual(open.labels,['Name','Units','Source','Measure','Identifier']);
assert(new Set(open.tops).size===1,'settings on one line '+open.tops);
assert.strictEqual(open.idText,false,'no nested Source identifier disclosure');
assert(open.foot.includes('Rules and blocks refer to this source as initial.'));assert(open.value&&open.remove);
// edits still write through: identifier, measure, name
await page.fill('#t details.tax-source[open] input[aria-label="Tax source name"]','Opening federal NOL');await page.dispatchEvent('#t details.tax-source[open] input[aria-label="Tax source name"]','change');
assert.strictEqual(await page.evaluate(()=>cfg.assumptions.external_tax.inputs.find(x=>x.id==='initial').name),'Opening federal NOL');
// a scalar source drops Measure but keeps the identifier in the same row
await page.evaluate(()=>{window._taxSourceOpen={retained:true};document.getElementById('content').innerHTML='<div id="t" style="max-width:1100px">'+externalTaxHtml()+'</div>';});
const sc=await page.evaluate(()=>[...document.querySelector('#t details.tax-source[open] .tax-source-grid').querySelectorAll(':scope>.et-field>span')].map(x=>x.textContent));
assert.deepStrictEqual(sc,['Name','Units','Source','Identifier']);
assert.deepStrictEqual(errors,[]);
console.log('PASS r496 tax sources: aligned rows with kind, value and identifier; one-line settings above the value editor; no nested identifier disclosure; edits write through');
}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
