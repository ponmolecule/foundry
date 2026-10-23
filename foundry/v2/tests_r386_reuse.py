"""Live balances and margin costs using existing deposit and Formula mechanics."""
import copy
import unittest
from .tests_r380_customer_deposits import config, flat
from .tests_r366_shared_lending import entered
from .engine_q_a import run_pf_a, _build_rate_curve_set
from .run_q import run_v2
from .validate_q import validate_errors_v2
from .opex_extensions import resolve_linked_components, linked_component_amount
from .source_catalog import acquisition_share_catalog
from .audit_workbook import _operating_expense_rows, _opex_component_detail_rows


def linked(source,sid,**kw):return dict(kind='linked',name=source,source=source,series_id=sid,**kw)
def factor(v):return dict(kind='entered',op='multiply',name='Participation',periodized=False,display='percent',spec=flat(v))
def setup(ppy=12):
    c=config(ppy);a=c['assumptions'];p=a['deposit_products'][0];p['source_catalog_id']='part-a'
    p['name']='Deposit portion A';p['rate_paid_ann']=.0125
    amounts=[404711.92264,883608.79509,2029378.03469,7746420.64012];weights=[.735414627,.192686753,.048006255,.023892365]
    p['balance_driver']['balance_per_customer_spec']={'source':'weighted_sum','unit':'money_per_unit','components':[{'id':'segment-'+str(i),'name':'Segment '+str(i),'amount_spec':entered(v,'money_per_unit'),'weight_spec':entered(w,'share')} for i,(v,w) in enumerate(zip(amounts,weights))]}
    p['balance_driver']['balance_share_spec']=flat(.05)
    other=copy.deepcopy(p);other.update(source_catalog_id='part-b',name='Deposit portion B',rate_paid_ann=.03)
    other['balance_driver']['balance_per_customer_spec']={'source':'deposit_customer_amount','series_id':'part-a'};other['balance_driver']['balance_share_spec']=flat(.95)
    a['deposit_products'].append(other)
    f=a['cac_feeds']['Accounts'];f['activity_series_ids']={'new_customers':'total-new','lost_customers':'total-lost'}
    f['channels'][0]['driver_specs']['new_customers']['value']=20
    f['channels'][0]['activity_series_ids']={'new_customers':'direct-new','lost_customers':'direct-lost'}
    f['channels'].append({'name':'Partner','method':'explicit','driver_specs':{'new_customers':{'source':'entered','mode':'flat','value':5,'period':'month'}},'avg_auc_per_customer':0,'activity_series_ids':{'new_customers':'partner-new','lost_customers':'partner-lost'}})
    from .account_activity import ensure_flow_ids
    ensure_flow_ids(a)
    a['nie_mode']='detailed';a['nie_detail']={'categories':[{'name':'Distribution agreement','series_id':'agreement','flow_spec':{'trajectory':'flat','value':0,'period':'month'},'linked_components':[]}]}
    return c

def attach_formula(c):
    a=c['assumptions'];share=next(x for x in acquisition_share_catalog(a) if x['numerator']=='partner-new' and x['observation']=='cumulative')
    terms=[dict(name='Eligible earnings '+p['name'],sign=1,factors=[linked('catalog_quantity','deposit.'+p['source_catalog_id']+'.balance',measure='period_end'),linked('reference_rate','effr',rate_period='year')]) for p in a['deposit_products']]
    terms += [dict(name='Interest cost '+p['name'],sign=-1,factors=[linked('deposit_interest',p['source_catalog_id'])]) for p in a['deposit_products']]
    a['nie_detail']['categories'][0]['linked_components']=[dict(driver='formula_driver',component_id='participation',name='Margin participation',base_terms=terms,factors=[factor(.2),linked('acquisition_share',share['series_id'],zero_denominator='zero')],positive_balance_guard={'series_ids':['deposit.'+p['source_catalog_id']+'.balance' for p in a['deposit_products']],'measure':'period_end'})]
    return c

class ReuseTests(unittest.TestCase):
    def test_balances_shares_link_identity_and_live_changes(self):
        c=setup();self.assertEqual(validate_errors_v2(c),[]);saved=copy.deepcopy(c);out=run_pf_a(c);self.assertEqual(c,saved)
        ps=[p for p in out['products'] if p['family']=='deposit'];amount=sum(v*w for v,w in zip([404711.92264,883608.79509,2029378.03469,7746420.64012],[.735414627,.192686753,.048006255,.023892365]));count=0
        for i in range(60):
            count=count*(1-.1/12)+25
            self.assertAlmostEqual(ps[0]['bal'][i+1],count*amount*.05,places=6)
            self.assertAlmostEqual(ps[1]['bal'][i+1],count*amount*.95,places=5)
        legacy=copy.deepcopy(c)
        for p,share in zip(legacy['assumptions']['deposit_products'],[.05,.95]):
            p['balance_driver']['balance_per_customer_spec']=flat(amount*share);p['balance_driver'].pop('balance_share_spec')
        expected=run_pf_a(legacy)
        for p,q in zip(ps,[p for p in expected['products'] if p['family']=='deposit']):
            for key in ('bal','intExp'):
                for x,y in zip(p[key],q[key]):self.assertAlmostEqual(x,y,places=5)
        a=c['assumptions'];a['deposit_products'][0]['name']='Renamed'
        self.assertEqual(run_pf_a(c)['bs']['deposits'],out['bs']['deposits'])
        a['deposit_products'][0]['balance_driver']['balance_per_customer_spec']['components'][0]['amount_spec']['value']*=2
        changed=run_pf_a(c);self.assertGreater(changed['bs']['deposits'][1],out['bs']['deposits'][1])
        a['cac_feeds']['Accounts']['channels'][0]['driver_specs']['new_customers']['value']*=2
        self.assertGreater(run_pf_a(c)['bs']['deposits'][1],changed['bs']['deposits'][1])

    def test_mixed_exposure_margin_no_duplicate_income(self):
        c=attach_formula(setup());self.assertEqual(validate_errors_v2(c),[])
        out=run_pf_a(c);curves=_build_rate_curve_set(c['assumptions'],c,12)
        for i,value in enumerate(out['nie_linked_by_category']['total']):
            expected=.2*.2*(curves['effr'](i+1)*out['bs']['deposits'][i+1]/12-out['is']['depExp'][i])
            self.assertAlmostEqual(value,expected,places=6)
        baseline=copy.deepcopy(c);baseline['assumptions']['nie_detail']['categories'][0]['linked_components']=[]
        b=run_pf_a(baseline);self.assertEqual(out['bs']['deposits'],b['bs']['deposits']);self.assertEqual(out['is']['depExp'],b['is']['depExp'])
        # Time-varying channel acquisitions must alter the cumulative gross share independently of active counts.
        f=c['assumptions']['cac_feeds']['Accounts']['channels'][1]['driver_specs']['new_customers'];f.update(mode='explicit',values=[0,10]+[5]*58,cadence='month',resolution='step',extend='error')
        from .opex_extensions import resolve_linked_components
        compiled=resolve_linked_components(c['assumptions']['nie_detail']['categories'][0],60,12,assumptions=c['assumptions']);self.assertTrue(compiled[0]['base_terms'])
        changed=run_pf_a(c)
        self.assertEqual(changed['nie_linked_by_category']['total'][0],0)
        # Confirm isolation from unrelated deposit products in the same engagement.
        extra=copy.deepcopy(c['assumptions']['deposit_products'][0]);extra.update(name='Unrelated deposits',source_catalog_id='unrelated',balance_mode='level',ending_balance_spec=flat(20000000),rate_paid_ann=.05)
        c['assumptions']['deposit_products'].append(extra)
        isolated=run_pf_a(c)
        self.assertEqual(isolated['nie_linked_by_category'],changed['nie_linked_by_category'])

    def test_quarterly_monthly_pairing_and_fail_closed(self):
        from .deposit_balance import customer_balance
        c=setup(4);a=c['assumptions'];p=a['deposit_products'][0]
        p['balance_driver']['measure']='period_average'
        p['balance_driver']['balance_share_spec']={'source':'entered','trajectory':'explicit','cadence':'month','values':[.1,.2,.3]+[.3]*57,'extend':'error'}
        d=customer_balance(p,a,20,4)
        self.assertAlmostEqual(d['endingBalanceDollars'][0],sum(x*y*z for x,y,z in zip(d['monthlyCount'][:3],d['monthlyDollarsPerCustomer'][:3],[.1,.2,.3]))/3)
        for change in ['cycle','missing','weights','share']:
            x=setup();ps=x['assumptions']['deposit_products']
            if change=='cycle':ps[0]['balance_driver']['balance_per_customer_spec']={'source':'deposit_customer_amount','series_id':'part-b'}
            elif change=='missing':ps[1]['balance_driver']['balance_per_customer_spec']['series_id']='absent'
            elif change=='weights':ps[0]['balance_driver']['balance_per_customer_spec']['components'][0]['weight_spec']['value']=1
            else:ps[0]['balance_driver']['balance_share_spec']=flat(1.1)
            self.assertTrue(validate_errors_v2(x),change)
        x=attach_formula(setup());x['assumptions']['nie_detail']['categories'][0]['linked_components'][0]['base_terms'][1]['factors'][0]['series_id']='missing'
        self.assertTrue(validate_errors_v2(x))

    def test_quarterly_formula_actual_profile_b_expense_and_cycle(self):
        import json
        from pathlib import Path
        from .engine_q_b import run_pf_b
        c=json.loads(Path('foundry/fixtures/parity/configs/pf_b_base.json').read_text());a=c['assumptions'];p=a['deposit_products'][0];p['source_catalog_id']='priced'
        a['nie_mode']='detailed';a['nie_detail']={'categories':[{'name':'Expense participation','series_id':'contract','flow_spec':{'trajectory':'flat','value':0,'period':'quarter'},'linked_components':[{'driver':'formula_driver','name':'Sharing','base_terms':[{'sign':1,'factors':[linked('deposit_interest','priced')]}],'factors':[factor(.2)]}]}]}
        p['minimum_interest_expense']={'period':'month','amount_spec':flat(10000000)}
        out=run_pf_b(c);base=copy.deepcopy(c);base['assumptions']['nie_detail']['categories'][0]['linked_components']=[]
        self.assertAlmostEqual(out['is']['otherOpex'][0]-run_pf_b(base)['is']['otherOpex'][0],6000000)
        c=attach_formula(setup(4));self.assertEqual(validate_errors_v2(c),[]);q=run_pf_a(c)
        curve=_build_rate_curve_set(c['assumptions'],c,4)['effr']
        self.assertAlmostEqual(q['nie_linked_by_category']['total'][0],.2*.2*(curve(1)*q['bs']['deposits'][1]/4-q['is']['depExp'][0]),places=6)
        cyc=attach_formula(setup());cyc['assumptions']['cac_feeds']['Accounts']['channels'][0]['driver_specs']['spend']={'source':'link','link':{'kind':'operating_expense_category','series_id':'agreement'}}
        self.assertTrue(validate_errors_v2(cyc))

    def test_zero_denominator_condition_negative_margin_and_audit(self):
        c=attach_formula(setup());a=c['assumptions'];cat=a['nie_detail']['categories'][0];comp=resolve_linked_components(cat,60,12,assumptions=a)[0]
        metrics={'periods_per_year':12,'catalog_balances':{'deposit.part-a.balance':{'period_end':5},'deposit.part-b.balance':{'period_end':95}},'financial_observations':{('reference_rate','effr'):.01,('deposit_interest','part-a'):100,('deposit_interest','part-b'):200},'account_activity':{'partner-new':{'values':[1]*60},'total-new':{'values':[4]*60}}}
        self.assertAlmostEqual(linked_component_amount(comp,0,metrics),(.01*100/12-300)*.2*.25)
        metrics['account_activity']['total-new']['values']=[0]*60;self.assertEqual(linked_component_amount(comp,0,metrics),0)
        metrics['catalog_balances']['deposit.part-a.balance']['period_end']=0;metrics['catalog_balances']['deposit.part-b.balance']['period_end']=0;metrics['financial_observations']={};self.assertEqual(linked_component_amount(comp,0,metrics),0)
        fraud=copy.deepcopy(c);fc=fraud['assumptions']['nie_detail']['categories'][0]['linked_components'][0]
        fc['base_terms']=[{'sign':1,'factors':[linked('catalog_quantity','deposit.'+sid+'.balance',measure='period_end')]} for sid in ['part-a','part-b']]
        fc['factors']=[dict(factor(.001),rate_period='year')]
        fo=run_pf_a(fraud)
        self.assertAlmostEqual(fo['nie_linked_by_category']['total'][0],fo['bs']['deposits'][1]*.001/12,places=7)
        out=run_pf_a(c);pub=run_v2(c);rows=_operating_expense_rows(c,pub,60,12,exact=out)
        row=next(r for r in rows if r[1]=='Margin participation');self.assertAlmostEqual(row[4][0]*1000,out['nie_linked_by_category']['total'][0])
        detail=_opex_component_detail_rows(c,pub,60,12,exact=out);self.assertFalse(any('ERROR:' in str(r) for r in detail));self.assertTrue(any('Signed base item' in str(r) for r in detail))

if __name__=='__main__':unittest.main()
