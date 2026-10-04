"""Legacy editor promotion preserves source economics at every model cadence."""
import copy
from .opex_extensions import resolve_linked_components, linked_component_amount
from .tests_opex_extensions import base_cfg
from .engine_q_a import run_pf_a
from .validate_q import validate_errors_v2
from .audit_workbook import _opex_component_detail_rows


def promote(c):
    b={'kind':'linked','source':c['driver'],'op':'multiply'}
    if c.get('series_id'): b['series_id']=c['series_id']
    wf=c['driver']=='workforce_count';auc=c['driver']=='customer_acquisition_auc'
    r={'kind':'entered','op':'multiply','periodized':wf,'spec':copy.deepcopy(c['amount_spec'] if wf else c['rate_spec'])}
    out={'driver':'formula_driver','factors':[b,r]}
    if auc:
        b['measure']=c.get('measure','period_end');r['rate_period']=c.get('rate_period','year');out['accrual_cadence']='monthly'
    return out


def main():
    count=0
    for ppy in (12,4):
        n=ppy
        metrics={'periods_per_year':ppy,'fee_income':1200,'gain_on_sale':200,'servicing_net':300,'fee_product_costs':100,
                 'fee_stream_quantities':{'qty':1234},'workforce_count':{'wf':7},
                 'customer_acquisition_auc_beginning':{'auc':100},
                 'customer_acquisition_auc_monthly':{'auc':[100*(i+2) for i in range(12)]}}
        cases=[{'driver':d,'rate_spec':{'source':'entered','trajectory':'flat','value':.015}} for d in
               ('fee_income','gain_on_sale','servicing_net','noninterest_income','net_fee_income')]
        cases.append({'driver':'fee_stream_quantity','series_id':'qty','rate_spec':{'source':'entered','trajectory':'flat','value':.015}})
        for period in ('month','quarter','year'):
            for spec in ({'trajectory':'flat','value':120,'period':period},
                         {'trajectory':'growth','value':120,'period':period,'growth_spec':{'rate':.1,'period':'year','method':'step'}},
                         {'trajectory':'explicit','values':[120]*(12 if period=='month' else 4 if period=='quarter' else 1),'period':period}):
                cases.append({'driver':'workforce_count','series_id':'wf','amount_spec':spec})
            for measure in ('period_average','period_end'):
                for rates in ({'source':'entered','trajectory':'flat','value':.12},
                              {'source':'entered','trajectory':'growth','base':.12,'growth_spec':{'rate':.1,'period':'year','method':'step'}},
                              {'source':'entered','trajectory':'explicit','values':[.01*(i+1) for i in range(12)],'cadence':'month','resolution':'step','extend':'hold'}):
                    cases.append({'driver':'customer_acquisition_auc','series_id':'auc','measure':measure,'rate_period':period,'rate_spec':rates})
        for raw in cases:
            old=resolve_linked_components({'linked_components':[raw]},n,ppy)[0]
            new=resolve_linked_components({'linked_components':[promote(raw)]},n,ppy)[0]
            a=[linked_component_amount(old,i,metrics) for i in range(n)]
            b=[linked_component_amount(new,i,metrics) for i in range(n)]
            assert a==b,(ppy,raw,a,b)
            count+=1
            if raw['driver']=='customer_acquisition_auc':
                extra=promote(raw);extra['factors'].append({'kind':'entered','op':'multiply','spec':{'source':'entered','trajectory':'flat','value':2}})
                compiled=resolve_linked_components({'linked_components':[extra]},n,ppy)[0]
                assert [linked_component_amount(compiled,i,metrics) for i in range(n)]==[2*x for x in a]
    # Generic rate period is separate from observation cadence; invalid accrual pairs fail closed.
    for ppy in (12,4):
        formula={'driver':'formula_driver','factors':[{'kind':'linked','source':'fee_income'},
            {'kind':'entered','rate_period':'year','spec':{'source':'entered','trajectory':'flat','value':.12}}]}
        compiled=resolve_linked_components({'linked_components':[formula]},ppy,ppy)[0]
        assert abs(linked_component_amount(compiled,0,{'fee_income':100})-100*.12/ppy)<1e-12
        formula['accrual_cadence']='monthly'
        try: resolve_linked_components({'linked_components':[formula]},ppy,ppy)
        except ValueError: pass
        else: raise AssertionError('invalid monthly pair accepted')
    # Full engine + validator + audit: varying monthly rates in a quarterly model.
    for ppy in (12,4):
        c=base_cfg(ppy);a=c['assumptions'];a['capital_raises']=[]
        a['cac_feeds']={'Flow':{'series_id':'auc','beginning_auc':0,'beginning_customers':0,'attrition_rate':0,'intra_year_shape':'linear','channels':[{'name':'Organic','method':'pool_conversion','params':{'pool':12,'pool_growth':0,'conversion_rate':1,'conversion_growth':0},'avg_auc_per_customer':1000000,'avg_auc_growth':0}]}}
        raw={'driver':'customer_acquisition_auc','series_id':'auc','measure':'period_average','rate_period':'year','rate_spec':{'source':'entered','trajectory':'explicit','cadence':'month','values':[.001*(i+1) for i in range(12)],'resolution':'step','extend':'hold'}}
        cat={'name':'Assessment','series_id':'assessment','flow_spec':{'trajectory':'flat','value':0,'period':'year'},'linked_components':[raw]};a['nie_detail']['categories']=[cat]
        old=run_pf_a(c);cat['linked_components']=[promote(raw)]
        assert not validate_errors_v2(c),validate_errors_v2(c)
        new=run_pf_a(c)
        assert old['is']==new['is'] and old['bs']==new['bs']
        rows=_opex_component_detail_rows(c,new,a['n_periods'],ppy)
        assert any('Monthly period_average AUC' in str(r[-1]) for r in rows)
        if ppy==4: assert abs(new['is']['otherOpex'][0]-(500000*.001+1500000*.002+2500000*.003)/12)<1e-9
    print(f'PASS {count} component equivalence cases; monthly/quarterly engine, validation and audit checks')

if __name__=='__main__':main()
