const assert=require('node:assert/strict'),fs=require('fs'),vm=require('vm');
const html=fs.readFileSync(__dirname+'/console_v2.html','utf8');
const keys=['s1','s2','s6','s3','s4','s5'];
function el(){return {hidden:false,attrs:{},classList:{values:new Set(),toggle(k,v){if(v)this.values.add(k);else this.values.delete(k);}},setAttribute(k,v){this.attrs[k]=v;},querySelector(){return this.heading;},heading:{setAttribute(k,v){this[k]=v;}}};}
const sections=Object.fromEntries(keys.map(k=>[k,el()])),items=Object.fromEntries(keys.map(k=>[k,el()]));let fits=0;
const ctx={window:{_fsxOpen:{}},_FSX:keys.map(k=>[k]),document:{getElementById:id=>sections[id.replace('fsx-','')],querySelector:s=>items[s.match(/data-k="([^"]+)"/)[1]]},fitControls(){fits++}};
vm.createContext(ctx);vm.runInContext(html.slice(html.indexOf('function _fsxActiveKey()'),html.indexOf('let _renderedAuthoringTab')),ctx);
ctx.fsxGo=ctx.window.fsxGo;ctx.fsxToggle=ctx.window.fsxToggle;
assert.equal(ctx._fsxActiveKey(),'s1');
const original={weights:[1,1,.5],opening_history:[0,20]};ctx.cfg=original;const before=JSON.stringify(original);
for(const k of keys){ctx.fsxGo(k);assert.deepEqual(keys.filter(id=>!sections[id].hidden),[k]);assert.deepEqual(keys.filter(id=>items[id].classList.values.has('on')),[k]);assert.equal(items[k].attrs['aria-current'],'page');assert.equal(sections[k].heading['aria-expanded'],true);}
ctx.fsxGo('s3');ctx.fsxToggle('s3');assert.equal(sections.s3.heading['aria-expanded'],false);assert.equal(items.s3.attrs['aria-current'],'page');ctx.fsxGo('s3');assert.equal(sections.s3.heading['aria-expanded'],true);
ctx.fsxGo('invalid');assert.equal(ctx.window._fsxActive,'s3');assert.equal(JSON.stringify(original),before);assert.equal(ctx._fsxActiveKey(),'s3');
assert(html.includes('fsx-sec[hidden]{display:none!important}'));assert(!html.includes('onclick="fsxAll(true);return false"'));assert(html.includes('shell.className=\'fsx fsx-focused\''));
console.log('PASS six single-visible sections, active navigation/accessibility, collapse/reopen, invalid target, financial-state preservation, re-render selection');
