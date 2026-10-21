import copy
import unittest
from .tests_linked_loan_balance import _cfg
from .lending_contracts import prepare,step,flat
from .engine_q_a import run_pf_a


def config(n=60, ppy=12):
    c=_cfg();a=c['assumptions'];a['periods_per_year']=ppy;a['n_periods']=n;a['capital_raises']=[]
    p=a['lending_products'][0]
    p.update(balance_mode='rollforward',structure='term',term_q=80,opening_balance=0,
             charge_off_ann=.0017,runoff_per_period=0,originations_per_period=0,yield_ann=.075,fee_yield_ann=0,
             opex_pct_ann=0,opex_fixed_per_period=0)
    p['loan_rollforward']=dict(source='entered_count',count_spec=flat(2),loan_size_spec=flat(1500000),
        payment_rate_spec=flat(.05),prepayment_rate_spec=flat(.05),reserve_rate_spec=flat(.0161),
        opening_allowance=0,provision_release_policy='allow',deferred=dict(basis='per_loan',opening_net_cost=0,
        cost_spec=flat(8500),fee_spec=flat(0),multiplier_spec=flat(1),amortization_rate_spec=flat(.05),prepayment_rate_spec=flat(.05)))
    return c


class LoanContractTests(unittest.TestCase):
    def test_three_portfolio_patterns_and_accounting(self):
        for size,cost,repay,prepay,loss,yield_ in [(1500000,8500,.05,.05,.0017,.075),(250000,3500,.17,.09,.008,.09),(800000,2000,.1,.1333,.0098,.1)]:
            c=config();p=c['assumptions']['lending_products'][0];x=p['loan_rollforward'];x['loan_size_spec']=flat(size);x['deferred']['cost_spec']=flat(cost);x['payment_rate_spec']=flat(repay);x['prepayment_rate_spec']=flat(prepay);x['deferred']['amortization_rate_spec']=flat(repay);x['deferred']['prepayment_rate_spec']=flat(prepay);p['yield_ann']=yield_;p['charge_off_ann']=loss
            before=copy.deepcopy(c);r=run_pf_a(c);self.assertEqual(c,before);v=r['products'][0]
            bal=db=allow=0.
            for i in range(60):
                co=bal*loss/12;end=bal+2*size-bal*(repay+prepay)/12-co
                amort=db*repay/12;catch=db*prepay/12;dbnext=db+2*cost-amort-catch
                interest=(bal+end)/2*yield_/12-amort-catch
                self.assertAlmostEqual(v['principalBalance'][i],end,places=6)
                self.assertAlmostEqual(v['interest'][i],interest,places=6)
                self.assertAlmostEqual(v['deferredNetBalance'][i],dbnext,places=6)
                self.assertAlmostEqual(v['provision'][i],end*.0161-allow+co,places=6)
                self.assertAlmostEqual(r['bs']['grossLoans'][i+1],end+dbnext,places=5)
                bal,db,allow=end,dbnext,end*.0161
            self.assertAlmostEqual(v['newLoanCount'][0],2)

    def test_live_flow_public_precision_and_fee_sign(self):
        c=config(12);a=c['assumptions'];f=a['cac_feeds']['ubl'];f['intra_period_path']='monthly_flows';f['activity_series_ids']={'new_customers':'gross-new','lost_customers':'gross-lost'}
        # Use actual CAC runtime, never net active-count differences.
        f['channels']=[{'name':'Direct','method':'explicit','params':{'new_customers_by_year':[120]},'avg_auc_per_customer':0}]
        p=a['lending_products'][0];p['loan_rollforward']['source']='account_activity';p['loan_rollforward']['series_id']='gross-new'
        from .account_activity import resolve
        act,_=resolve(a,12,12)
        first=run_pf_a(c)['products'][0];self.assertGreater(sum(first['newLoanCount']),0);self.assertEqual(first['newLoanCount'],act['gross-new']['values'])
        p['loan_rollforward']['loan_size_spec']=flat(3000000)
        second=run_pf_a(c)['products'][0];self.assertAlmostEqual(second['origq'][0],first['origq'][0]*2)
        from .run_q import run_v2
        public=run_v2(c)['products'][0];self.assertAlmostEqual(public['detailExact']['deferredNetBalance'][0],second['deferredNetBalance'][0]/1000)
        p['loan_rollforward']['deferred']['cost_spec']=flat(0);p['loan_rollforward']['deferred']['fee_spec']=flat(8500)
        fee=run_pf_a(c)['products'][0];self.assertLess(fee['deferredNetBalance'][0],0)
        self.assertGreater(fee['interest'][1],fee['grossInterest'][1])

    def test_schedule_floor_and_zero_targets(self):
        c=config(24);p=c['assumptions']['lending_products'][0];x=p['loan_rollforward'];x['reserve_rate_spec']={'source':'entered','trajectory':'explicit','cadence':'month','values':[0,0,0]+[.0161]*9+[0]*12,'extend':'hold'}
        x['deferred']['multiplier_spec']={'source':'entered','trajectory':'explicit','cadence':'year','values':[1,1.0404],'extend':'hold'}
        v=run_pf_a(c)['products'][0];self.assertEqual(v['alll'][:3],[0,0,0]);self.assertGreater(v['provision'][1],0)
        self.assertLess(v['provision'][12],0);self.assertAlmostEqual(v['deferredCosts'][12],17000*1.0404)
        x['provision_release_policy']='floor_zero';w=run_pf_a(c)['products'][0];self.assertEqual(w['provision'][12],0);self.assertGreater(w['alll'][12],w['allowanceTarget'][12])

    def test_quarterly_and_invalid(self):
        c=config(8,4);r=run_pf_a(c)['products'][0];self.assertAlmostEqual(r['principalPayments'][1],3000000*.05/4)
        for edit in [lambda p:p.update(balance_mode='explicit_level'),lambda p:p.update(measurement='fair_value'),lambda p:p['loan_rollforward'].update(source='account_activity',series_id='missing'),lambda p:p['loan_rollforward'].update(payment_rate_spec=flat(float('nan'))),lambda p:p['loan_rollforward'].update(provision_release_policy='bad')]:
            c=config();edit(c['assumptions']['lending_products'][0])
            with self.assertRaises(ValueError):run_pf_a(c)
        from .engine_q_b import run_pf_b
        with self.assertRaisesRegex(ValueError,'Profile A'):run_pf_b(config(12,4))

    def test_stress_audit_and_reporting(self):
        c=config();base=run_pf_a(c)['products'][0]
        c['scenario_overlays']={'reserve_mult':2,'charge_off_mult':2,'origination_volume_haircut':.25}
        v=run_pf_a(c)['products'][0]
        self.assertAlmostEqual(v['origq'][0],base['origq'][0]*.75)
        self.assertAlmostEqual(v['deferredCosts'][0],base['deferredCosts'][0]*.75)
        self.assertAlmostEqual(v['alll'][0],base['alll'][0]*1.5)
        del c['scenario_overlays']
        from .run_q import run_v2
        from .audit_workbook import calculation_audit_workbook
        public=run_v2(c)
        wb=calculation_audit_workbook(c,public)
        self.assertIn('Loan Rollforward',wb.sheetnames)
        self.assertTrue(any('deferredNetBalance' in str(cell.value) for row in wb['Loan Rollforward'] for cell in row))
        self.assertAlmostEqual(base['bal'][1],base['principalBalance'][0]+base['deferredNetBalance'][0])

    def test_disabled_is_inert(self):
        c=config(12);p=c['assumptions']['lending_products'][0];del p['loan_rollforward'];before=copy.deepcopy(c)
        self.assertIsNone(prepare(p,c['assumptions'],{}, {},12,12));self.assertEqual(c,before)
