"""r231a_fix1: opening sweep state, audit arithmetic, frozen identity and display index."""
import copy,json,subprocess
from pathlib import Path
from unittest.mock import patch
from .tests_deposit_retention import fixture,flat,near
from .engine_q_a import run_pf_a
from .validate_q import validate_errors_v2
from .parity import run_parity
from .run_q import run_v2
from . import registry_q


def main():
    c=fixture();g=c['assumptions']['deposit_retention_pools'][0]
    g.update(balance_spec={'source':'entered','trajectory':'explicit','cadence':'month','values':[1_000_000,2_000_000,3_000_000]+[3_000_000]*33,'extend':'error'},capacity_source='none',sweep_fee_balance_measure='period_average',opening_swept_balance=0)
    o=run_pf_a(copy.deepcopy(c));a=o['deposit_retention_pools']['pool']
    assert a['sweptBalance'][:3]==[500_000,1_000_000,1_500_000]
    assert a['sweepFeeBasis'][:3]==[250_000,750_000,1_250_000]
    assert a['beginningSweptBalance'][:3]==[0,500_000,1_000_000]
    assert a['sweepFee'][:3]==[2500,7500,12500]
    for q in range(36):near(sum(p['sweepFee'][q] for p in o['products'] if p['family']=='deposit'),a['sweepFee'][q])
    # Existing pools have an independent opening swept stock, not inferred from retained openings.
    g['opening_swept_balance']=500_000
    assert run_pf_a(copy.deepcopy(c))['deposit_retention_pools']['pool']['sweepFee'][:3]==[5000,7500,12500]
    # Fee accrues on a run-down average even when the ending swept balance is zero.
    g['balance_spec']['values']=[0]*36
    a=run_pf_a(copy.deepcopy(c))['deposit_retention_pools']['pool']
    assert a['sweepFee'][:2]==[2500,0]
    print('PASS zero / existing opening swept balances, runoff and category fee reconciliation')
    g['balance_spec']['values']=[1_000_000,2_000_000,3_000_000]+[3_000_000]*33
    g.pop('sweep_fee_balance_measure');g.pop('opening_swept_balance')
    assert run_pf_a(copy.deepcopy(c))['deposit_retention_pools']['pool']['sweepFee'][:3]==[5000,10000,15000]
    g['sweep_fee_balance_measure']='period_average'
    pub,raw=run_parity(c,include_exact=True)
    assert pub['deposit_retention_pools']['pool']['sweepFeeBasis'][:3]==[250,750,1250]
    assert pub['deposit_retention_pools']['pool']['sweepFee'][:3]==[2.5,7.5,12.5]
    # Retained openings still govern period-1 retained interest, independently of opening sweep state.
    p=c['assumptions']['deposit_products'][0];p.update(opening_balance=100_000,interest_balance_measure='period_average')
    d=next(p for p in run_pf_a(copy.deepcopy(c))['products'] if p['family']=='deposit')
    near(d['interestBasis'][0],112_500);near(d['intExp'][0],1125)
    for invalid in (-1,float('nan'),float('inf')):
        x=copy.deepcopy(c);x['assumptions']['deposit_retention_pools'][0]['opening_swept_balance']=invalid
        assert validate_errors_v2(x),invalid
    print('PASS legacy period-end default, public audit units, independent retained opening and fail-closed sweep opening')
    cfg=json.load(open('foundry/fixtures/core_bank_test_base.json'));res=run_v2(cfg)
    frozen=dict(config=cfg,config_hash=res['config_hash'],run_hash='f1384367e87a')
    with patch.object(registry_q,'get_entry',return_value=frozen):assert registry_q.verify('review-fixture')['match']
    print('PASS actual frozen-run verification against r230 fingerprint')
    html=Path('web/console_v2.html').read_text();start=html.index('function productReferenceIndex(');end=html.index('function _loanBalanceMode(',start)
    js=html[start:end]+'''
const inputs={deposit_products:[{name:'Same',index:'effr'},{name:'Same',index:'prime'},{name:'Plain'}],lending_products:[{name:'Same',index:'prime'}]};
const results=[{family:'lending',name:'Same'},{family:'deposit',name:'Same'},{family:'deposit',name:'Same'},{family:'deposit',name:'Plain'}];
function eq(a,b){if(a!==b)throw Error(a+' != '+b);}
eq(productReferenceIndex(results[0],results,inputs),'prime');
eq(productReferenceIndex(results[1],results,inputs),'effr');
eq(productReferenceIndex(results[2],results,inputs),'prime');
eq(productReferenceIndex(results[3],results,inputs),'sofr');
eq(productReferenceIndex({name:'Missing',family:'deposit'},results,inputs),null);
eq(productReferenceIndex({index:'effr'},[],{}),'effr');
console.log('PASS index display resolves duplicate names by family order, defaults and historical snapshot metadata');
'''
    r=subprocess.run(['node','-e',js],text=True,capture_output=True);assert r.returncode==0,r.stderr;print(r.stdout.strip())


if __name__=='__main__':main()
