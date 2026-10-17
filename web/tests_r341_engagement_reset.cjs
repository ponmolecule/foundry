// r341: the reset dialog renders the server's area report honestly and never mutates cfg.
const assert=require('node:assert/strict'),fs=require('fs'),vm=require('vm');
const html=fs.readFileSync(__dirname+'/console_v2.html','utf8');
const a=html.indexOf('// ===== r341: engagement reset'),b=html.indexOf('\nfunction renderConfigTab(){');
assert(a>0&&b>a,'reset block present');
const ctx={esc:s=>String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/"/g,'&quot;'),LC:{baseline:'{}',state:()=> 'MODIFIED'},window:{},document:{getElementById:()=>null}};
vm.createContext(ctx);vm.runInContext(html.slice(a,b)+';this.set=v=>{_engReset=v};this.get=()=>_engReset;',ctx);
const areas=[{id:'lending',label:'Lending',count:4,present:true,locks:true},{id:'deposits',label:'Deposits',count:2,present:true,locks:true},
 {id:'fees',label:'Fees and off-book',count:0,present:false,locks:false},{id:'other',label:'Other model settings',count:1,present:true,locks:true,keys:['tax rate']}];
ctx.set({policy:{values:{name:'Zero <Bank>',periods_per_year:4,years:3},early:false},areas,sel:new Set(['lending','deposits']),busy:false,error:''});
let h=ctx._engResetHtml();
for(const m of h.matchAll(/on(?:change|click)="([^"]+)"/g))new vm.Script(m[1]);
assert(!/undefined|NaN/.test(h),'no leaks');
assert(h.includes('Zero &lt;Bank')&&!h.includes('<Bank'),'name escaped');
assert.equal((h.match(/Locks setup/g)||[]).length,3,'three areas marked as locking');
assert(h.includes('Setup stays locked by Other model settings.'),'partial selection says what still locks');
assert(h.includes('Kept, re-baselined: tax rate'),'other settings say they are kept');
assert(h.includes('Reset 2 areas'));
ctx.engagementResetToggle('all',true);h=ctx._engResetHtml();
assert(h.includes('>Reset all</button>')&&h.includes('editable in Engagement setup'),'reset all unlocks');
ctx.engagementResetToggle('all',false);h=ctx._engResetHtml();
assert(h.includes('Select at least one area.')&&/ers-go"[^>]*disabled/.test(h),'nothing selected disables reset');
ctx.LC.state=()=> 'NEW-UNSAVED';assert(ctx._engResetHtml().includes('cannot be reverted'),'unsaved engagement warns honestly');
console.log('PASS reset dialog');
