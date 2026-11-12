// Browser-independent checks for the actual statement helpers and unfunded verdict.
// The full r414 browser suite remains the integration check; its cash label is updated.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const html=fs.readFileSync('web/console_v2.html','utf8');
let native=12,n=14;
const ctx={window:{},PPY:()=>native,NP:()=>n,renderContent:()=>{},
  refresh:()=>{throw Error('View reran engine');},scheduleAutosave:()=>{throw Error('View saved inputs');},
  calcText:()=>'',refCell:()=>'',noteFor:()=>'',PERLAB:i=>'M'+i,
  cellNum:v=>'<td>'+v+'</td>',_precedenceZero:()=>null};
vm.createContext(ctx);
vm.runInContext(html.slice(html.indexOf('function incomeStatementView('),html.indexOf('function incomeStatementValues(')),ctx);
vm.runInContext(html.slice(html.indexOf('function balanceSheetView('),html.indexOf('function balanceSheetToolbar(')),ctx);
vm.runInContext(html.slice(html.indexOf('function balanceSheetRow('),html.indexOf('function balanceSheetRow(')+html.slice(html.indexOf('function balanceSheetRow(')).indexOf('\n}\n')+3),ctx);
const plain=x=>JSON.parse(JSON.stringify(x)),full=[9999,...Array.from({length:14},(_,i)=>i+1)];
for(const [ppy,want] of [[12,full],[4,[9999,3,6,9,12,14]],[1,[9999,12,14]]]){
  ctx.window._balanceViewPPY=ppy;
  const view=ctx.balanceSheetView();assert.deepStrictEqual(plain(ctx.balanceSheetValues(full,view,true)),want);
  const row=ctx.balanceSheetRow(view,true,'Cash position / unfunded if negative',full,'','cash');
  const cells=[...row.matchAll(/<td>(.*?)<\/td>/g)].map(m=>m[1]);
  assert.equal(cells.shift(),'Cash position / unfunded if negative');
  assert.deepStrictEqual(cells.map(Number),want);
}
ctx.window._balanceViewPPY=4;n=4;
assert.deepStrictEqual(plain(ctx.balanceSheetValues([999,1,2,null,4],ctx.balanceSheetView(),true)),[999,null,4]);
native=4;n=14;ctx.window._balanceViewPPY=12;
assert.equal(ctx.balanceSheetView().selected,4);
const start=html.indexOf('function _verdictCall(r){'),end=html.indexOf('\n}',start)+2;
vm.runInContext(html.slice(start,end),ctx);
const verdict=ctx._verdictCall({funding:{feasible:false}});
assert.equal(verdict.cls,'bad');assert.equal(verdict.gated,true);assert(verdict.call.includes('Unfunded'));
assert(html.includes("rowBS('Cash position / unfunded if negative'"));
console.log('PASS actual balance-row rendering and monthly/quarterly/annual sampling, opening, partial/missing periods and unfunded-plan verdict');
