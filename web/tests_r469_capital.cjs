const assert=require('assert'),fs=require('fs'),vm=require('vm');
const html=fs.readFileSync('web/console_v2.html','utf8');
for(const ppy of [12,4,1]){
 let renders=0,globals=0,runs=0,shown=0;
 const ctx={window:{},cfg:{assumptions:{}},PPY:()=>ppy,renderGlobals(){globals++},renderContent(){renders++;shown=ctx.cfg.assumptions.scheduled_borrowings.length},refresh(){runs++}};
 vm.createContext(ctx);vm.runInContext(html.slice(html.indexOf('window.sbAdd = function(){'),html.indexOf('window.raiseAdd = function(){')),ctx);
 for(let i=1;i<=3;i++){ctx.window.sbAdd();assert.equal(shown,i,'new borrowing must appear without another action');assert.equal(renders,i);assert.equal(runs,i);assert.equal(globals,i);}
 const rows=ctx.cfg.assumptions.scheduled_borrowings;assert.equal(rows.length,3);assert.notStrictEqual(rows[0],rows[1]);assert(rows.every(b=>(ppy===4?b.quarter:b.period)===1));
}
for(const m of html.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script>/gi))if(!/\bsrc=/.test(m[1]))new vm.Script(m[2]);
console.log('PASS scheduled borrowing additions render immediately at all model cadences; inline scripts compile');
