"""Catalog dialog opens/searches even when a publisher omits optional measures."""
from pathlib import Path
import subprocess

def main():
    html=Path('web/console_v2.html').read_text();a=html.index('async function openSourceCatalog(');b=html.index('async function browseSourceCatalog(',a)
    js=r'''
const assert=require('node:assert/strict');let selected=null,shown=false;
const rows=[{series_id:'fee.economics',label:'Interchange fee income',family:'Fee income',unit:'money_flow',consumers:['settlement_balance'],driver:'fee_stream_economics'},
{series_id:'purchases',label:'Card purchases',family:'Fee Product',unit:'money_flow',measures:[],consumers:['lending_funded_flow'],driver:'fee_stream_quantity'}];
async function loadSourceCatalog(){return rows};function esc(v){return String(v)};
const list={children:[],_html:'',set innerHTML(v){this._html=v;this.children=[]},get innerHTML(){return this._html},appendChild(x){this.children.push(x)}};
const input={value:'',focus(){}};const dlg={style:{},querySelector(q){return q==='input'?input:list},addEventListener(){},showModal(){shown=true},close(){},remove(){}};
const document={getElementById(){return null},createElement(kind){return kind==='dialog'?dlg:{style:{}}},body:{appendChild(){}}};
''' + html[a:b] + r'''
(async()=>{await openSourceCatalog('lending_funded_flow',x=>selected=x.series_id);
assert(shown);assert.equal(list.children.length,2);assert(list.children[0].disabled);assert(!list.children[1].disabled);
input.value='purchases';input.oninput();assert.equal(list.children.length,1);list.children[0].onclick();assert.equal(selected,'purchases');
input.value='not found';input.oninput();assert(list.innerHTML.includes('No matching sources'));
console.log('PASS source dialog opens with optional measures absent, searches, filters eligibility and selects stable quantity ID');})();
'''
    subprocess.run(['node'],input=js,text=True,check=True)
if __name__=='__main__':main()
