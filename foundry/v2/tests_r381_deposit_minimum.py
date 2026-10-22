"""Deposit expense minimum: accounting, binding transitions, units and compatibility."""
import copy, json, unittest
from pathlib import Path
from .deposit_pricing import minimum_interest_path
from .tests_r380_customer_deposits import config
from .tests_deposit_retention import fixture, flat
from .engine_q_a import run_pf_a
from .engine_q_b import run_pf_b
from .run_q import run_v2
from .validate_q import validate_errors_v2
from .audit_workbook import _product_rows


def minimum(amount=30000, period='month'):
    return {'period':period,'amount_spec':flat(amount)}


class DepositMinimumTests(unittest.TestCase):
    def test_source_hsa_nonbinding_and_live_binding(self):
        c=config();p=c['assumptions']['deposit_products'][0]
        p.update(rate_type='fixed',rate_paid_ann=.039*.5)
        before=run_pf_a(c);p['minimum_interest_expense']=minimum()
        self.assertEqual(validate_errors_v2(c),[])
        out=run_pf_a(c);self.assertEqual(before['is'],out['is']);self.assertEqual(before['bs'],out['bs'])
        dep=next(p for p in out['products'] if p['family']=='deposit')
        self.assertAlmostEqual(dep['intExp'][0],54031.25)
        self.assertEqual(dep['minimumInterestTopUp'],[0]*60)
        c['assumptions']['cac_feeds']['Accounts']['channels'][0]['driver_specs']['new_customers']['value']=1000
        dep=next(p for p in run_pf_a(c)['products'] if p['family']=='deposit')
        self.assertAlmostEqual(dep['intExp'][0],30000)
        self.assertAlmostEqual(dep['interestBeforeMinimum'][0],771.875)

    def test_binding_transition_and_single_income_posting(self):
        c=config();a=c['assumptions'];p=a['deposit_products'][0]
        a['n_periods']=12
        p.update(balance_mode='level',rate_paid_ann=.12,ending_balance_spec={'source':'entered','trajectory':'explicit','cadence':'month','values':[0,0,12_000_000]+[12_000_000]*9,'extend':'error'})
        base=run_pf_a(c);p['minimum_interest_expense']=minimum()
        out=run_pf_a(c);d=next(x for x in out['products'] if x['family']=='deposit')
        self.assertEqual(d['intExp'][:4],[30000,30000,60000,120000])
        self.assertEqual(d['minimumInterestTopUp'][:4],[30000,30000,0,0])
        self.assertEqual(base['is']['overhead'],out['is']['overhead'])
        for i in range(12):
            self.assertAlmostEqual(out['is']['depExp'][i]-base['is']['depExp'][i],d['minimumInterestTopUp'][i])
        # Funding/treasury interest may also move as the expense changes equity.
        # The direct posting is the deposit-interest line, with no duplicate NIE.
        self.assertEqual(base['is']['prodOpex'],out['is']['prodOpex'])

    def test_amount_period_and_schedules(self):
        for period,amount in [('month',30000),('quarter',90000),('year',360000)]:
            p={'minimum_interest_expense':minimum(amount,period)}
            self.assertEqual(minimum_interest_path(p,12,12),[30000]*12)
            self.assertEqual(minimum_interest_path(p,4,4),[90000]*4)
        p={'minimum_interest_expense':{'period':'month','amount_spec':{'source':'entered','trajectory':'explicit','cadence':'year','values':[30000,40000],'resolution':'step','extend':'error'}}}
        self.assertEqual(minimum_interest_path(p,24,12),[30000]*12+[40000]*12)
        for bad in [minimum(-1),minimum(float('nan')),minimum(1,'week'),{'period':'month'}]:
            with self.assertRaises(ValueError):minimum_interest_path({'minimum_interest_expense':bad},12,12)

    def test_pool_interest_recalculation(self):
        c=fixture();a=c['assumptions'];a['deposit_products']=a['deposit_products'][:1];p=a['deposit_products'][0]
        p['pool_share_spec']=flat(1);p['minimum_interest_expense']=minimum(5000)
        out=run_pf_a(c);d=next(x for x in out['products'] if x['family']=='deposit')
        self.assertEqual(d['interestBeforeMinimum'][0],4000)
        self.assertEqual(d['minimumInterestTopUp'][0],1000)
        self.assertEqual(d['intExp'][0],5000)

    def test_profile_b_and_public_audit(self):
        c=json.loads(Path('foundry/fixtures/parity/configs/pf_b_base.json').read_text());p=c['assumptions']['deposit_products'][0]
        base=run_pf_b(c);p['minimum_interest_expense']=minimum(10_000_000)
        out=run_pf_b(c);d=next(x for x in out['products'] if x['family']=='deposit')
        self.assertEqual(d['intExp'][0],30_000_000);self.assertEqual(d['interest'][0],-30_000_000)
        self.assertAlmostEqual(out['is']['intDep'][0]-base['is']['intDep'][0],d['minimumInterestTopUp'][0])
        c=config();c['assumptions']['deposit_products'][0]['minimum_interest_expense']=minimum(1_000_000)
        pub=run_v2(c);d=next(x for x in pub['products'] if x['family']=='deposit')
        self.assertEqual(d['detailExact']['minimumInterestExpense'][0],1000)
        rows=_product_rows(pub,60,run_pf_a(c))
        self.assertTrue(any(x[2]=='minimumInterestExpense' and x[4][0]==1000 for x in rows))


if __name__=='__main__':unittest.main()
