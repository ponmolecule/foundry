const fs=require('fs'),vm=require('vm'),assert=require('assert');
const h=fs.readFileSync('web/console_v2.html','utf8');
let serial=0,fl={components:[]};const opts=[{value:'workforce_count::staff',series_id:'staff',label:'Workforce headcount · Staff'}];
const c={window:{},structuredClone,_seriesId:()=>`fa-${++serial}`,_faFormulaState:()=>fl,_faDriverOptions:()=>opts,_faSuggestedComponentName:()=> 'Staff',renderContent(){},refresh(){},esc:String,PPY:()=>12,fmtComma:String,_numInput:String,_depF2:(n,d)=>Number(n).toFixed(d),_depTrLab:()=> 'FLAT',_faSeriesEditor:(p,s,l,k)=>`<editor data-kind="${k}">${l}</editor>`,_faComponentDisplayName:x=>x.name,_lfxRes:()=>({res:null,stale:false})};
vm.createContext(c);
vm.runInContext(h.slice(h.indexOf('// Independent levels and entered quantities'),h.indexOf('window.faFormulaRemoveComponent=')),c);
vm.runInContext(h.slice(h.indexOf('/* r466: Fixed assets Formula / level as one component table:'),h.indexOf('function structuresSectionsHtml(')),c);
c.window.faFormulaAddEntered();assert.equal(fl.components.length,1);assert.equal(c._faComponentMode(fl.components[0]),'level');
const a=fl.components[0];a.multiplier_spec.value=120000;const dep={kind:'component_rates',base_rate_spec:{value:0}};
function render(){return c._faFormulaHtml(fl,fl.components,dep,opts,'gross',0)}
c.window._faCompOpen=a.component_id;let out=render();assert(out.includes('Entered asset level'));assert(out.includes('Asset level ($000s)'));assert(!out.includes('No driver selected'));
c.window.faFormulaComponentMode(0,'quantity');a.driver_spec.value=4;a.multiplier_spec.value=10000;out=render();assert(out.includes('Entered quantity'));assert(out.includes('Quantity before M1'));assert(!out.includes('No driver selected'));
c.window.faFormulaComponentMode(0,'level');assert.equal(a.multiplier_spec.value,120000);
c.window.faFormulaComponentMode(0,'quantity');assert.equal(a.driver_spec.value,4);assert.equal(a.multiplier_spec.value,10000);
c.window.faFormulaComponentMode(0,'link');a.lag_months=2;const before=JSON.stringify(a.driver_spec);c.window.faFormulaComponentMode(0,'level');c.window.faFormulaComponentMode(0,'link');assert.equal(JSON.stringify(a.driver_spec),before);assert.equal(a.lag_months,2);
out=render();assert(out.includes('Staff'));assert(!/undefined|NaN/.test(out));
console.log('PASS independent level/quantity rendering, source switching and restoration of entered paths and existing linked settings');
