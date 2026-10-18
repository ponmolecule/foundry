"""Blank stream grids recover in place after preview, without requiring preexisting icons."""
from pathlib import Path
import subprocess

def main():
    html=Path('web/console_v2.html').read_text();a=html.index('function refreshStreamFigures(){');b=html.index('\n}',a)+2
    js=r'''
const assert=require('node:assert/strict');const window=globalThis;let lastRes=null;
const metas0=[{qid:'count',basis:'account'},{qid:'money',basis:'transaction'}],metas1=[{qid:'other',basis:'account'}];window._stMetaByFi={0:metas0,1:metas1};
function _stProvP(m){return 'M'+Math.max(0,...m.map(x=>(x.qty||[]).length))};
function _stCellHtml(m,k,fi){return m[k].qty?.length?fi+':'+m[k].qty.at(-1):'—'};
function _stSrcRows(){return ''};function _stSetupFeeRow(){return ''};
function make(fi,n){const cells=Array.from({length:n},()=>({innerHTML:'—'}));const heading={textContent:'Driver · M'};
const tb={querySelectorAll(sel){return sel==='tr'?cells.map(c=>({classList:{contains(){return false}},querySelector(){return c}})):[]},insertAdjacentHTML(){}};
return {offsetParent:{},cells,heading,getAttribute(){return String(fi)},querySelector(sel){if(sel.includes('data-ip'))throw Error('Must not depend on icons');return sel==='tbody'?tb:sel==='thead th.num'?heading:null}}};
const first=make(0,2),second=make(1,1);const document={querySelectorAll(){return [first,second]}};
''' + html[a:b] + r'''
refreshStreamFigures();assert(first.cells.every(c=>c.innerHTML==='—'));
lastRes={fee_stream_quantities:{series:{count:[1,2],money:[23000,46000],other:[9,10]}}};refreshStreamFigures();
assert.equal(first.cells[0].innerHTML,'0:2');assert.equal(first.cells[1].innerHTML,'0:46000');assert.equal(second.cells[0].innerHTML,'1:10');assert.equal(first.heading.textContent,'Driver · M2');
lastRes=null;refreshStreamFigures();assert(first.cells.every(c=>c.innerHTML==='—'));assert(second.cells.every(c=>c.innerHTML==='—'));
lastRes={fee_stream_quantities:{series:{count:[3],money:[69000],other:[11]}}};refreshStreamFigures();assert.equal(first.cells[0].innerHTML,'0:3');assert.equal(first.heading.textContent,'Driver · M1');
console.log('PASS stream figures: all-dash startup, success, multiple owners, failure clearing, recovery and period header');
'''
    assert 'data-stream-owner="\'+_fi+\'"' in html
    subprocess.run(['node'],input=js,text=True,check=True)
if __name__=='__main__':main()
