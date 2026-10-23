"""Reusable weighted deposits and typed, read-only expense calculations."""
import copy
import unittest
from .tests_r380_customer_deposits import config, flat
from .tests_r366_shared_lending import entered
from .engine_q_a import run_pf_a
from .run_q import run_v2
from .validate_q import validate_errors_v2
from .linked_calculations import compile_expression, evaluate
from .audit_workbook import _operating_expense_rows, _opex_component_detail_rows


def leaf(value,unit='scalar',per='none'):
    return dict(op='entered',unit=unit,per=per,spec=flat(value))
def op(kind,a,b):return dict(op=kind,args=[a,b])
def setup(ppy=12):
    c=config(ppy);a=c['assumptions'];p=a['deposit_products'][0];p['source_catalog_id']='deposits-1'
    a['balance_components_model']={'enabled':False,'inputs':[{'id':'balances','name':'Weighted balance','unit':'money_per_unit','amount_time_basis':'none','spec':{'source':'weighted_sum','unit':'money_per_unit','components':[{'id':'small','name':'Small','amount_spec':entered(1000,'money_per_unit'),'weight_spec':entered(.8,'share')},{'id':'large','name':'Large','amount_spec':entered(5000,'money_per_unit'),'weight_spec':entered(.2,'share')}]}}]}
    p['balance_driver']['balance_per_customer_spec']={'source':'input_ref','input_id':'balances','factors':[entered(.05,'share')]}
    feed=a['cac_feeds']['Accounts'];feed['activity_series_ids']={'new_customers':'all-new','lost_customers':'all-lost'}
    feed['channels'][0]['activity_series_ids']={'new_customers':'direct-new','lost_customers':'direct-lost'}
    feed['channels'].append({'name':'Partner','method':'explicit','driver_specs':{'new_customers':{'source':'entered','mode':'flat','value':10000,'period':'month'}},'avg_auc_per_customer':0,'activity_series_ids':{'new_customers':'partner-new','lost_customers':'partner-lost'}})
    a['nie_mode']='detailed';a['nie_detail']={'categories':[{'name':'Distribution cost','series_id':'expense-1','flow_spec':dict(trajectory='flat',value=0,period='month'),'linked_components':[]}]}
    from .account_activity import ensure_flow_ids
    ensure_flow_ids(a)
    return c

def expression():
    balance=dict(op='balance',series_id='deposit.deposits-1.balance',measure='period_end')
    earned=op('multiply',op('multiply',dict(op='reference_rate',series_id='effr'),balance),leaf(1/12))
    margin=op('subtract',earned,dict(op='deposit_interest',series_id='deposits-1'))
    ratio=op('divide',dict(op='activity',series_id='partner-new',observation='cumulative'),dict(op='activity',series_id='all-new',observation='cumulative'));ratio['zero_policy']='zero'
    return op('multiply',op('multiply',ratio,leaf(.2)),margin)

def with_calc(c,expr=None):
    c['assumptions']['nie_detail']['categories'][0]['linked_components']=[dict(driver='linked_calculation',component_id='calc-1',name='Margin share',expression=expr or expression())]
    return c

class LinkedCalculationsTests(unittest.TestCase):
    def test_weighted_deposits_live_and_legacy_equivalence(self):
        c=setup();before=copy.deepcopy(c);a=c['assumptions'];out=run_pf_a(c);self.assertEqual(c,before)
        p=next(x for x in out['products'] if x['family']=='deposit');self.assertAlmostEqual(p['bal'][1],80000*1800*.05)
        legacy=copy.deepcopy(c);legacy['assumptions']['deposit_products'][0]['balance_driver']['balance_per_customer_spec']=flat(90)
        expected=run_pf_a(legacy)
        for key in ('bal','intExp','interest'):self.assertEqual(p[key],next(x for x in expected['products'] if x['family']=='deposit')[key])
        a['balance_components_model']['inputs'][0]['spec']['components'][0]['amount_spec']['value']=2000
        self.assertGreater(run_pf_a(c)['bs']['deposits'][1],out['bs']['deposits'][1])
        c=setup(4);from .deposit_balance import customer_balance
        d=customer_balance(c['assumptions']['deposit_products'][0],c['assumptions'],20,4)
        self.assertEqual(d['monthlyDollarsPerCustomer'],[90]*60)
        self.assertTrue(d['assumptionCalculation'])

    def test_margin_expense_end_vs_average_cumulative_ratio_and_negative(self):
        c=with_calc(setup());self.assertEqual(validate_errors_v2(c),[])
        before=copy.deepcopy(c);out=run_pf_a(c);self.assertEqual(c,before)
        p=next(x for x in out['products'] if x['family']=='deposit')
        from .engine_q_a import _build_rate_curve_set
        rates=_build_rate_curve_set(c['assumptions'],c,12)
        expected=[]
        for i in range(60):
            expected.append(.125*.2*(rates['effr'](i+1)*p['bal'][i+1]/12-p['intExp'][i]))
        actual=out['nie_linked_by_category']['total']
        for x,y in zip(expected,actual):self.assertAlmostEqual(x,y,places=7)
        self.assertLess(actual[0],0) # No unrequested floor on negative margin.
        c['assumptions']['cac_feeds']['Accounts']['channels'][1]['driver_specs']['new_customers']['value']=0
        self.assertEqual(run_pf_a(c)['nie_linked_by_category']['total'],[0]*60)

    def test_guards_units_and_fail_closed(self):
        c=setup();a=c['assumptions'];cat=a['nie_detail']['categories'][0]
        e=op('divide',leaf(123,'money'),leaf(0));e['zero_policy']='zero'
        compiled=compile_expression(e,a,60,12,None,cat);self.assertEqual(evaluate(compiled,0,{}),0)
        e['zero_policy']='error';compiled=compile_expression(e,a,60,12,None,cat)
        with self.assertRaisesRegex(ValueError,'zero'):evaluate(compiled,0,{})
        cond={'op':'if_positive','args':[leaf(0),e,leaf(0,'money')]}
        self.assertEqual(evaluate(compile_expression(cond,a,60,12,None,cat),0,{}),0)
        for bad in [op('add',leaf(1,'money'),leaf(1)),dict(op='deposit_interest',series_id='missing'),dict(op='balance',series_id='missing'),dict(op='activity',series_id='missing'),dict(op='entered',unit='money',spec=flat(float('nan')))]:
            with self.assertRaises((ValueError,TypeError)):compile_expression(bad,a,60,12,None,cat)
        cyc=setup();ca=cyc['assumptions'];category=ca['nie_detail']['categories'][0]
        ca['cac_feeds']['Accounts']['channels'][0]['driver_specs']['spend']={'source':'link','link':{'kind':'operating_expense_category','series_id':'expense-1'}}
        with self.assertRaisesRegex(ValueError,'cycle'):
            compile_expression(dict(op='deposit_interest',series_id='deposits-1'),ca,60,12,None,category)
        bad=with_calc(c,op('add',leaf(1,'money'),leaf(1)))
        self.assertTrue(validate_errors_v2(bad))

    def test_quarterly_observations_and_profile_b_actual_interest(self):
        # Expressions explicitly own natural-period conversion; quarter uses its own observations.
        c=setup(4);expr=expression()
        expr['args'][1]['args'][0]['args'][1]=leaf(1,per='year')
        with_calc(c,expr);out=run_pf_a(c)
        p=next(x for x in out['products'] if x['family']=='deposit')
        from .engine_q_a import _build_rate_curve_set
        curves=_build_rate_curve_set(c['assumptions'],c,4)
        self.assertAlmostEqual(out['nie_linked_by_category']['total'][0],.125*.2*(curves['effr'](1)*p['bal'][1]/4-p['intExp'][0]))
        import json
        from pathlib import Path
        from .engine_q_b import run_pf_b
        c=json.loads(Path('foundry/fixtures/parity/configs/pf_b_base.json').read_text())
        a=c['assumptions'];p=a['deposit_products'][0];p['source_catalog_id']='b-deposit'
        a['nie_mode']='detailed';a['nie_detail']={'categories':[{'name':'Contract share','series_id':'contract-cost','flow_spec':dict(trajectory='flat',value=0,period='quarter'),'linked_components':[dict(driver='linked_calculation',name='Expense share',expression=op('multiply',dict(op='deposit_interest',series_id='b-deposit'),leaf(.2)))]}]}
        p['minimum_interest_expense']={'period':'month','amount_spec':flat(10000000)}
        out=run_pf_b(c)
        baseline=copy.deepcopy(c);baseline['assumptions']['nie_detail']['categories'][0]['linked_components']=[]
        self.assertAlmostEqual(out['is']['otherOpex'][0]-run_pf_b(baseline)['is']['otherOpex'][0],6000000)

    def test_audit_and_public_units(self):
        c=with_calc(setup());out=run_pf_a(c);pub=run_v2(c)
        rows=_operating_expense_rows(c,pub,60,12,exact=out)
        found=[r for r in rows if r[1]=='Margin share'];self.assertTrue(found)
        self.assertAlmostEqual(found[0][4][0]*1000,out['nie_linked_by_category']['total'][0])
        detail=_opex_component_detail_rows(c,pub,60,12,exact=out)
        self.assertFalse(any('ERROR:' in str(r) for r in detail),str(detail[:2]))
        self.assertTrue(any('Operand unit:' in str(r) for r in detail))

if __name__=='__main__':unittest.main()
