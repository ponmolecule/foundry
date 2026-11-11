// r482: a blank cell inside a pasted schedule is refused with the period named (it used to be skipped,
// shifting every later value one period early). Trailing empty cells and explicit zeros are fine.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const H=fs.readFileSync('web/console_v2.html','utf8');
const ctx={status:null,appStatus(k,m){ctx.status=[k,m];},PPY:()=>12,NP:()=>36};vm.createContext(ctx);
vm.runInContext(H.slice(H.indexOf('function _seriesExplicitValues('),H.indexOf('function _seriesExplicitPasteInput(')),ctx);
vm.runInContext(H.slice(H.indexOf('function _feeParseExplicitValues('),H.indexOf('function _feeParseExplicitValues(')+400).split('\n')[0],ctx);
vm.runInContext(H.slice(H.indexOf('// r480: a pasted schedule must match'),H.indexOf('function _seriesCadenceOptions(')),ctx);
const P=t=>ctx._seriesExplicitValues(t),G=(t,c)=>{ctx.status=null;const ok=ctx._seriesPasteLengthOk(P(t),c);return [ok,ctx.status&&ctx.status[1]];};
const row=a=>a.join('\t');
// 1. Blanks keep their position.
assert.deepStrictEqual([...P('1\t\t3').map(x=>x.value)],[1,3]);assert.deepStrictEqual([...P('1\t\t3').blanks],[2]);
assert.deepStrictEqual([...P('1\n\n3').blanks],[2]);assert.deepStrictEqual([...P('1,,3').blanks],[2]);
// 2. A blank inside a full-length yearly paste is refused, naming the period, before any count check.
assert.deepStrictEqual(G(row(['1','','3']),'year'),[false,'Y2 is blank. Every period needs a value (enter 0 for zero). Nothing was loaded; the saved schedule is unchanged.']);
// 3. One blank plus one extra value used to load with every later value shifted early; now refused.
assert.deepStrictEqual(G(row(['1','','3','4']),'year')[0],false);
// 4. Several blanks are listed.
assert.strictEqual(G(Array.from({length:36},(_,i)=>i%10===4?'':String(i)).join('\n'),'month')[1].split('.')[0],'M5, M15, M25, M35 are blank');
// 5. Explicit zeros, trailing empty cells from a spreadsheet selection, and leading/trailing blank lines are fine.
assert.deepStrictEqual(G(row(['0','0','0']),'year'),[true,null]);
assert.deepStrictEqual(G('1\t2\t3\t\t','year'),[true,null]);
assert.deepStrictEqual(G('\n1\n2\n3\n\n','year'),[true,null]);
assert.deepStrictEqual(G('1\t\n2\t\n3\t\n','year'),[true,null],'trailing empty column per row');
// 6. Fee parser carries the same blank positions.
const f=ctx._feeParseExplicitValues('5\t\t7');assert.deepStrictEqual([...f],[5,7]);assert.deepStrictEqual([...f.blanks],[2]);
// 7. Every paste handler passes the parsed array (not a count) so blanks reach the guard.
assert.strictEqual((H.match(/_seriesPasteLengthOk\((raw|vals|values)\.length/g)||[]).length,0);
assert((H.match(/_seriesPasteLengthOk\((raw|vals|values),/g)||[]).length>=27);
console.log('PASS r482 paste blanks: positions kept, blank refused with period named, zeros and selection padding accepted, all handlers pass the parsed array');
