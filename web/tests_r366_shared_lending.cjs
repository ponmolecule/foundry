const fs=require('fs'),vm=require('vm'),assert=require('assert'),H=fs.readFileSync(__dirname+'/console_v2.html','utf8');
for(const m of H.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script>/gi))if(!/\bsrc=/.test(m[1]))new vm.Script(m[2]);
let seq=0;const ctx={cfg:{assumptions:{lending_products:[{name:'Generic',balance_driver:{average_balance_per_customer_spec:{source:'entered',trajectory:'flat',value:17}}}]}},window:{},renderContent(){},refresh(){},esc:s=>String(s),_seriesId:()=>`stable-${++seq}`,lastRes:null,PPY:()=>12,_nativeFlowPeriod:()=> 'month',_numInput:v=>String(v),fmtComma:v=>String(v),fmtField(){},_seriesSourcePeriods:()=>60,_seriesPasteSummary:()=>'',_seriesResolutionUseful:()=>false,_seriesCadenceOptions:()=>['month','quarter','year'],_explicitPreviewHtml:()=>'',_pf:x=>+String(x).replace(/,/g,''),setPath(path,v){const parts=path.split('.');let o=ctx.cfg;for(const p of parts.slice(0,-1))o=o[p];o[parts.at(-1)]=v;},getPath(path){return path.split('.').reduce((o,p)=>o[p],ctx.cfg)}};
vm.createContext(ctx);vm.runInContext(H.slice(H.indexOf('// Reusable shared assumptions'),H.indexOf('function _loanBalanceMode(')),ctx);
// Use the actual existing trajectory/value helpers and full amount-series renderer.
for(const name of ['_faSeriesEnsure','faSeriesTrajectory','faSeriesValue']){const line=H.split('\n').find(l=>l.startsWith((name.startsWith('_')?'function ':'window.')+name+(name.startsWith('_')?'(':'=')));assert(line,name);vm.runInContext(line,ctx);}
ctx._faSeriesExplicitIsOpen=()=>false;
const a=H.indexOf('function _faSeriesEditor('),b=H.indexOf('// ===== r340:',a);vm.runInContext(H.slice(a,b),ctx);
ctx.loanAmountMode(0,'shared');ctx.loanSharedCreate(0);let row=ctx.cfg.assumptions.balance_components_model.inputs[0],sid=row.id;
assert.equal(ctx.cfg.assumptions.balance_components_model.enabled,false);assert.equal(row.spec.components.length,1);
ctx.sharedComponentAdd(sid);assert.equal(row.spec.components.length,2);
let path='assumptions.balance_components_model.inputs.0.spec.components.0.amount_spec';ctx.window.faSeriesValue(path,'value','6493634','dollars');assert.equal(row.spec.components[0].amount_spec.value,6493634);
ctx.window.faSeriesValue('assumptions.balance_components_model.inputs.0.spec.components.0.weight_spec','value','74','rate');assert.equal(row.spec.components[0].weight_spec.value,.74);
ctx.loanAmountFactorAdd(0);const fp='assumptions.lending_products.0.balance_driver.average_balance_per_customer_spec.factors.0';ctx.window.faSeriesValue(fp,'value','4.11','rate');assert(Math.abs(ctx.getPath(fp).value-.0411)<1e-15);
let h=ctx._loanAmountEditor(0,ctx.cfg.assumptions.lending_products[0],'assumptions.lending_products.0');assert(h.includes('Shared assumption × factors'));assert(h.includes('6493634'));assert(h.includes('74.0000'));assert(h.includes('4.1100'));assert(h.includes('affect every consumer'));
ctx.setPath('assumptions.balance_components_model.inputs.0.name','Reusable industry input');assert.equal(ctx.cfg.assumptions.lending_products[0].balance_driver.average_balance_per_customer_spec.input_id,sid);
ctx.getPath(fp).name='Advance percentage';ctx.window.faSeriesTrajectory(fp,'growth');assert.equal(ctx.getPath(fp).name,'Advance percentage');assert.equal(ctx.getPath(fp).base,.041100000000000005);
ctx._bcState=()=>ctx.cfg.assumptions.balance_components_model;ctx.appStatus=(kind,msg)=>{ctx.lastStatus={kind,msg}};
vm.runInContext(H.split('\n').find(l=>l.startsWith('window.bcInputRemove=')),ctx);ctx.window.bcInputRemove(0);assert.equal(ctx.lastStatus.kind,'err');assert.equal(ctx._sharedInputs().length,1);
ctx.sharedComponentRemove(sid,1);assert.equal(row.spec.components.length,1);
ctx.cfg.assumptions.interest_balance_model={enabled:true};ctx._bcLegacyAdapter=()=>({enabled:true,inputs:[{id:'legacy-input'}],components:[{id:'legacy-component'}]});vm.runInContext(H.split('\n').find(l=>l.startsWith('window.bcAdoptLegacy=')),ctx);ctx.window.bcAdoptLegacy();assert.equal(ctx.cfg.assumptions.balance_components_model.components[0].id,'legacy-component');assert(ctx.cfg.assumptions.balance_components_model.inputs.some(x=>x.id===sid));assert.equal(ctx.cfg.assumptions.interest_balance_model.enabled,false);
ctx.loanAmountMode(0,'entered');assert.equal(ctx.cfg.assumptions.lending_products[0].balance_driver.average_balance_per_customer_spec.value,17);
assert(ctx._loanAmountEditor(0,ctx.cfg.assumptions.lending_products[0],'assumptions.lending_products.0').includes('$ / unit'));
console.log('PASS shared registry reuse without accounting activation, component add/remove, dollar and percent units, separate factor, rename identity, Entered restoration and rendered controls');
