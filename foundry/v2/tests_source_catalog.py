"""Behavioral catalog, native-dollar linking, timing, identity and audit checks."""
import copy
from .tests_deposit_retention import fixture, flat
from .source_catalog import catalog, require_balance, result_balances
from .validate_q import validate_errors_v2
from .engine_q_a import run_pf_a
from .run_q import run_v2
from .audit_workbook import _opex_component_detail_rows


def setup():
    c=fixture();a=c['assumptions']
    a['deposit_products'][0]['source_catalog_id']='category-a'
    a['deposit_products'][1]['source_catalog_id']='category-b'
    a['nie_detail']={'enabled':True,'fdic_bp_ann':0,'categories':[{'name':'Linked assessment','series_id':'assessment','fixed_spec':{'trajectory':'flat','value':0,'period':'month'},'linked_components':[{'driver':'formula_driver','component_id':'assessment-formula','factors':[{'kind':'linked','source':'catalog_quantity','series_id':'deposit_pool.pool.retainedBalance','measure':'period_end','name':'Retained deposits'},{'kind':'entered','op':'multiply','name':'Annual rate','display':'percent','periodized':True,'spec':{'trajectory':'flat','value':.0015,'period':'year'}}]}]}]}
    return c


def main():
    c=setup();assert not validate_errors_v2(c),validate_errors_v2(c)
    before=copy.deepcopy(c);rows=catalog(c['assumptions']);assert c==before
    sid='deposit_pool.pool.retainedBalance'
    assert require_balance(c['assumptions'],sid)['unit']=='money_stock'
    assert any(x['series_id']=='deposit.category-a.balance' for x in rows)
    # Native-dollar formula: 400k * 0.15% / 12 = $50 monthly.
    out=run_pf_a(c);blank=copy.deepcopy(c);blank['assumptions']['nie_detail']['categories'][0]['linked_components']=[]
    base=run_pf_a(blank)
    assert all(abs(x-y-50)<1e-7 for x,y in zip(out['is']['otherOpex'],base['is']['otherOpex']))
    # Source rename/reorder preserves link and amounts; both category and pool sources work.
    renamed=copy.deepcopy(c);a=renamed['assumptions'];a['deposit_retention_pools'][0]['name']='Renamed pool';a['deposit_products'].reverse()
    assert run_pf_a(renamed)['is']['otherOpex']==out['is']['otherOpex']
    factor=c['assumptions']['nie_detail']['categories'][0]['linked_components'][0]['factors'][0]
    factor['series_id']='bank.deposits';assert run_pf_a(c)['is']['otherOpex']==out['is']['otherOpex']
    factor['series_id']='deposit.category-a.balance';d=run_pf_a(c)
    assert abs(d['is']['otherOpex'][0]-base['is']['otherOpex'][0]-12.5)<1e-7
    # Average observes actual opening, not first period end copied back.
    factor['series_id']=sid;factor['measure']='period_average';d=run_pf_a(c)
    assert abs(d['is']['otherOpex'][0]-base['is']['otherOpex'][0]-25)<1e-7
    assert abs(d['is']['otherOpex'][1]-base['is']['otherOpex'][1]-50)<1e-7
    # Published units and audit factor agree with native engine math.
    result=run_v2(c);observed=result_balances(c,result,0)
    assert abs(observed[sid]['period_average']-200_000)<1e-7
    from .audit_workbook import _opex_component_detail_rows
    detail=_opex_component_detail_rows(c,result,36,12)
    assert not any(str(x[-1]).startswith('ERROR:') for x in detail)
    # Missing source and incompatible measure fail closed.
    bad=copy.deepcopy(c);bad['assumptions']['nie_detail']['categories'][0]['linked_components'][0]['factors'][0]['series_id']='missing'
    assert any('missing' in str(e) for e in validate_errors_v2(bad))
    bad=copy.deepcopy(c);bad['assumptions']['nie_detail']['categories'][0]['linked_components'][0]['factors'][0]['series_id']='deposit_pool.pool.availableBalance'
    assert validate_errors_v2(bad)
    # Quarterly calculation periodizes annual rate once, no /12 hardcode.
    c=setup();c['assumptions'].update(periods_per_year=4,n_periods=12)
    out=run_pf_a(c);blank=copy.deepcopy(c);blank['assumptions']['nie_detail']['categories'][0]['linked_components']=[]
    b=run_pf_a(blank)
    assert abs(out['is']['otherOpex'][0]-b['is']['otherOpex'][0]-150)<1e-7
    # An expense-funded acquisition -> activity -> deposit -> same expense link is circular.
    from .source_catalog import balance_link_creates_cycle
    cyc=setup()['assumptions'];cat=cyc['nie_detail']['categories'][0]
    cyc['cac_feeds']={'Acquisition':{'series_id':'auc','customer_count_series_id':'customers','channels':[{'driver_specs':{'spend':{'source':'link','link':{'kind':'operating_expense_category','series_id':cat['series_id']}}}}]}}
    cyc['obs_exposures'][0]['fee_streams']=[{'name':'Acquired activity','quantity_series_id':'acquired-activity','basis':'transaction','driver':{'source':'customer_acquisition_count','ref':'customers'}}]
    cyc['deposit_retention_pools'][0]['balance_spec']={'source':'derived','derived':{'kind':'activity_held','activity':{'source':'link','link':{'kind':'fee_quantity','series_id':'acquired-activity'}}}}
    assert balance_link_creates_cycle(cyc,cat,'deposit_pool.pool.retainedBalance')
    assert balance_link_creates_cycle(cyc,cat,'bank.deposits')
    # Broken links do not prevent catalog discovery needed to repair the configuration.
    cyc['obs_exposures'][0]['fee_streams'][0]['driver']={'source':'fee_stream_quantity','ref':'missing'}
    assert catalog(cyc)
    import json
    from .engine_q_b import run_pf_b
    bcfg=json.load(open('foundry/fixtures/parity/configs/pf_b_base.json'))
    bcfg['assumptions']['nie_detail']=setup()['assumptions']['nie_detail']
    bcfg['assumptions']['nie_detail']['categories'][0]['linked_components'][0]['factors'][0]['series_id']='bank.deposits'
    bresult=run_pf_b(bcfg);blank=copy.deepcopy(bcfg);blank['assumptions']['nie_detail']['categories'][0]['linked_components']=[]
    bbase=run_pf_b(blank)
    for i in range(12):assert abs(bresult['is']['otherOpex'][i]-bbase['is']['otherOpex'][i]-bresult['bs']['deposits'][i]*.0015/4)<1e-6
    print('PASS catalog purity, typed identity, pool/category/total links, annual cadence, opening average, audit units, missing sources')

if __name__=='__main__':main()
