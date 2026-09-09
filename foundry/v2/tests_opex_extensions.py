import copy, json, sys
from foundry.v2.opex_extensions import resolve_settlement
from foundry.v2.growth import GrowthContext
from foundry.v2.engine_q_a import run_pf_a

P=F=0
def ck(name, ok, detail=''):
    global P,F
    if ok: P+=1; print('  PASS ',name)
    else: F+=1; print('  FAIL ',name,detail)

def base_cfg(ppy=12):
    c=json.load(open('foundry/fixtures/universal_template_bank.json'))
    a=c['assumptions']; a['periods_per_year']=ppy; a['n_periods']=12 if ppy==12 else 4
    a['premises_equipment']=0; a['premises_depreciation_annual']=0; a.pop('fixed_assets',None)
    a['nie_detail']={'categories':[], 'other_gross_up_rate':0, 'fdic_bp_ann':0, 'occ_bp_ann':0,
                     'workforce':{'mode':'roles','roles':[]}}
    return c

def main():
    # Generic settlement math: annual January prepay and Mar/Sep semiannual timing.
    rec=[10_000.0]*12
    ann=resolve_settlement(rec, {'mode':'annual','payment_month':1}, 12,
                           context=GrowthContext(2026,1))
    ck('annual January payment pays full year immediately', ann['cash'][0]==120_000 and sum(ann['cash'][1:])==0)
    ck('annual January prepay runs 110k after Jan to zero after Dec',
       ann['prepaid'][0]==110_000 and abs(ann['prepaid'][-1])<1e-9 and max(ann['accrued'])==0)
    semi=resolve_settlement(rec, {'mode':'semiannual','payment_months':[3,9]}, 12,
                            context=GrowthContext(2026,1))
    ck('semiannual Mar/Sep cash is 60k each', semi['cash'][2]==60_000 and semi['cash'][8]==60_000 and sum(semi['cash'])==120_000)
    ck('semiannual timing accrues before Mar then prepays after Mar',
       semi['accrued'][:2]==[10_000,20_000] and semi['prepaid'][2]==30_000 and semi['prepaid'][5]==0)

    # Linked component: 10% of fee income is additive to the entered base Opex.
    c=base_cfg(12); a=c['assumptions'];
    a['nie_detail']['categories']=[{
        'name':'Vendor platform',
        'flow_spec':{'trajectory':'flat','value':120_000,'period':'year'},
        'linked_components':[{'driver':'fee_income','rate_spec':{'source':'entered','trajectory':'flat','value':0.10}}]
    }]
    r=run_pf_a(c)
    expected0=10_000 + r['is']['fees'][0]*0.10
    ck('linked Opex component = entered base + fee income × rate', abs(r['is']['otherOpex'][0]-expected0)<1e-6,
       (r['is']['otherOpex'][0],expected0))

    # Custom settlement creates BS timing balances but does not alter recognized NIE.
    c=base_cfg(12); a=c['assumptions']
    a['nie_detail']['categories']=[{
        'name':'Annual license',
        'flow_spec':{'trajectory':'flat','value':120_000,'period':'year'},
        'settlement':{'mode':'annual','payment_month':1}
    }]
    r=run_pf_a(c)
    ck('annual prepaid category still recognizes 10k/month', all(abs(x-10_000)<1e-6 for x in r['is']['otherOpex']))
    ck('annual prepaid category surfaces prepaid asset balance', abs(r['bs']['prepaidOpex'][1]-110_000)<1e-6 and abs(r['bs']['prepaidOpex'][12])<1e-6)
    ck('annual prepaid category creates no accrued balance', max(r['bs']['accruedOpex'])<1e-9)

    # OCC: annual bp input becomes a semiannual assessment fixed off the half-year measurement base.
    c=base_cfg(4); a=c['assumptions']; a['nie_detail']['occ_bp_ann']=20.0
    r=run_pf_a(c)
    opening_assets=r['bs']['totalAssets'][0]
    half1=opening_assets*20/10000/2
    ck('OCC Q1/Q2 recognition shares one Dec-31-based semiannual assessment',
       abs(r['is']['otherOpex'][0]-half1/2)<1e-5 and abs(r['is']['otherOpex'][1]-half1/2)<1e-5,
       (r['is']['otherOpex'][:2], half1/2))
    ck('OCC March payment creates Q1 prepaid then clears by Q2',
       abs(r['bs']['prepaidOpex'][1]-half1/2)<1e-5 and abs(r['bs']['prepaidOpex'][2])<1e-5)
    ck('OCC H2 resets from June measurement base',
       abs(r['is']['otherOpex'][2] - (r['bs']['totalAssets'][2]*20/10000/2)/2)<1e-5)

    # Fail closed: custom settlement + endogenous linked revenue component.
    c=base_cfg(12); a=c['assumptions']; a['nie_detail']['categories']=[{
        'name':'Bad combo','flow_spec':{'trajectory':'flat','value':120_000,'period':'year'},
        'linked_components':[{'driver':'fee_income','rate_spec':{'trajectory':'flat','value':.1}}],
        'settlement':{'mode':'annual','payment_month':1}}]
    bad=False
    try: run_pf_a(c)
    except ValueError: bad=True
    ck('custom settlement + linked revenue fails closed', bad)

    print(f'\n{P} passed, {F} failed')
    return 0 if F==0 else 1
if __name__=='__main__': sys.exit(main())
