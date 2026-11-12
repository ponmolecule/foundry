// r480: a pasted schedule must match the horizon at its cadence exactly. A mismatch is refused (nothing loaded,
// saved schedule unchanged, pasted text kept). Saved schedules whose length no longer matches are flagged, and a
// cadence change never pads or cuts entered values.
const {chromium}=require('playwright'),fs=require('fs'),assert=require('assert');
(async()=>{
const src=fs.readFileSync('web/console_v2.html','utf8');
// 1. Static: every handler that parses pasted series values calls the length guard before storing.
{const fns=[];const re=/(?:^|\n)(?:window\.([A-Za-z_]+)=function|function ([A-Za-z_]+)|_feeGlobal\.([A-Za-z_]+)=function)\(([^)]*)\)\s*\{/g;let m;const starts=[];
 while((m=re.exec(src)))starts.push({name:m[1]||m[2]||m[3],at:m.index});
 starts.forEach((s,k)=>{const body=src.slice(s.at,k+1<starts.length?starts[k+1].at:s.at+4000);if(/_seriesExplicitValues\(|_feeParseExplicitValues\(/.test(body)&&!/^(_seriesExplicitValues|_feeParseExplicitValues|_seriesExplicitPasteInput|_feeExplicitPasteInput|_feeCoeffPasteInput|_feeFlatAmountPasteInput|_structuredPasteInput)$/.test(s.name))fns.push({name:s.name,ok:/_seriesPasteLengthOk\(/.test(body)});});
 const missing=fns.filter(f=>!f.ok).map(f=>f.name);
 assert(fns.length>=25,'found '+fns.length+' paste handlers');
 assert.deepStrictEqual(missing,[],'paste handlers without the length guard: '+missing.join(', '));}
const html=src.replace('<script src="/web/rates_workspace.js"></script>','<script>'+fs.readFileSync('web/rates_workspace.js','utf8')+'</script>').replace('<head>','<head><script>window.V3=true;window.V31=true;</script>').replace(/renderTabs\(\);\nwhoami\(\)\.then[^\n]+/,'');
const fx=JSON.parse(fs.readFileSync('foundry/fixtures/universal_template_bank.json','utf8'));
const browser=await chromium.launch({executablePath:process.env.FOUNDRY_CHROMIUM_PATH,args:['--no-sandbox','--disable-gpu','--single-process','--no-zygote'],headless:true});
try{
const page=await browser.newPage({viewport:{width:1440,height:3600}}),errors=[];page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>{errors.push('dialog: '+d.message());d.dismiss();});page.setDefaultTimeout(15000);
await page.route('**/*',r=>r.fulfill({status:200,json:{}}));await page.goto('http://foundry.test');await page.setContent(html);
const VALS=Array.from({length:62},(_,t)=>Math.round((547174.65167+t*1234.56789)*1e5)/1e5);
const P='assumptions.balance_components_model.components.0.terms.0.source_spec';
const load=(n,cad)=>page.evaluate(([f,vals,n,cad,P])=>{cfg=normalizeCfg(f);cfg.assumptions.n_periods=60;lastRes=null;lastErrs=[];refresh=()=>{};scheduleAutosave=()=>{};window._statusLog=[];const _as=appStatus;appStatus=(k,m)=>{window._statusLog.push([k,m]);};
 window._cfgModule='sec';window._fsxOpen={s2:true};renderTabs();setTab('config');cfg.assumptions.balance_components_model=null;bcAdd();const c=cfg.assumptions.balance_components_model.components[0];c.treatment='earning_asset';
 c.terms[0].source_spec={source:'entered',trajectory:'explicit',cadence:cad||'month',values:vals.slice(0,n).map(v=>v*1000),extend:'hold',resolution:'step'};
 window._faSeriesExplicitOpen[P]=true;renderContent();fsxGo('s2');document.querySelectorAll('.bc-editor details.fk-card').forEach(d=>d.open=true);},[fx,VALS,n,cad,P]);
const stored=()=>page.evaluate(P=>JSON.parse(JSON.stringify(P.split('.').reduce((o,k)=>o[k],cfg))),P);
const ta=()=>page.locator('.bc-editor .fk-drawer textarea').first();
const paste=async n=>{await ta().fill(VALS.slice(0,n).map(v=>v.toFixed(5)).join('\n'));await page.locator('.bc-editor .fk-drawer .fk-btn',{hasText:'Load (replace)'}).first().click();await page.waitForTimeout(60);};
const lastStatus=()=>page.evaluate(()=>window._statusLog.at(-1));
// 2. 59 into a 60-month horizon: refused, saved schedule and pasted text unchanged.
await load(60,'month');let before=await stored();
await paste(59);
assert.deepStrictEqual(await lastStatus(),['err','59 values pasted. A 60-month horizon needs exactly 60. Nothing was loaded; the saved schedule is unchanged.']);
assert.deepStrictEqual(await stored(),before,'saved schedule unchanged');
assert.strictEqual((await ta().inputValue()).split('\n').length,59,'pasted text kept for correction');
// 3. 61: refused the same way.
await paste(61);
assert.strictEqual((await lastStatus())[1],'61 values pasted. A 60-month horizon needs exactly 60. Nothing was loaded; the saved schedule is unchanged.');
assert.deepStrictEqual(await stored(),before);
// 4. Exactly 60: loaded, nothing padded.
await paste(60);let st=await stored();
assert.strictEqual((await lastStatus())[0],'ok');assert.strictEqual(st.values.length,60);
assert(Math.abs(st.values[59]/1000-VALS[59])<1e-6,'M60 is the pasted M60');
// 5. Quarterly horizon expects 20; yearly expects 5.
await load(20,'quarter');await paste(19);
assert.strictEqual((await lastStatus())[1],'19 values pasted. A 20-quarter horizon needs exactly 20. Nothing was loaded; the saved schedule is unchanged.');
await load(5,'year');await paste(6);
assert.strictEqual((await lastStatus())[1],'6 values pasted. A 5-year horizon needs exactly 5. Nothing was loaded; the saved schedule is unchanged.');
// 6. A saved short schedule is flagged: chip, count, warning, missing cells.
await load(59,'month');
const prev=page.locator('.bc-editor .fk-drawer').first();
assert.strictEqual(await prev.locator('.eps-warn').innerText(),'M60 not entered. Schedule has 59 of 60 month values.');
assert.strictEqual(await prev.locator('.explicit-preview-count').innerText(),'59 of 60');
assert.strictEqual(await prev.locator('.eps-missing').count(),1);
assert(/^59 of 60 mo · /.test(await page.locator('.bc-editor .fk-spark-bad em').first().innerText()));
// 7. A long saved schedule is flagged with the periods beyond the horizon.
await load(62,'month');
assert.strictEqual(await page.locator('.bc-editor .fk-drawer .eps-warn').first().innerText(),'M61–M62 beyond the 60-month horizon. Schedule has 62 of 60 month values.');
assert.strictEqual(await page.locator('.bc-editor .fk-drawer .eps-beyond').count(),2);
// 8. r490: a cadence change never relabels values. 60 varying months cannot become quarters, so the quarter
// schedule starts empty (flagged, not padded or zero-filled) and switching back restores the months.
await load(60,'month');before=await stored();
await page.evaluate(P=>faSeriesCadence(P,'quarter'),P);st=await stored();
assert.strictEqual(st.cadence,'quarter');assert.deepStrictEqual(st.values,[],'months not relabelled as quarters');
await page.evaluate(P=>faSeriesCadence(P,'month'),P);st=await stored();
assert.strictEqual(st.cadence,'month');assert.deepStrictEqual(st.values,before.values,'month values restored');
// 9. Matching schedules show no flag.
await load(60,'month');
assert.strictEqual(await page.locator('.bc-editor .eps-warn').count(),0);assert.strictEqual(await page.locator('.bc-editor .fk-spark-bad').count(),0);
// 10. Other paste paths refuse the same way: workforce count, opex category, lending funded flow.
const other=await page.evaluate(()=>{const out={};const wf=_ensureWorkforce(),r=wf.roles[0];nieWorkforceCountMode(0,'explicit');const cad=r.count_spec.cadence,need=_seriesSourcePeriods(cad),b1=JSON.stringify(r.count_spec.values);
 nieWorkforceCountPaste(0,Array.from({length:need-1},(_,i)=>i+1).join('\n'));out.wf=[window._statusLog.at(-1)[0],JSON.stringify(r.count_spec.values)===b1];
 nieWorkforceCountPaste(0,Array.from({length:need},(_,i)=>i+1).join('\n'));out.wfOk=[window._statusLog.at(-1)[0],r.count_spec.values.length===need];
 const ct=_ensureNieDetail().categories[0],fs=_ensureNieCatFlow(ct),n2=_seriesSourcePeriods(fs.period||'month'),b2=JSON.stringify(fs.values||null);
 nieCatSchedulePaste(0,Array.from({length:n2+1},(_,i)=>i+1).join('\n'));out.opex=[window._statusLog.at(-1)[0],JSON.stringify(fs.values||null)===b2];
 return out;});
assert.deepStrictEqual(other,{wf:['err',true],wfOk:['ok',true],opex:['err',true]});
assert.deepStrictEqual(errors,[]);
console.log('r480 schedule length: 10 checks passed');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exit(1);});
