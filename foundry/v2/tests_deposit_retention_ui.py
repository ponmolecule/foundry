"""Run actual browser functions in Node: state changes, identity and menu rendering."""
import json
import subprocess
from pathlib import Path


def main():
    html=Path('web/console_v2.html').read_text()
    start=html.index('const _depositPoolOpen = new Set();')
    end=html.index('function _loanBalanceMode(p)',start)
    js=r'''
const window=globalThis;
let cfg={assumptions:{deposit_products:[{name:'DDA',growth_per_period:.05,runoff_per_period:.01,new_deposits_per_period:1000,overrides:{growth_per_period:{1:.1}}},{name:'Savings'}],obs_exposures:[{name:'Upstream',fee_streams:[{name:'Activity',quantity_series_id:'tpv',basis:'transaction',driver:{source:'constant',params:{flow_path:{unit_kind:'money_flow'}}}},{name:'Migration',quantity_series_id:'migration',basis:'transaction',driver:{source:'stream_ref',params:{coefficient:{kind:'pct',semantics:'share'}}}}]}],lending_products:[{name:'Facility',balance_mode:'funded_flow_level'}]}};
let serial=0,lastRes=null;
function _seriesId(k){return k+'-'+(++serial);}function renderContent(){}function refresh(){}
function getPath(p){return p.split('.').reduce((a,k)=>a&&a[k],cfg);}function setPath(p,v){let ks=p.split('.'),key=ks.pop(),obj=ks.reduce((a,k)=>a[k],cfg);obj[key]=v;}
function esc(v){return String(v).replace(/[<>&"']/g,c=>({'<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;',"'":'&#39;'}[c]));}
function _nativeFlowPeriod(){return 'month';}
function _faSeriesEditor(p,s,l){return '<div data-editor="'+p+'">'+l+'</div>';}
function _explicitPreviewHtml(){return '<div>preview</div>';}
function fmtComma(v){return String(v);}
''' + html[start:end]+ r'''
function assert(v,m){if(!v)throw new Error(m);}
depositMode(0,'pool');
const p=cfg.assumptions.deposit_products[0],g=cfg.assumptions.deposit_retention_pools[0];
assert(p.growth_per_period===0&&p.runoff_per_period===0&&p.new_deposits_per_period===0&&!p.overrides.growth_per_period,'old balance dynamics conflict');
assert(p.retention_pool_id===g.id&&p.pool_share_spec.value===1,'first member');
assert(g.sweep_fee_balance_measure==='period_average'&&g.opening_swept_balance===0,'new pool fee defaults');
assert(_depositPoolOpen.has(g.id),'new pool should open');
depositMode(1,'pool');depositPoolSelect(1,g.id);
assert(cfg.assumptions.deposit_products[1].pool_share_spec.value===0,'new member should not silently double allocation');
const markup=depositBalanceHtml(p,'assumptions.deposit_products.0');
assert(markup.includes('Maximum retained share')&&markup.includes('Fee on swept-out balances'),'menu content '+markup);
assert(markup.includes('Opening swept-out balance (off-book, $000s)')&&markup.includes('Average balance'),'opening sweep control and fee basis');
assert(markup.includes('ontoggle')&&markup.includes(' open'),'shared settings preserve expanded state');
depositPoolAdjustment('assumptions.deposit_retention_pools.0');
assert(depositBalanceHtml(p,'assumptions.deposit_products.0').includes('Remove adjustment'),'adjustment remove action');
depositOperandSource('assumptions.deposit_retention_pools.0.balance_spec','derived',false);
const d=g.balance_spec.derived;
assert(g.balance_spec.owner_module==='deposits'&&g.balance_spec.series_id&&d.kind==='activity_held','derived identity');
depositActivitySource('assumptions.deposit_retention_pools.0.balance_spec.derived.activity','link');
const loan=depositSources('fee_quantity','transaction').find(x=>x.kind==='lending_funded_flow');
depositActivityLink('assumptions.deposit_retention_pools.0.balance_spec.derived.activity',loan.id);
assert(d.activity.link.kind==='lending_funded_flow','lending link type');
assert(depositSources('fee_share').find(x=>x.id==='migration'),'existing migration coefficient available');
assert(depositOperandHtml('assumptions.deposit_retention_pools.0.balance_spec',g.balance_spec,'Source',false).includes('Holding days'),'derived rendering');
depositMode(0,'level');assert(cfg.assumptions.deposit_retention_pools.length===1,'shared pool preserved');
depositMode(1,'rollforward');assert(!cfg.assumptions.deposit_retention_pools,'unused pool removed');
console.log('PASS deposit UI state, shared identities, typed links, clean removal and rendering');
'''
    r=subprocess.run(['node','-e',js],text=True,capture_output=True)
    assert r.returncode==0,r.stderr
    print(r.stdout.strip())
    # Verify the existing schedule editor remains the sole paste implementation.
    assert '_faSeriesEditor(path,sp' in html[start:end]
    assert '<textarea' not in html[start:end]
    assert 'sweptBalance' in html[html.index('if(currentTab==="detail")'):] if 'if(currentTab==="detail")' in html else 'sweptBalance' in html
    print('PASS existing Load / Clear / Close schedule editor reused; Product Detail exposes sweep results')


if __name__=='__main__':main()
