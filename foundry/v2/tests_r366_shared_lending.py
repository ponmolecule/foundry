import copy
import json
import unittest
from pathlib import Path
from .shared_assumptions import SharedAssumptions
from .tests_linked_loan_balance import _cfg
from .engine_q_a import run_pf_a
from .run_q import run_v2


def entered(v,u):return {'source':'entered','trajectory':'flat','value':v,'unit':u}
def fixture():
    c=_cfg();a=c['assumptions'];a['periods_per_year']=12;a['n_periods']=60
    amounts=[6493634,13998822,29239418,110763089];weights=[.74,.19,.05,.02]
    a['balance_components_model']={'enabled':False,'inputs':[{'id':'generic-value','name':'Annual amount per account','unit':'money_per_unit','amount_time_basis':'year','spec':{'source':'weighted_sum','unit':'money_per_unit','components':[{'id':'segment-'+str(i),'name':'Size '+str(i),'amount_spec':entered(v,'money_per_unit'),'weight_spec':entered(w,'share')} for i,(v,w) in enumerate(zip(amounts,weights))]}}],'components':[]}
    a['lending_products'][0]['balance_driver']['average_balance_per_customer_spec']={'source':'input_ref','input_id':'generic-value','factors':[dict(entered(.0411,'share'),name='Advance share')]}
    return c

class SharedLendingTests(unittest.TestCase):
    def test_source_equivalence_and_live_inputs(self):
        cfg=fixture();saved=copy.deepcopy(cfg);r=run_pf_a(cfg);self.assertEqual(cfg,saved)
        p=r['products'][0];amount=sum(a*w for a,w in zip([6493634,13998822,29239418,110763089],[.74,.19,.05,.02]))*.0411
        self.assertAlmostEqual(amount,457948.448622)
        self.assertAlmostEqual(p['averageBalancePerCustomer'][0],amount)
        self.assertAlmostEqual(p['bal'][1],100*amount)
        old=copy.deepcopy(cfg);old['assumptions']['lending_products'][0]['balance_driver']['average_balance_per_customer_spec']=entered(amount,'money_per_unit')
        expected=run_pf_a(old)
        for key in ('bal','interest','co','alll','opex'):
            for v,w in zip(p[key],expected['products'][0][key]):self.assertAlmostEqual(v,w,places=6)
        cfg['assumptions']['balance_components_model']['inputs'][0]['spec']['components'][0]['amount_spec']['value']*=2
        self.assertGreater(run_pf_a(cfg)['products'][0]['bal'][1],p['bal'][1])
        cfg['assumptions']['lending_products'][0]['balance_driver']['average_balance_per_customer_spec']['factors'][0]['value']=.02
        self.assertLess(run_pf_a(cfg)['products'][0]['bal'][1],p['bal'][1])

    def test_reuse_rename_and_monthly_resolution(self):
        c=fixture();a=c['assumptions'];s=a['lending_products'][0]['balance_driver']['average_balance_per_customer_spec']
        x=a['balance_components_model']['inputs'][0];before=SharedAssumptions(a,60,12).resolve(s,'money_per_unit')[0]
        x['name']='Different industry';self.assertEqual(before,SharedAssumptions(a,60,12).resolve(s,'money_per_unit')[0])
        part=x['spec']['components'][0];part['amount_spec']={'source':'entered','unit':'money_per_unit','trajectory':'explicit','cadence':'month','values':[100,200,300],'extend':'hold'}
        monthly=SharedAssumptions(a,60,12).resolve(s,'money_per_unit')[0];quarterly=SharedAssumptions(a,20,4).resolve(s,'money_per_unit')[0]
        self.assertEqual(quarterly,monthly[2::3])
        a['lending_products'].append(copy.deepcopy(a['lending_products'][0]));a['lending_products'][1]['name']='Other lending use'
        r=run_pf_a(c);self.assertEqual(r['products'][0]['bal'],r['products'][1]['bal'])

    def test_segment_source_recurrence_and_credit(self):
        c=fixture();a=c['assumptions'];a['n_periods']=12
        feed=a['cac_feeds']['ubl'];feed['beginning_customers']=0
        adds=[4.8125,9.625,9.625,14,14,14,20,20,20,25,25,25]
        gross=[v*min(.5+i*.0125,.8) for i,v in enumerate(adds)]
        feed['channels']=[{'name':'Linked population result','method':'explicit','driver_specs':{'new_customers':{'source':'entered','trajectory':'explicit','cadence':'month','values':gross,'extend':'hold'}},'params':{}}]
        feed['driver_specs']={'attrition_rate':{'source':'entered','trajectory':'flat','value':.1/12,'period':'month'}}
        p=a['lending_products'][0];p['yield_ann']=.11;p['charge_off_ann']=.01;p['reserve_rate_pct_bal']=.0045
        r=run_pf_a(c)['products'][0];counts=[0]*4;prior=0
        amounts=[6493634,13998822,29239418,110763089];weights=[.74,.19,.05,.02]
        for i,new in enumerate(gross):
            counts=[v*(1-.1/12)+new*w for v,w in zip(counts,weights)]
            end=sum(v*t*.0411 for v,t in zip(counts,amounts))
            self.assertAlmostEqual(r['bal'][i+1],end,places=6)
            self.assertAlmostEqual(r['interest'][i],.11/12*(prior+end)/2,places=6)
            self.assertAlmostEqual(r['co'][i],.01/12*prior,places=6)
            self.assertAlmostEqual(r['alll'][i],.0045*end,places=6)
            prior=end

    def test_reuse_in_existing_balance_component(self):
        from .balance_components import BalanceComponents
        c=fixture();a=c['assumptions'];m=a['balance_components_model'];m['enabled']=True
        m['components']=[{'id':'other-use','name':'Other purpose','treatment':'off_book','terms':[{'source_spec':{'source':'customer_count','series_id':'count','measure':'period_end'},'factors':[{'source':'input_ref','input_id':'generic-value'}]}]}]
        bc=BalanceComponents(a,{'count':{'period_end':[2]*12}},{},12,12)
        self.assertAlmostEqual(bc.value({'source':'input_ref','input_id':'generic-value'},0,{}),11142298.02)

    def test_invalid_inputs_fail_closed(self):
        for mutation in ('missing','cycle','weights','negative','nan','units','future-weight'):
            c=fixture();a=c['assumptions'];s=a['lending_products'][0]['balance_driver']['average_balance_per_customer_spec'];x=a['balance_components_model']['inputs'][0];part=x['spec']['components'][0]
            if mutation=='missing':s['input_id']='absent'
            if mutation=='cycle':x['spec']={'source':'input_ref','input_id':x['id']}
            if mutation=='weights':part['weight_spec']['value']=.5
            if mutation=='negative':part['amount_spec']['value']=-1
            if mutation=='nan':part['amount_spec']['value']=float('nan')
            if mutation=='units':x['unit']='count'
            if mutation=='future-weight':part['weight_spec']={'source':'entered','unit':'share','trajectory':'explicit','cadence':'year','values':[.74,.5],'extend':'hold'}
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):run_pf_a(c)

    def test_public_detail_and_audit(self):
        from .audit_workbook import calculation_audit_workbook
        c=fixture();r=run_v2(c);p=r['products'][0]
        self.assertTrue(p['lendingAssumptionDetail'])
        self.assertAlmostEqual(next(x for x in p['lendingAssumptionDetail'] if x['name']=='Annual amount per account')['values'][0],11142298.02)
        wb=calculation_audit_workbook(c,r);self.assertIn('Lending Assumptions',wb.sheetnames)
