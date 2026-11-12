const fs=require('fs'),vm=require('vm'),assert=require('assert');
const html=fs.readFileSync('web/console_v2.html','utf8');
const start=html.indexOf("let t=_fkRow('Name',_fkName(c.name"),end=html.indexOf("  b+=_fkSec('Identity','',t);",start);
assert(start>0&&end>start);
function render(comp,ppy=12){
 const inputs=[],sels=[];
 const x={c:comp,kind:comp.treatment,path:'assumptions.balance_components_model.components.0',i:0,
  _BC_TREAT:[[comp.treatment,'Cash','Cash']],PPY:()=>ppy,_numInput:String,
  _fkRow:(label,value)=>label+':'+value+'\n',_fkName:()=>'',_fkSel:(options,value,action)=>{sels.push({options,value,action});return options.map(o=>o[1]).join('|');},
  _fkNum:(value,action,unit,opts)=>{inputs.push({value,action,unit,opts});return String(value);},
  _fkInfo:String,_fkChk:()=>'',renderContent:()=>{},refresh:()=>{},_pf:s=>Number(s.replaceAll(',','')),
  _bcState:()=>({components:[comp]}),setPath:(path,value)=>{comp[path.split('.').at(-1)]=value;}};
 vm.createContext(x);vm.runInContext(html.slice(start,end)+'\nresult=t;',x);return {x,inputs,sels};
}
const comp={treatment:'residual_cash',interest_balance_measure:'prior_quarter_average'};
const before=JSON.stringify(comp);let r=render(comp);
assert.equal(JSON.stringify(comp),before,'rendering cannot seed a historical value');
assert(r.x.result.includes('Previous-quarter beginning balance'));
assert(!r.x.result.includes('First prior-end balance'));
const field=r.inputs.find(i=>i.opts.aria==='Previous-quarter beginning balance');assert(field);assert.equal(field.value,'');assert.equal(field.unit,'$000s');
vm.runInContext('(function(){'+field.action+'}).call({value:"123.456789"});',r.x);
assert.equal(comp.prior_quarter_opening_balance,123456.789);
vm.runInContext('(function(){'+field.action+'}).call({value:""});',r.x);
assert(!Object.hasOwn(comp,'prior_quarter_opening_balance'),'blank is missing, not silent zero');
const old={treatment:'residual_cash',interest_balance_measure:'prior_end'};r=render(old);
assert(r.x.result.includes('First prior-end balance'));assert(!r.x.result.includes('Previous-quarter beginning balance:'));
assert(!render(old,1).sels[1].options.some(o=>o[0]==='prior_quarter_average'));
console.log('PASS previous-quarter basis control, required historical input, $000s conversion, blank handling, old controls and inert rendering');
