"""Zero missing-rate defaults and explicit entered-rate preservation."""
import copy,json
from .engine_q_a import run_pf_a
from .engine_q_b import run_pf_b
from .run_q import run_v2

def main():
    for path,run in [('foundry/fixtures/core_bank_test_base.json',run_pf_a),('foundry/fixtures/parity/configs/pf_b_base.json',run_pf_b)]:
        c=json.load(open(path));a=c['assumptions'];a['nie_detail']={'categories':[],'other_gross_up_rate':0,'occ_simplified_enabled':False}
        missing=run(c);zero=copy.deepcopy(c);zero['assumptions']['nie_detail']['fdic_bp_ann']=0
        assert missing==run(zero),path
        explicit=copy.deepcopy(c);explicit['assumptions']['nie_detail']['fdic_bp_ann']=5
        assert run(explicit)['is']['otherOpex']!=missing['is']['otherOpex'],path
    # A residual book with $30m capital earns nothing without an authored residual yield.
    c=json.load(open('foundry/fixtures/universal_template_bank.json'));a=c['assumptions'];c['target_state']['initial_capital']=30_000_000
    for key in ('lending_products','deposit_products','obs_exposures','securities_afs','securities_htm','managed_securities_portfolios','capital_raises','scheduled_borrowings'):a[key]=[]
    for key in ('premises_equipment','intangibles','other_assets','other_liabilities','cash_yield','overhead_per_period','cash_target_pct_deposits'):a[key]=0
    for key in ('nie_detail','interest_balance_model','fixed_assets','other_liabilities_model','cost_pools','cac_feeds','fee_modules','securities_yield'):a.pop(key,None)
    c['pre_opening']={'expenses':[]};a['surplus_allocation_policy']='residual_securities'
    missing=run_pf_a(c);a['securities_yield']=0;assert run_pf_a(c)==missing
    assert missing['bs']['sec'][0]==30_000_000 and all(v==0 for v in missing['is']['secInt'])
    a['securities_yield']=.04;assert run_pf_a(c)['is']['secInt'][0]>0
    c=json.load(open('foundry/fixtures/core_bank_test_base.json'));c['assumptions']['nie_detail']['fdic_bp_ann']=5
    assert run_v2(c)['run_hash']=='89f8d8f7231d'
    print('PASS Profile A/B missing FDIC = explicit zero; explicit 5 still accrues; explicit-5 core result fingerprint pinned')
if __name__=='__main__':main()
