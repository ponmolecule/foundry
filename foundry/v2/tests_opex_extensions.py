import copy, json, sys
from foundry.v2.opex_extensions import (resolve_recognition, resolve_settlement,
                                          normalize_linked_component, linked_component_amount)
from foundry.v2.growth import GrowthContext
from foundry.v2.engine_q_a import run_pf_a
from foundry.v2.validate_q import validate_config_v2, ConfigErrorV2
from foundry.v2.run_q import run_v2

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
    # Generic recognition timing: preserve the economic trajectory total but rebucket NIE.
    econ=[10_000.0]*12
    ann_rec=resolve_recognition(econ, {'mode':'annual','recognition_month':1}, 12,
                                context=GrowthContext(2026,1))
    ck('annual January recognition puts full 120k NIE in January',
       ann_rec[0]==120_000 and sum(ann_rec[1:])==0 and sum(ann_rec)==sum(econ))
    semi_rec=resolve_recognition(econ, {'mode':'semiannual','recognition_months':[3,9]}, 12,
                                 context=GrowthContext(2026,1))
    ck('semiannual Mar/Sep recognition puts 60k in each selected month',
       semi_rec[2]==60_000 and semi_rec[8]==60_000 and sum(semi_rec)==120_000
       and sum(x for i,x in enumerate(semi_rec) if i not in (2,8))==0)
    qrec=resolve_recognition(econ, {'mode':'quarterly','recognition_months':[3,6,9,12]}, 12,
                              context=GrowthContext(2026,1))
    ck('quarterly recognition preserves 30k per quarter at configured month',
       [qrec[i] for i in (2,5,8,11)]==[30_000]*4 and sum(qrec)==120_000)
    ann_q=resolve_recognition([30_000.0]*4, {'mode':'annual','recognition_month':1}, 4,
                              context=GrowthContext(2026,1))
    ck('quarterly engine annual recognition preserves same 120k economics',
       ann_q==[120_000,0,0,0])

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


    # Fee-stream quantity is a first-class observational Opex driver, distinct from fee income.
    c=base_cfg(12); a=c['assumptions']
    a['obs_exposures'].append({
        'name':'Settlement business','call_report_line':'obs','_fee_product':True,
        'fee_streams':[{
            'name':'Settlement fee','quantity_series_id':'fee-qty-settlement','basis':'transaction',
            'driver':{'source':'constant','trajectory':'flat','params':{'base':1_000_000.0}},
            'rate':{'behavior':'flat','params':{'per_unit':0.001}},
            'timing':{'start_period':1},'cost':{'kind':'none','params':{}}
        }]})
    a['nie_detail']['categories']=[{
        'name':'Settlement processing expense',
        'flow_spec':{'trajectory':'flat','value':0,'period':'year'},
        'linked_components':[{'driver':'fee_stream_quantity','series_id':'fee-qty-settlement',
                              'rate_spec':{'source':'entered','trajectory':'flat','value':0.02}}]
    }]
    r=run_pf_a(c)
    settlement_product=next(x for x in r['products'] if x.get('name')=='Settlement business')
    ck('fee-stream quantity link uses pre-pricing throughput, not fee income',
       abs(r['is']['otherOpex'][0]-20_000.0)<1e-6 and abs(settlement_product['fees'][0]-1_000.0)<1e-6,
       (r['is']['otherOpex'][0],settlement_product['fees'][0]))
    ck('fee-stream quantity is surfaced as stable native-period Series',
       r.get('fee_stream_quantities',{}).get('fee-qty-settlement')==[1_000_000.0]*12)
    comp=normalize_linked_component({'driver':'fee_stream_quantity','series_id':'fee-qty-settlement',
                                     'rate_spec':{'trajectory':'flat','value':.02}})
    comp['rates']=[.02]
    ck('linked quantity primitive is observational quantity × dimensionless rate',
       abs(linked_component_amount(comp,0,{'fee_stream_quantities':{'fee-qty-settlement':1_000_000}})-20_000)<1e-9)
    tiny=normalize_linked_component({'driver':'fee_stream_quantity','series_id':'fee-qty-settlement',
                                     'rate_spec':{'source':'entered','trajectory':'flat','value':0.000001}})
    tiny['rates']=[0.000001]
    ck('linked Opex multiplier retains 0.0001 percent as a nonzero 1e-6 decimal rate',
       abs(linked_component_amount(tiny,0,{'fee_stream_quantities':{'fee-qty-settlement':1_000_000}})-1.0)<1e-12)

    vc=copy.deepcopy(c); vc['assumptions']['n_periods']=36
    try:
        validate_config_v2(vc); valid_link=True
    except ConfigErrorV2:
        valid_link=False
    ck('validation accepts existing stable fee-stream quantity Series reference', valid_link)
    badc=copy.deepcopy(vc); badc['assumptions']['nie_detail']['categories'][0]['linked_components'][0]['series_id']='missing-fee-qty'
    bad=False
    try: validate_config_v2(badc)
    except ConfigErrorV2 as e: bad=('does not exist' in str(e))
    ck('validation fails closed on missing fee-stream quantity Series reference', bad)

    public=run_v2(vc)
    qser=(((public.get('fee_stream_quantities') or {}).get('series') or {}).get('fee-qty-settlement') or [])
    ck('public run exposes linked fee-stream quantity in $000s per engine period',
       len(qser)==36 and abs(qser[0]-1000.0)<1e-9 and (public.get('fee_stream_quantities') or {}).get('units')=='$000s / engine period')

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

    # Recognition is the P&L axis; settlement remains independently configurable.
    c=base_cfg(12); a=c['assumptions']
    a['nie_detail']['categories']=[{
        'name':'Annual January expense',
        'flow_spec':{'trajectory':'flat','value':120_000,'period':'year'},
        'recognition':{'mode':'annual','recognition_month':1}
    }]
    r=run_pf_a(c)
    ck('annual January recognition hits NIE only in January',
       abs(r['is']['otherOpex'][0]-120_000)<1e-6 and max(abs(x) for x in r['is']['otherOpex'][1:])<1e-6)
    ck('same-as-recognition settlement creates no timing balance',
       max(r['bs']['prepaidOpex'])<1e-9 and max(r['bs']['accruedOpex'])<1e-9)

    c=base_cfg(12); a=c['assumptions']
    a['nie_detail']['categories']=[{
        'name':'Semiannual expense',
        'flow_spec':{'trajectory':'flat','value':120_000,'period':'year'},
        'recognition':{'mode':'semiannual','recognition_months':[3,9]}
    }]
    r=run_pf_a(c)
    ck('Mar/Sep recognition hits NIE twice yearly without 84-value force-fit',
       abs(r['is']['otherOpex'][2]-60_000)<1e-6 and abs(r['is']['otherOpex'][8]-60_000)<1e-6
       and abs(sum(r['is']['otherOpex'])-120_000)<1e-6)

    c=base_cfg(12); a=c['assumptions']
    a['nie_detail']['categories']=[{
        'name':'Recognize Jan pay Dec',
        'flow_spec':{'trajectory':'flat','value':120_000,'period':'year'},
        'recognition':{'mode':'annual','recognition_month':1},
        'settlement':{'mode':'annual','payment_month':12}
    }]
    r=run_pf_a(c)
    ck('recognition-before-settlement produces accrued Opex liability',
       r['bs']['accruedOpex'][1] > 119_999 and abs(r['bs']['accruedOpex'][12])<1e-6)

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

    c=base_cfg(12); a=c['assumptions']; a['nie_detail']['categories']=[{
        'name':'Bad recognition combo','flow_spec':{'trajectory':'flat','value':120_000,'period':'year'},
        'linked_components':[{'driver':'fee_income','rate_spec':{'trajectory':'flat','value':.1}}],
        'recognition':{'mode':'annual','recognition_month':1}}]
    bad=False
    try: run_pf_a(c)
    except ValueError: bad=True
    ck('custom recognition + linked revenue fails closed', bad)

    print(f'\n{P} passed, {F} failed')
    return 0 if F==0 else 1
if __name__=='__main__': sys.exit(main())
