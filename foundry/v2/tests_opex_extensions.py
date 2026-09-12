import copy, json, sys
from foundry.v2.opex_extensions import (resolve_recognition, resolve_settlement,
                                          normalize_linked_component, linked_component_amount, apply_piecewise_schedule,
                                          fee_stream_balance_quantity_catalog, recognition_spec_for_category)
from foundry.v2.income_modules import nie_category_series, fee_stream_q
from foundry.v2.growth import GrowthContext
from foundry.v2.engine_q_a import run_pf_a
from foundry.v2.engine_q_b import run_pf_b
from foundry.v2.validate_q import validate_config_v2, ConfigErrorV2
from foundry.v2.run_q import run_v2
from foundry.v2.audit_workbook import calculation_audit_workbook

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
    # Generic recognition timing: first occurrence is literal and anchors recurrence.
    econ=[10_000.0]*12
    ann_rec=resolve_recognition(econ, {'mode':'annual','first_period':1}, 12,
                                context=GrowthContext(2026,1))
    ck('annual recognition at M1 puts full 120k NIE in M1',
       ann_rec[0]==120_000 and sum(ann_rec[1:])==0 and sum(ann_rec)==sum(econ))
    semi_rec=resolve_recognition(econ, {'mode':'semiannual','first_period':3}, 12,
                                 context=GrowthContext(2026,1))
    ck('semiannual first recognition M3 anchors M3/M9 and nothing hits before M3',
       semi_rec[:2]==[0,0] and semi_rec[2]==60_000 and semi_rec[8]==40_000
       and sum(semi_rec)==100_000)
    qrec=resolve_recognition(econ, {'mode':'quarterly','first_period':3}, 12,
                              context=GrowthContext(2026,1))
    ck('quarterly first recognition M3 repeats every three periods from M3',
       [qrec[i] for i in (2,5,8,11)]==[30_000,30_000,30_000,10_000]
       and sum(qrec[:2])==0 and sum(qrec)==100_000)
    monthly_late=resolve_recognition(econ, {'mode':'monthly','first_period':4}, 12)
    ck('monthly timing can also start literally after M1',
       monthly_late[:3]==[0,0,0] and monthly_late[3:]==[10_000.0]*9)
    ann_q=resolve_recognition([30_000.0]*4, {'mode':'annual','first_period':1}, 4,
                              context=GrowthContext(2026,1))
    ck('quarterly engine annual recognition preserves same 120k economics from Q1',
       ann_q==[120_000,0,0,0])
    ctx_shift=resolve_recognition(econ, {'mode':'annual','first_period':3}, 12,
                                  context=GrowthContext(2031,8))
    ctx_base=resolve_recognition(econ, {'mode':'annual','first_period':3}, 12,
                                 context=GrowthContext(2026,1))
    ck('ordinal recognition is invariant to client-calendar start month/year', ctx_shift==ctx_base)
    long_econ=[10_000.0]*60
    late=resolve_recognition(long_econ, {'mode':'annual','first_period':35}, 12,
                             context=GrowthContext(2026,1))
    ck('Annual + first recognition M35 means M35/M47/M59 with nothing before M35',
       sum(late[:34])==0 and late[34]==120_000.0 and late[46]==120_000.0
       and late[58]==20_000.0 and sum(late[35:46])==0)

    # r60 compatibility: remove the short-lived separate commencement axis without losing intent.
    legacy_r60={'name':'Legacy delayed monthly expense',
                'flow_spec':{'trajectory':'flat','value':120_000.0,'period':'year','start_period':35},
                'recognition':{'mode':'trajectory'}}
    migrated=recognition_spec_for_category(legacy_r60,12)
    ck('r60 Expense begins M35 migrates to Monthly first recognition M35',
       migrated=={'mode':'monthly','first_period':35})
    legacy_custom={'name':'Legacy annual expense',
                   'flow_spec':{'trajectory':'flat','value':120_000.0,'period':'year','start_period':25},
                   'recognition':{'mode':'annual','first_period':35}}
    migrated_custom=recognition_spec_for_category(legacy_custom,12)
    ck('r60 start_period cannot override an explicitly authored first recognition',
       migrated_custom=={'mode':'annual','first_period':35})
    legacy_econ=nie_category_series(legacy_custom,48,12,growth_context=GrowthContext(2026,1))
    ck('r61 economic trajectory ignores removed r60 start_period axis',
       legacy_econ[:12]==[10_000.0]*12)
    legacy_rec=resolve_recognition(legacy_econ,migrated_custom,12)
    ck('legacy custom annual timing now follows the simple M35/M47 contract',
       sum(legacy_rec[:34])==0 and legacy_rec[34]==120_000.0 and legacy_rec[46]==20_000.0)

    # Generic settlement math on model-period ordinals.
    rec=[10_000.0]*12
    ann=resolve_settlement(rec, {'mode':'annual','first_payment_period':1}, 12,
                           context=GrowthContext(2026,1))
    ck('annual ordinal payment at M1 pays full year immediately', ann['cash'][0]==120_000 and sum(ann['cash'][1:])==0)
    ck('annual M1 prepay runs 110k after M1 to zero after M12',
       ann['prepaid'][0]==110_000 and abs(ann['prepaid'][-1])<1e-9 and max(ann['accrued'])==0)
    semi=resolve_settlement(rec, {'mode':'semiannual','first_payment_period':3}, 12,
                            context=GrowthContext(2026,1))
    ck('semiannual ordinal cash at M3/M9 is 60k each', semi['cash'][2]==60_000 and semi['cash'][8]==60_000 and sum(semi['cash'])==120_000)
    ck('semiannual timing accrues before M3 then prepays after M3',
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

    # CAC/AUC is a stock-linked Opex driver. Annual multipliers accrue on the canonical
    # monthly period-end AUC path, then aggregate to native presentation cadence.
    def fraud_cfg(ppy):
        fc=base_cfg(ppy); fa=fc['assumptions']
        fa['cac_feeds']={'fraud_base':{
            'series_id':'cac-auc-fraud','owner_module':'customer_acquisition',
            'beginning_auc':0,'beginning_customers':0,'attrition_rate':0,'intra_year_shape':'linear',
            'channels':[{'name':'Organic','method':'pool_conversion',
                         'params':{'pool':12,'pool_growth':0,'conversion_rate':1.0,'conversion_growth':0},
                         'avg_auc_per_customer':1_000_000,'avg_auc_growth':0}]}}
        fa['nie_detail']['categories']=[{
            'name':'Provision for Fraud & Operational Losses','series_id':'opex-fraud',
            'flow_spec':{'trajectory':'flat','value':0,'period':'year'},
            'linked_components':[{'driver':'customer_acquisition_auc','series_id':'cac-auc-fraud',
                                  'rate_period':'year',
                                  'rate_spec':{'source':'entered','trajectory':'flat','value':0.0001}}]}]
        return fc

    fm=fraud_cfg(12); rm=run_pf_a(fm)
    fq=fraud_cfg(4); rq=run_pf_a(fq)
    ck('AUC-linked annual multiplier accrues against monthly period-end AUC',
       abs(rm['is']['otherOpex'][0]-(1_000_000*.0001/12))<1e-6 and
       abs(rm['is']['otherOpex'][11]-(12_000_000*.0001/12))<1e-6)
    ck('quarterly AUC-linked Opex sums canonical monthly accruals, not Q-end AUC proxy',
       abs(rq['is']['otherOpex'][0]-((1_000_000+2_000_000+3_000_000)*.0001/12))<1e-6)
    ck('AUC-linked fraud expense is cadence-equivalent by quarter',
       all(abs(rq['is']['otherOpex'][q]-sum(rm['is']['otherOpex'][q*3:(q+1)*3]))<1e-6 for q in range(4)))
    ck('AUC-linked fraud expense preserves annual total across monthly/quarterly models',
       abs(sum(rm['is']['otherOpex'])-sum(rq['is']['otherOpex']))<1e-6)

    # AUC measure normalization: legacy r64/r65 configs omitted a measure and meant monthly EOP.
    legacy_norm = normalize_linked_component({'driver':'customer_acquisition_auc','series_id':'cac-auc-fraud',
                                               'rate_period':'year',
                                               'rate_spec':{'source':'entered','trajectory':'flat','value':0.0001}})
    ck('legacy AUC-linked Opex with no measure migrates as Period end', legacy_norm.get('measure')=='period_end')

    # Period-average Opex uses the same canonical monthly balance contract as Reg W cost pools.
    # Beginning 0.9m and a linear ramp to 3.3m gives M1/M2/M3 EOP 1.1/1.3/1.5m and
    # monthly average exposure 1.0/1.2/1.4m.
    def avg_auc_opex_cfg(ppy):
        c=base_cfg(ppy); a=c['assumptions']
        a['cac_feeds']={'avg_base':{
            'series_id':'cac-auc-avg','owner_module':'customer_acquisition',
            'beginning_auc':900_000.0,'beginning_customers':0,'attrition_rate':0,'intra_year_shape':'linear',
            'channels':[{'name':'Explicit adds','method':'explicit',
                         'params':{'new_customers_by_year':[1.0],'spend':0.0},
                         'avg_auc_per_customer':2_400_000.0}]}}
        a['nie_detail']['categories']=[{
            'name':'Average-AUC linked expense','series_id':'opex-avg-auc',
            'flow_spec':{'trajectory':'flat','value':0,'period':'year'},
            'linked_components':[{'driver':'customer_acquisition_auc','series_id':'cac-auc-avg',
                                  'measure':'period_average','rate_period':'year',
                                  'rate_spec':{'source':'entered','trajectory':'flat','value':0.0001}}]}]
        return c

    am=avg_auc_opex_cfg(12); arm=run_pf_a(am)
    aq=avg_auc_opex_cfg(4); arq=run_pf_a(aq)
    ck('Period-average AUC-linked Opex uses true opening balance in M1',
       abs(arm['is']['otherOpex'][0]-(1_000_000*.0001/12))<1e-6)
    ck('quarterly Period-average AUC-linked Opex sums monthly average-AUC accruals',
       abs(arq['is']['otherOpex'][0]-((1_000_000+1_200_000+1_400_000)*.0001/12))<1e-6)
    ck('Period-average AUC-linked Opex is cadence-equivalent by quarter',
       all(abs(arq['is']['otherOpex'][q]-sum(arm['is']['otherOpex'][q*3:(q+1)*3]))<1e-6 for q in range(4)))

    # Profile B shares the same Opex balance-measure contract even though its product engine is separate.
    pb=json.load(open('foundry/fixtures/parity/configs/pf_b_base.json'))
    pba=pb['assumptions']; pba['cac_feeds']=copy.deepcopy(aq['assumptions']['cac_feeds'])
    pba['nie_detail']=copy.deepcopy(aq['assumptions']['nie_detail'])
    pbr=run_v2(pb)
    ck('Profile B Opex honors the same canonical Period-average AUC contract',
       abs(pbr['financials']['is']['otherOpex'][0]-0.03)<1e-9)

    bad_measure=avg_auc_opex_cfg(12)
    bad_measure['assumptions']['nie_detail']['categories'][0]['linked_components'][0]['measure']='daily_average'
    measure_failed=False
    try: validate_config_v2(bad_measure)
    except ConfigErrorV2 as e: measure_failed=('period_end or period_average' in str(e))
    ck('AUC-linked Opex fails closed on unsupported balance measure', measure_failed)

    html=open('web/console_v2.html').read()
    ck('Opex UI exposes Period average / Period end selector and preserves EOP migration default',
       'nieCatLinkedMeasure' in html and '>Period average</option>' in html and '>Period end</option>' in html
       and 'lc.measure=lc.measure||"period_end"' in html)
    vfm=copy.deepcopy(fm); vfm['assumptions']['n_periods']=36
    try:
        validate_config_v2(vfm); auc_valid=True
    except ConfigErrorV2:
        auc_valid=False
    ck('validation accepts existing CAC AUC Series reference', auc_valid)
    bad_auc=copy.deepcopy(vfm); bad_auc['assumptions']['nie_detail']['categories'][0]['linked_components'][0]['series_id']='missing-auc'
    bad=False
    try: validate_config_v2(bad_auc)
    except ConfigErrorV2 as e: bad=('does not exist' in str(e))
    ck('validation fails closed on missing CAC AUC Series reference', bad)

    cyc=fraud_cfg(12); cyc['assumptions']['n_periods']=36
    feed=cyc['assumptions']['cac_feeds']['fraud_base']
    feed['channels']=[{'name':'Paid acquisition','method':'spend_cac','params':{},'avg_auc_per_customer':1_000_000,
                       'driver_specs':{
                           'spend':{'source':'link','series_id':'cac-spend','owner_module':'customer_acquisition',
                                    'link':{'kind':'operating_expense_category','series_id':'opex-fraud','aggregation':'sum'}},
                           'cac':{'source':'entered','trajectory':'flat','value':1000},
                           'avg_auc_per_customer':{'source':'entered','trajectory':'flat','value':1_000_000}}}]
    cyc_bad=False
    try: validate_config_v2(cyc)
    except ConfigErrorV2 as e: cyc_bad=('circular dependency' in str(e))
    ck('AUC-linked Opex fails closed when the same category drives that CAC feed', cyc_bad)

    # Custom settlement creates BS timing balances but does not alter recognized NIE.
    c=base_cfg(12); a=c['assumptions']
    a['nie_detail']['categories']=[{
        'name':'Annual license',
        'flow_spec':{'trajectory':'flat','value':120_000,'period':'year'},
        'settlement':{'mode':'annual','first_payment_period':1}
    }]
    r=run_pf_a(c)
    ck('annual prepaid category still recognizes 10k/month', all(abs(x-10_000)<1e-6 for x in r['is']['otherOpex']))
    ck('annual prepaid category surfaces prepaid asset balance', abs(r['bs']['prepaidOpex'][1]-110_000)<1e-6 and abs(r['bs']['prepaidOpex'][12])<1e-6)
    ck('annual prepaid category creates no accrued balance', max(r['bs']['accruedOpex'])<1e-9)

    # Recognition is the P&L axis; settlement remains independently configurable.
    c=base_cfg(12); a=c['assumptions']
    a['nie_detail']['categories']=[{
        'name':'Annual ordinal expense',
        'flow_spec':{'trajectory':'flat','value':120_000,'period':'year'},
        'recognition':{'mode':'annual','first_period':1}
    }]
    r=run_pf_a(c)
    ck('annual M1 recognition hits NIE only in M1',
       abs(r['is']['otherOpex'][0]-120_000)<1e-6 and max(abs(x) for x in r['is']['otherOpex'][1:])<1e-6)
    ck('same-as-recognition settlement creates no timing balance',
       max(r['bs']['prepaidOpex'])<1e-9 and max(r['bs']['accruedOpex'])<1e-9)

    c=base_cfg(12); a=c['assumptions']; a['n_periods']=14
    a['nie_detail']['categories']=[{
        'name':'Semiannual expense',
        'flow_spec':{'trajectory':'flat','value':120_000,'period':'year'},
        'recognition':{'mode':'semiannual','first_period':3}
    }]
    r=run_pf_a(c)
    ck('M3/M9 recognition hits NIE twice yearly without 84-value force-fit',
       abs(r['is']['otherOpex'][2]-60_000)<1e-6 and abs(r['is']['otherOpex'][8]-60_000)<1e-6
       and abs(sum(r['is']['otherOpex'])-120_000)<1e-6)

    c=base_cfg(12); a=c['assumptions']
    a['nie_detail']['categories']=[{
        'name':'Recognize M1 pay M12',
        'flow_spec':{'trajectory':'flat','value':120_000,'period':'year'},
        'recognition':{'mode':'annual','first_period':1},
        'settlement':{'mode':'annual','first_payment_period':12}
    }]
    r=run_pf_a(c)
    ck('recognition-before-settlement produces accrued Opex liability',
       r['bs']['accruedOpex'][1] > 119_999 and abs(r['bs']['accruedOpex'][12])<1e-6)

    # r78 OCC contract: modern Detailed Opex is inert unless the simplified shortcut is
    # explicitly enabled. Pre-r78 saved models that persisted occ_bp_ann remain active.
    c0=base_cfg(4); a0=c0['assumptions']; a0['nie_detail'].pop('occ_bp_ann',None); a0['nie_detail'].pop('occ_simplified_enabled',None)
    r0=run_pf_a(c0)
    c0z=base_cfg(4); r0z=run_pf_a(c0z)
    ck('modern Detailed Opex with no OCC config posts no simplified OCC expense',
       all(abs(x-y)<1e-9 for x,y in zip(r0['is']['otherOpex'],r0z['is']['otherOpex']))
       and max(abs(x) for x in r0['bs']['prepaidOpex'])<1e-9
       and max(abs(x) for x in r0['bs']['accruedOpex'])<1e-9)
    c0d=base_cfg(4); a0d=c0d['assumptions']; a0d['nie_detail']['occ_bp_ann']=20.0; a0d['nie_detail']['occ_simplified_enabled']=False
    r0d=run_pf_a(c0d)
    ck('explicitly disabled simplified OCC ignores a retained legacy rate',
       all(abs(x-y)<1e-9 for x,y in zip(r0d['is']['otherOpex'],r0z['is']['otherOpex'])))
    cb=json.load(open('foundry/fixtures/parity/configs/pf_b_base.json')); ab=cb['assumptions']
    ab['nie_detail']={'categories':[],'other_gross_up_rate':0,'fdic_bp_ann':0,
                      'workforce':{'mode':'roles','roles':[]}}
    rb0=run_pf_b(cb)
    cbz=copy.deepcopy(cb); cbz['assumptions']['nie_detail']['occ_bp_ann']=0.0; rb0z=run_pf_b(cbz)
    cbd=copy.deepcopy(cb); cbd['assumptions']['nie_detail']['occ_bp_ann']=20.0; cbd['assumptions']['nie_detail']['occ_simplified_enabled']=False; rb0d=run_pf_b(cbd)
    ck('Profile B also keeps simplified OCC off when absent or explicitly disabled',
       all(abs(x-y)<1e-9 for x,y in zip(rb0['is']['otherOpex'],rb0z['is']['otherOpex']))
       and all(abs(x-y)<1e-9 for x,y in zip(rb0d['is']['otherOpex'],rb0z['is']['otherOpex'])))

    # OCC: annual bp input becomes a semiannual assessment fixed off the half-year measurement base.
    # No enable flag intentionally emulates a pre-r78 saved model and must stay backward-compatible.
    c=base_cfg(4); a=c['assumptions']; a['nie_detail']['occ_bp_ann']=20.0
    r=run_pf_a(c)
    opening_assets=r['bs']['totalAssets'][0]
    half1=opening_assets*20/10000/2
    ck('OCC Q1/Q2 recognition shares one ordinal semiannual assessment',
       abs(r['is']['otherOpex'][0]-half1/2)<1e-5 and abs(r['is']['otherOpex'][1]-half1/2)<1e-5,
       (r['is']['otherOpex'][:2], half1/2))
    ck('OCC default ordinal payment at Q1 creates prepaid then clears by Q2',
       abs(r['bs']['prepaidOpex'][1]-half1/2)<1e-5 and abs(r['bs']['prepaidOpex'][2])<1e-5)
    ck('OCC second ordinal half resets from prior half-end measurement base',
       abs(r['is']['otherOpex'][2] - (r['bs']['totalAssets'][2]*20/10000/2)/2)<1e-5)
    c2=base_cfg(4); a2=c2['assumptions']; a2['nie_detail']['occ_bp_ann']=20.0; a2['nie_detail']['occ_payment_first_period']=2
    r2=run_pf_a(c2)
    ck('OCC first payment can be translated to Q2 then repeats every two quarters',
       r2['bs']['accruedOpex'][1] > 0 and abs(r2['bs']['accruedOpex'][2])<1e-5
       and r2['bs']['accruedOpex'][3] > 0 and abs(r2['bs']['accruedOpex'][4])<1e-5)

    # A cost pool can be consumed by Operating Expense as the final posting direction.
    # This is the expense-side twin of Fee Product cost recovery: the pool stays non-posting,
    # while the recovered/marked-up charge posts once to NIE.
    def platform_services_cfg(ppy):
        pc=base_cfg(ppy); pa=pc['assumptions']
        pa['capital_raises']=[]
        pa['cac_feeds']={'platform':{
            'series_id':'cac-auc-platform','owner_module':'customer_acquisition',
            'beginning_auc':0.0,'beginning_customers':0.0,'attrition_rate':0.0,
            'intra_year_shape':'linear','channels':[{
                'name':'Explicit adds','method':'explicit',
                'params':{'new_customers_by_year':[1.0],'spend':0.0},
                'avg_auc_per_customer':1_000_000_000.0}]}}
        pa['cost_pools']=[{
            'series_id':'pool-platform','owner_module':'cost_pool','name':'Platform services eligible cost',
            'components':[
                {'kind':'assumption_cost_base','series_id':'cost-base-fixed','name':'Fixed service cost',
                 'allocation_pct':1.0,
                 'flow_spec':{'trajectory':'growth','value':300_000.0,'period':'year',
                              'base_position':'period1','growth_spec':{'rate':.03,'period':'year',
                                                                     'method':'step','anchor':'model_year'}}},
                {'kind':'balance_derived_cost','series_id':'cost-base-variable','name':'Average-AUC variable cost',
                 'allocation_pct':1.0,'source_kind':'managed_notional','source_series_id':'cac-auc-platform',
                 'measure':'period_average','rate_period':'year',
                 'rate_spec':{'source':'entered','trajectory':'flat','value':.00006}},
            ]}]
        pa['nie_detail']['categories']=[{
            'series_id':'opex-platform','owner_module':'operating_expense',
            'name':'Intercompany - Platform Services',
            'flow_spec':{'trajectory':'flat','value':0.0,'period':'year'},
            'linked_components':[{
                'driver':'cost_pool_charge','ref':'pool-platform','recovery_pct':1.0,
                'markup':{'value':.05,'period':'year','trajectory':'flat','resolution':'step'}}],
        }]
        return pc

    pm=platform_services_cfg(12)
    prm=run_pf_a(pm)
    expected=[26_468.75,26_906.25,27_343.75,27_781.25,28_218.75,28_656.25,
              29_093.75,29_531.25,29_968.75,30_406.25,30_843.75,31_281.25]
    ck('cost-pool Opex posts the source Platform Services monthly charge exactly once to NIE',
       all(abs(x-y)<1e-6 for x,y in zip(prm['is']['otherOpex'][:12],expected))
       and abs(sum(prm['is']['otherOpex'][:12])-346_500.0)<1e-6,
       prm['is']['otherOpex'][:12])
    additive=platform_services_cfg(12)
    additive['assumptions']['nie_detail']['categories'][0]['flow_spec']['value']=12_000.0
    pra=run_pf_a(additive)
    ck('typed cost-pool charge composes additively with the ordinary entered Opex base',
       abs(pra['is']['otherOpex'][0]-27_468.75)<1e-6
       and abs(sum(pra['is']['otherOpex'][:12])-358_500.0)<1e-6)

    pq=platform_services_cfg(4)
    prq=run_pf_a(pq)
    expected_q=[80_718.75,84_656.25,88_593.75,92_531.25]
    ck('cost-pool Opex preserves exact monthly economics in quarterly presentation',
       all(abs(x-y)<1e-6 for x,y in zip(prq['is']['otherOpex'][:4],expected_q))
       and abs(sum(prq['is']['otherOpex'][:4])-346_500.0)<1e-6)
    pf_b=json.load(open('foundry/fixtures/parity/configs/pf_b_base.json'))
    pba=pf_b['assumptions']; pba['n_periods']=12; pba['periods_per_year']=4; pba['capital_raises']=[]
    for key in ('cac_feeds','cost_pools','nie_detail'):
        pba[key]=copy.deepcopy(pq['assumptions'][key])
    pba['premises_equipment']=0; pba['premises_depreciation_annual']=0; pba.pop('fixed_assets',None)
    prb=run_pf_b(pf_b)
    ck('Profile B can consume the same shared cost pool as Operating Expense',
       all(abs(x-y)<1e-6 for x,y in zip(prb['is']['otherOpex'][:4],expected_q))
       and abs(sum(prb['is']['otherOpex'][:4])-346_500.0)<1e-6)
    try:
        validate_config_v2(pm); pool_opex_valid=True
    except ConfigErrorV2 as e:
        print('cost-pool Opex validation error',e); pool_opex_valid=False
    ck('validation accepts Operating Expense as a downstream cost-pool consumer', pool_opex_valid)

    missing_pool=copy.deepcopy(pm)
    missing_pool['assumptions']['nie_detail']['categories'][0]['linked_components'][0]['ref']='missing-pool'
    bad=False
    try: validate_config_v2(missing_pool)
    except ConfigErrorV2 as e: bad='missing-pool' in str(e)
    ck('cost-pool Opex fails closed on a missing pool reference', bad)

    circular=copy.deepcopy(pm)
    circular['assumptions']['cost_pools'][0]['components'].insert(0,{
        'kind':'operating_expense_category','series_id':'opex-platform','allocation_pct':1.0})
    bad=False
    try: validate_config_v2(circular)
    except ConfigErrorV2 as e: bad=('circular dependency' in str(e) or 'cost-pool charge' in str(e))
    ck('cost-pool Opex fails closed when the pool includes its own downstream Opex category', bad)

    auc_loop=copy.deepcopy(pm)
    auc_loop['assumptions']['cac_feeds']['platform']['channels']=[{
        'name':'Paid acquisition','method':'spend_cac','params':{},'avg_auc_per_customer':1_000_000_000.0,
        'driver_specs':{
            'spend':{'source':'link','series_id':'cac-spend-platform','owner_module':'customer_acquisition',
                     'link':{'kind':'operating_expense_category','series_id':'opex-platform','aggregation':'sum'}},
            'cac':{'source':'entered','trajectory':'flat','value':1_000.0},
            'avg_auc_per_customer':{'source':'entered','trajectory':'flat','value':1_000_000_000.0}}}]
    bad=False
    try: validate_config_v2(auc_loop)
    except ConfigErrorV2 as e: bad=('cost-pool-calculated Operating Expense category' in str(e) or 'circular dependency' in str(e) or 'cost-pool charge' in str(e))
    ck('cost-pool Opex fails closed on Opex → CAC/AUC → cost-pool → same Opex loop', bad)

    # r67 compatibility: old exclusive calculation.kind configs remain stable on load/run,
    # but r68 authoring no longer creates this shape.
    legacy_r67=platform_services_cfg(12)
    lcat=legacy_r67['assumptions']['nie_detail']['categories'][0]
    lcat.pop('linked_components',None)
    lcat['flow_spec']={'trajectory':'flat','value':999_999.0,'period':'year'}
    lcat['calculation']={'kind':'cost_pool','ref':'pool-platform','recovery_pct':1.0,
                         'markup':{'value':.05,'period':'year','trajectory':'flat','resolution':'step'}}
    prl=run_pf_a(legacy_r67)
    ck('legacy r67 exclusive cost-pool Opex remains backward-compatible without reactivating dormant entered base',
       abs(prl['is']['otherOpex'][0]-26_468.75)<1e-6
       and abs(sum(prl['is']['otherOpex'][:12])-346_500.0)<1e-6)

    # Generic tiered / banded linked Opex: literal base + marginal-rate schedules over
    # composable upstream balance terms.  These fixtures intentionally mirror a regulator-style
    # schedule without introducing any regulator name or engagement label into the runtime.
    general_bands=[
        {'lower_bound':0.0,'upper_bound':2_000_000.0,'base_amount':2_086.0,'marginal_rate':0.0},
        {'lower_bound':2_000_000.0,'upper_bound':20_000_000.0,'base_amount':2_086.0,'marginal_rate':0.000082447},
        {'lower_bound':20_000_000.0,'upper_bound':100_000_000.0,'base_amount':3_570.0,'marginal_rate':0.000065956},
        {'lower_bound':100_000_000.0,'upper_bound':200_000_000.0,'base_amount':8_846.0,'marginal_rate':0.000042869},
        {'lower_bound':200_000_000.0,'upper_bound':1_000_000_000.0,'base_amount':13_132.0,'marginal_rate':0.000041111},
        {'lower_bound':1_000_000_000.0,'upper_bound':None,'base_amount':46_020.0,'marginal_rate':0.000039571},
    ]
    trust_bands=[
        {'lower_bound':0.0,'upper_bound':1_000_000_000.0,'base_amount':15_961.0,'marginal_rate':0.0},
        {'lower_bound':1_000_000_000.0,'upper_bound':10_000_000_000.0,'base_amount':15_961.0,'marginal_rate':0.000003179},
        {'lower_bound':10_000_000_000.0,'upper_bound':None,'base_amount':44_572.0,'marginal_rate':0.000000529},
    ]
    ck('piecewise schedule preserves literal source breakpoint bases instead of smoothing them',
       abs(apply_piecewise_schedule(20_000_000.0,general_bands)-3_570.046)<1e-9
       and abs(apply_piecewise_schedule(20_000_001.0,general_bands)-3_570.000065956)<1e-9)

    gen_comp=normalize_linked_component({
        'driver':'piecewise_linked','name':'General tiered assessment',
        'terms':[{'source':'bank_total_assets','weight':1.0}],
        'bands':general_bands,'timing':{'mode':'semiannual','first_period':9},
        'observation_lag':{'value':1,'period':'month'}})
    trust_comp=normalize_linked_component({
        'driver':'piecewise_linked','name':'Composite balance assessment',
        'terms':[{'source':'customer_acquisition_auc','series_id':'auc-tiered','measure':'period_end','weight':1.0},
                 {'source':'fee_stream_balance_quantity','series_id':'reserve-tiered','weight':1.0}],
        'bands':trust_bands,'timing':{'mode':'semiannual','first_period':9},
        'observation_lag':{'value':1,'period':'month'}})
    tier_metrics={
        'periods_per_year':12,
        'bank_total_assets_end_by_period':[150_000_000.0,160_000_000.0,170_000_000.0,180_000_000.0,
                                           190_000_000.0,200_000_000.0,210_000_000.0,220_000_000.0,250_000_000.0],
        'customer_acquisition_auc_beginning':{'auc-tiered':100_000_000.0},
        'customer_acquisition_auc_monthly':{'auc-tiered':[200_000_000.0,300_000_000.0,400_000_000.0,500_000_000.0,
                                                          600_000_000.0,700_000_000.0,800_000_000.0,900_000_000.0]},
        'fee_stream_quantity_history':{'reserve-tiered':[25_000_000.0,50_000_000.0,75_000_000.0,100_000_000.0,
                                                         125_000_000.0,150_000_000.0,175_000_000.0,200_000_000.0]},
    }
    expected_general=13_132.0+0.000041111*(250_000_000.0-200_000_000.0)
    expected_trust=15_961.0+0.000003179*((900_000_000.0+200_000_000.0)-1_000_000_000.0)
    ck('piecewise component uses the prior-month Total Assets observation on the configured event',
       abs(linked_component_amount(gen_comp,8,tier_metrics)-expected_general)<1e-9
       and linked_component_amount(gen_comp,7,tier_metrics)==0.0)
    ck('piecewise composite driver sums independent upstream balance terms before applying bands',
       abs(linked_component_amount(trust_comp,8,tier_metrics)-expected_trust)<1e-9)
    prestart_metrics=copy.deepcopy(tier_metrics)
    prestart_metrics['fee_stream_quantity_history']={}
    prestart_metrics['fee_stream_quantity_known_ids']={'reserve-tiered'}
    expected_prestart=15_961.0  # 900MM AUC + zero inactive reserve quantity remains below the first trust breakpoint.
    ck('validated Balance Fee quantity Series resolves to zero before stream activation instead of becoming unavailable',
       abs(linked_component_amount(trust_comp,8,prestart_metrics)-expected_prestart)<1e-9)
    ck('two generic tiered components reproduce the combined source-formula shape without regulator-specific runtime logic',
       abs((linked_component_amount(gen_comp,8,tier_metrics)+linked_component_amount(trust_comp,8,tier_metrics))
           -(expected_general+expected_trust))<1e-9)
    tier_metrics_15=copy.deepcopy(tier_metrics)
    tier_metrics_15['bank_total_assets_end_by_period'] += [260_000_000.0,270_000_000.0,280_000_000.0,290_000_000.0,300_000_000.0,310_000_000.0]
    ck('semiannual tiered timing recurs six model months after the first event',
       linked_component_amount(gen_comp,14,tier_metrics_15)>0.0
       and linked_component_amount(gen_comp,13,tier_metrics_15)==0.0)

    reserve_stream={
        'basis':'balance','name':'Reserve balance','quantity_series_id':'reserve-tiered',
        'driver':{'source':'managed_notional','trajectory':'derived','params':{'stock_multiplier':{'kind':'pct','value':0.30,'trajectory':'flat'}}},
        'rate':{'behavior':'flat','params':{'rate_path':{'value':0.0012,'trajectory':'flat'}}},
        'timing':{'start_period':1},'cost':{'kind':'none','params':{}}}
    capctx={'managed_notional':1_000_000_000.0,'capture_stream_qty':{}}
    fee_stream_q(reserve_stream,1,capctx,ppy=12)
    ck('Balance Fee stream publishes its modeled driver balance as a stable observational quantity',
       capctx['capture_stream_qty'].get('reserve-tiered')==[300_000_000.0])
    cat_assumptions={'obs_exposures':[{'name':'Trust product','fee_streams':[reserve_stream]}]}
    ck('tiered Opex source catalog exposes Balance Fee stream quantities by stable Series ID',
       fee_stream_balance_quantity_catalog(cat_assumptions)[0]['series_id']=='reserve-tiered')

    tier_cfg=base_cfg(12); ta=tier_cfg['assumptions']; ta['n_periods']=12; ta['capital_raises']=[]
    ta['nie_detail']['categories']=[{
        'series_id':'opex-tiered','owner_module':'operating_expense','name':'Tiered assessment',
        'flow_spec':{'trajectory':'flat','value':0.0,'period':'year'},
        'linked_components':[{
            'driver':'piecewise_linked','component_id':'tiered-assets','name':'Asset-based band table',
            'terms':[{'source':'bank_total_assets','weight':1.0}],
            'bands':copy.deepcopy(general_bands),
            'timing':{'mode':'semiannual','first_period':9},
            'observation_lag':{'value':1,'period':'month'}}]}]
    try:
        validate_config_v2(tier_cfg); tier_valid=True
    except ConfigErrorV2 as e:
        print('tiered validation error',e); tier_valid=False
    ck('validation accepts generic tiered/banded Opex under Advanced',tier_valid)
    tier_run=run_pf_a(tier_cfg)
    tier_expected=apply_piecewise_schedule(tier_run['bs']['totalAssets'][8],general_bands)
    ck('full engine posts the tiered component once on its configured event using prior-period assets',
       abs(tier_run['is']['otherOpex'][8]-tier_expected)<1e-6
       and all(abs(tier_run['is']['otherOpex'][k])<1e-9 for k in range(8)))

    tier_audit=calculation_audit_workbook(tier_cfg, run_v2(tier_cfg))
    ows=tier_audit['Operating Expense']
    tier_audit_row=None
    for r in range(1,ows.max_row+1):
        if ows.cell(r,3).value=='tiered-assets':
            tier_audit_row=r; break
    audit_vals=[] if tier_audit_row is None else [ows.cell(tier_audit_row,c).value for c in range(5,17)]
    ck('calculation audit workbook exposes the tiered Opex component at native cadence for source-model reconciliation',
       tier_audit_row is not None
       and all(abs(float(audit_vals[k] or 0.0))<1e-9 for k in range(8))
       and abs(float(audit_vals[8] or 0.0)-(tier_expected/1000.0))<1e-6)

    dormant_rec=copy.deepcopy(tier_cfg)
    dormant_rec['assumptions']['nie_detail']['categories'][0]['recognition']={'mode':'annual','first_period':2}
    dormant_run=run_pf_a(dormant_rec)
    ck('stored recurring-expense recognition is inert when entered recurring expense is zero and tiered timing owns the component',
       abs(dormant_run['is']['otherOpex'][8]-tier_expected)<1e-6
       and all(abs(dormant_run['is']['otherOpex'][k])<1e-9 for k in range(8)))

    dormant_sett=copy.deepcopy(tier_cfg)
    dormant_sett['assumptions']['nie_detail']['categories'][0]['settlement']={'mode':'annual','first_payment_period':2}
    dormant_sett_run=run_pf_a(dormant_sett)
    ck('stored recurring-expense settlement is inert when entered recurring expense is zero and tiered timing owns the component',
       abs(dormant_sett_run['is']['otherOpex'][8]-tier_expected)<1e-6
       and all(abs(dormant_sett_run['is']['otherOpex'][k])<1e-9 for k in range(8)))

    bad_lag=copy.deepcopy(tier_cfg); bad_lag['assumptions']['periods_per_year']=4; bad_lag['assumptions']['n_periods']=4
    bad=False
    try: validate_config_v2(bad_lag)
    except ConfigErrorV2 as e: bad='finer than' in str(e)
    ck('tiered component fails closed when a one-month observation lag cannot be represented at quarterly cadence',bad)

    # Ownership contract: category recognition/settlement govern only the entered recurring path.
    # Additive linked components retain their own/native timing and may coexist with those controls.
    c=base_cfg(12); a=c['assumptions']; a['capital_raises']=[]; a['nie_detail']['categories']=[{
        'name':'Mixed settlement','flow_spec':{'trajectory':'flat','value':120_000,'period':'year'},
        'linked_components':[{'driver':'fee_income','rate_spec':{'trajectory':'flat','value':.1}}],
        'settlement':{'mode':'annual','first_payment_period':1}}]
    mixed_valid=True
    try: validate_config_v2(c)
    except ConfigErrorV2: mixed_valid=False
    mixed_settlement=run_pf_a(c)
    ck('validation accepts recurring-expense-owned timing alongside additive components', mixed_valid)
    ck('custom recurring-expense settlement can coexist with an additive linked component',
       abs(mixed_settlement['is']['otherOpex'][0]-(10_000+mixed_settlement['is']['fees'][0]*.1))<1e-6)

    c=base_cfg(12); a=c['assumptions']; a['nie_detail']['categories']=[{
        'name':'Mixed recognition','flow_spec':{'trajectory':'flat','value':120_000,'period':'year'},
        'linked_components':[{'driver':'fee_income','rate_spec':{'trajectory':'flat','value':.1}}],
        'recognition':{'mode':'annual','first_period':1}}]
    mixed_recognition=run_pf_a(c)
    ck('custom recurring-expense recognition can coexist with an additive linked component',
       abs(mixed_recognition['is']['otherOpex'][0]-(120_000+mixed_recognition['is']['fees'][0]*.1))<1e-6
       and abs(mixed_recognition['is']['otherOpex'][1]-(mixed_recognition['is']['fees'][1]*.1))<1e-6)

    print(f'\n{P} passed, {F} failed')
    return 0 if F==0 else 1
if __name__=='__main__': sys.exit(main())
