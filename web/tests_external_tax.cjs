const fs=require('fs'),vm=require('vm'),assert=require('assert');
const html=fs.readFileSync('web/console_v2.html','utf8');for(const m of html.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/gi))new vm.Script(m[1]);
const js=html.slice(html.indexOf('const TAX_BLOCK_TYPES='),html.indexOf('function otherIncomeState()'));
const c={console,cfg:{assumptions:{tax_rate:.27,tax_policy:{interim_method:'ytd_actual'},tax_detail:{enabled:true,va_mode:'full'}}},renderContent(){},refresh(){},_nativeFlowPeriod(){return 'month'},otherIncomeSources(){return []},_pf:Number,confirm(){return true},esc:x=>String(x??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('"','&quot;'),_faSeriesEditor(){return '<span>schedule editor</span>'}};c.window=c;c.setPath=(p,v)=>{let a=c.cfg;let ks=p.split('.');for(const k of ks.slice(0,-1))a=a[k]||(a[k]={});a[ks.at(-1)]=v};vm.createContext(c);vm.runInContext(js,c);
const policy=JSON.stringify(c.cfg.assumptions.tax_policy);c.taxModeSet('external');assert.equal(c.cfg.assumptions.external_tax.inputs[0].amount_spec.value,0);c.extTaxAdd('input');c.extTaxAdd('input');c.extTaxAdd('rule');const m=c.cfg.assumptions.external_tax;assert.equal(new Set([...m.inputs,...m.rules].map(x=>x.id)).size,4);
const before=JSON.stringify(m);const output=vm.runInContext('externalTaxHtml()',c);assert.equal(JSON.stringify(m),before,'render must not mutate');for(const label of ['Derived rules','Current tax provision','Separate payment source','Explicit recognized balances','safe_div','bank_pretax','configured_tax_rate','value="27"'])assert(output.includes(label),label);
c.setPath('assumptions.tax_rate',.19);assert(vm.runInContext('externalTaxHtml()',c).includes('value="19"'));assert.equal(JSON.stringify(m),before,'rate edit preserves authored sources');
c.taxModeSet('calculated');assert.equal(JSON.stringify(m),before,'mode switch preserves external authoring');assert.equal(JSON.stringify(c.cfg.assumptions.tax_policy),policy,'mode switch preserves calculated policy');c.taxModeSet('external');assert.equal(JSON.stringify(c.cfg.assumptions.external_tax),before);
if(!process.argv.includes('--emit-rules'))console.log('PASS external tax UI: zero default, distinct IDs, immutable rendering, rule/source controls, safe mode roundtrip and syntax');

// Choose operations and source IDs, never hand-type the generated expressions.
const model=c.cfg.assumptions.external_tax;model.inputs=[{id:'outside',name:'Outside income',unit:'money'},{id:'initial',name:'Opening balance',unit:'money'}];model.rules=[{id:'remaining',name:'Remaining losses',unit:'money',expression:'0'}];
function build(id,op,args){let i=model.rules.findIndex(x=>x.id===id);if(i<0){model.rules.push({id,name:id,unit:'money',expression:'0'});i=model.rules.length-1;}c.extTaxBuild(i);c.extTaxDraftSet(i,'op',op);args.forEach((id,index)=>c.extTaxDraftSet(i,'arg',{id,index}));c.extTaxApply(i);assert(!vm.runInContext(`extTaxDraft(${i})`,c),id+' applied');return model.rules[i];}
build('total','sum',['bank_pretax','outside']);build('positive_total','positive',['total']);build('capacity','multiply',['positive_total','configured_nol_limit']);build('prior_loss','prior',['remaining','initial']);build('used','min',['prior_loss','capacity']);build('remaining','difference',['prior_loss','used']);build('taxable','difference',['positive_total','used']);build('current','multiply',['taxable','configured_tax_rate']);build('allocation','divide',['bank_pretax','total']);build('allocated','multiply',['current','allocation']);
assert.equal(model.rules.at(-2).unit,'scalar');assert.equal(model.rules.find(x=>x.id==='prior_loss').expression,'prior(remaining, initial)');
assert(vm.runInContext('extTaxBuilderHtml(0)',c).includes('Edit calculation'));
const good=JSON.stringify(model.rules[0]);c.extTaxBuild(0);c.extTaxDraftSet(0,'arg',{index:0,id:'bank_pretax'});c.extTaxApply(0);assert.equal(JSON.stringify(model.rules[0]),good,'incomplete draft must not change rule');
c.extTaxDraftSet(0,'arg',{index:1,id:'configured_tax_rate'});c.extTaxApply(0);assert.equal(JSON.stringify(model.rules[0]),good,'mixed units must not change rule');
c.extTaxDraftSet(0,'arg',{index:1,id:'remaining'});c.extTaxApply(0);assert.equal(JSON.stringify(model.rules[0]),good,'indirect cycle must not change rule');
c.extTaxCancel(0);assert.equal(JSON.stringify(model.rules[0]),good,'cancel preserves rule');
assert.throws(()=>c.extTaxCompile(1,{op:'sum',args:['bank_pretax','taxable']}),/circular/,'indirect cycle through existing rules');
assert.throws(()=>c.extTaxCompile(0,{op:'multiply',args:['bank_pretax','outside']}),/scalar/);
assert.throws(()=>c.extTaxCompile(0,{op:'divide',args:['configured_tax_rate','outside']}),/scalar/);
assert.equal(c.extTaxCompile(0,{op:'max',args:['bank_pretax','outside']}).expression,'max(bank_pretax, outside)');
assert.equal(c.extTaxCompile(0,{op:'prior',args:['remaining','configured_opening_nol']}).expression,'prior(remaining, configured_opening_nol)');
c.extTaxNolLimit('75');assert.equal(c.cfg.assumptions.tax_policy.nol_utilization_limit_pct,.75);
for(const label of ['<span>Measure</span>','<span>Source</span>','<span>Units</span>','<span>Identifier</span>']){model.inputs=[{id:'visible',name:'Visible',source:'entered',unit:'money'}];assert(vm.runInContext('externalTaxHtml()',c).includes(label),label);}
if(process.argv.includes('--emit-rules'))console.log(JSON.stringify(model.rules));else console.log('PASS selector builder: composed allocation, prior recurrence, inferred units, draft/cancel, invalid selection and cycle guards, setting reuse and visible labels');
