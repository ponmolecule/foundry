// r481: leaving Detailed Operating Expense warns when other inputs link to its Series, and the run-error banner
// leads with that cause (with Restore Detailed) instead of a list of dangling-link symptoms.
const {chromium}=require('playwright'),fs=require('fs'),assert=require('assert'),{execFileSync}=require('child_process');
// Real engine messages for the same config with Detailed parked, exactly as the console receives them.
const parked=JSON.parse(execFileSync('python3',['-c',`import json,copy
from foundry.v2.validate_q import validate_errors_v2
c=json.load(open('foundry/fixtures/universal_template_bank.json'));a=c['assumptions']
a['_nie_detail_draft']=a['nie_detail'];a['nie_detail']=None;a['_operating_expense_mode']='simple'
print(json.dumps(validate_errors_v2(c)))`],{encoding:'utf8',maxBuffer:1<<26}));
(async()=>{
assert(parked.length>3,'engine rejects the parked config: '+parked.length);
const html=fs.readFileSync('web/console_v2.html','utf8').replace('<script src="/web/rates_workspace.js"></script>','<script>'+fs.readFileSync('web/rates_workspace.js','utf8')+'</script>').replace('<head>','<head><script>window.V3=true;window.V31=true;</script>').replace(/renderTabs\(\);\nwhoami\(\)\.then[^\n]+/,'');
const fx=JSON.parse(fs.readFileSync('foundry/fixtures/universal_template_bank.json','utf8'));
const browser=await chromium.launch({executablePath:process.env.FOUNDRY_CHROMIUM_PATH,args:['--no-sandbox','--disable-gpu','--single-process','--no-zygote'],headless:true});
try{
const page=await browser.newPage({viewport:{width:1440,height:1400}}),errors=[];page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>{errors.push('dialog: '+d.message());d.dismiss();});page.setDefaultTimeout(15000);
await page.route('**/*',r=>r.fulfill({status:200,json:{}}));await page.goto('http://foundry.test');await page.setContent(html);
await page.evaluate(f=>{cfg=normalizeCfg(f);lastRes=null;lastErrs=null;refresh=()=>{};scheduleAutosave=()=>{};renderTabs();setTab('config');renderContent();},fx);
const snap=()=>page.evaluate(()=>({mode:_operatingExpenseMode(cfg.assumptions),nd:!!cfg.assumptions.nie_detail,draft:!!cfg.assumptions._nie_detail_draft,roles:((cfg.assumptions.nie_detail||cfg.assumptions._nie_detail_draft||{}).workforce||{}).roles?.length,cats:((cfg.assumptions.nie_detail||{}).categories||[]).length}));
const start=await snap();assert.strictEqual(start.mode,'detailed');
// 1. Dependents: every input outside Detailed Operating Expense that links to its Series, grouped by area.
const dep=await page.evaluate(()=>_wfDependents());
assert.deepStrictEqual(dep,{count:3,parts:['1 CAC feed','1 cost pool','other liabilities'],text:'1 CAC feed, 1 cost pool, other liabilities'});
// 2. Simple: the guard names what will break; Keep Detailed and Escape change nothing.
await page.evaluate(()=>nieOff());
const g=page.getByRole('alertdialog');assert.strictEqual(await g.count(),1);
const gt=await g.innerText();assert(gt.includes('Switch Operating Expense to Simple?'),gt);assert(gt.includes(dep.count+' inputs link to Operating Expense series')&&gt.includes(dep.text),gt);
await g.getByRole('button',{name:'Keep Detailed'}).click();assert.strictEqual(await g.count(),0);assert.deepStrictEqual(await snap(),start);
await page.evaluate(()=>nieOff());await page.keyboard.press('Escape');assert.strictEqual(await page.getByRole('alertdialog').count(),0);assert.deepStrictEqual(await snap(),start);
// 3. Confirming parks Detailed as a draft.
await page.evaluate(()=>nieOff());await page.getByRole('button',{name:'Switch to Simple'}).click();
let st=await snap();assert.strictEqual(st.mode,'simple');assert.strictEqual(st.nd,false);assert.strictEqual(st.draft,true);
// 4. The banner leads with the cause, counts the dependents and keeps every message behind a disclosure.
await page.evaluate(m=>{lastErrs=m;lastRunFailure=null;refreshConfigPreviews();},parked);
const b=page.locator('#content > .config-run-error');assert.strictEqual(await b.count(),1);
const cause=await b.locator('.cre-cause').innerText();
assert(cause.startsWith('Figures unavailable. Operating Expense is set to Simple, so its workforce and expense-category series are unavailable.'),cause);
assert(cause.includes(dep.count+' inputs link to them ('+dep.text+')'),cause);
assert.strictEqual(await b.locator('.cre-other').count(),0,'every parked-config message is attributed to the cause');
const merged=parked.map(e=>e.message).reduce((a,m)=>{if(a.length&&/^expected exactly one\b/i.test(m))a[a.length-1]+='; '+m;else a.push(m);return a;},[]);
assert.strictEqual(await b.locator('.cre-all summary').innerText(),'All '+merged.length+' messages');
assert(!(await b.locator('.cre-all').evaluate(d=>d.open)),'list collapsed');
assert.deepStrictEqual(await b.locator('.cre-all li').allTextContents(),merged,'split fragments rejoined');
// 5. Restore Detailed brings back the same roles and categories; the banner clears on a clean run.
await b.getByRole('button',{name:'Restore Detailed'}).click();
st=await snap();assert.strictEqual(st.mode,'detailed');assert.strictEqual(st.nd,true);assert.strictEqual(st.draft,false);assert.strictEqual(st.roles,start.roles);assert.strictEqual(st.cats,start.cats);
await page.evaluate(()=>{lastErrs=null;refreshConfigPreviews();});assert.strictEqual(await page.locator('#content > .config-run-error').count(),0);
// 6. Turning the module off from the strip is guarded the same way.
await page.evaluate(()=>opexToggle());assert(/Turn Operating Expense off\?/.test(await page.getByRole('alertdialog').innerText()));
await page.getByRole('button',{name:'Turn off'}).click();st=await snap();assert.strictEqual(st.mode,'off');assert.strictEqual(st.draft,true);
await page.evaluate(m=>{lastErrs=m;refreshConfigPreviews();},parked);
assert(/Operating Expense is turned off/.test(await page.locator('#content > .config-run-error .cre-cause').innerText()));
await page.evaluate(()=>nieOn());
// 7. Unrelated errors keep the plain banner; with no dependents the switch is immediate.
await page.evaluate(()=>{lastErrs=[{message:'Deposit beta must be between 0 and 1'}];refreshConfigPreviews();});
assert.strictEqual(await page.locator('#content > .config-run-error').innerText(),'Figures unavailable — Deposit beta must be between 0 and 1');
await page.evaluate(()=>{lastErrs=null;const A=cfg.assumptions;const strip=o=>{if(!o||typeof o!=='object')return;if(Array.isArray(o)){o.forEach(strip);return;}if(/^(workforce_count|workforce_role_count|workforce_role_expense|operating_expense_category|operating_expense_flow)$/.test(o.kind||''))delete o.series_id;for(const k in o){if(k!=='nie_detail')strip(o[k]);}};strip(A);});
assert.strictEqual(await page.evaluate(()=>_wfDependents().count),0);
await page.evaluate(()=>nieOff());assert.strictEqual(await page.getByRole('alertdialog').count(),0);assert.strictEqual((await snap()).mode,'simple');
assert.deepStrictEqual(errors,[]);
console.log('r481 operating expense guard: 7 checks passed');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exit(1);});
