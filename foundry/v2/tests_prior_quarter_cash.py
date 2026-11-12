"""Quarterly income basis derived from cash history, not forecast inputs."""
import copy
import io
import unittest
from .balance_components import BalanceComponents, prior_quarter_average, validate_model
from .tests_balance_components import component, configured
from .engine_q_a import run_pf_a


def cash_component(**changes):
    return component('cash','residual_cash',0.,rate=.12,
        interest_balance_measure='prior_quarter_average',prior_quarter_opening_balance=80.,**changes)


def runtime(ppy=12):
    a={'periods_per_year':ppy,'balance_components_model':{'components':[cash_component()]}}
    b=BalanceComponents(a,{}, {},12,ppy);b.set_opening_cash(100.)
    return b


class PreviousQuarterCashTests(unittest.TestCase):
    def test_monthly_basis_held_within_quarter_ignores_intramonth_path(self):
        b=runtime();basis=[];income=[]
        for i,cash in enumerate([160.,800.,140.,30.,900.,200.,170.,30.,100.]):
            rows,_=b.period(i,{}, {},cash,0.,0.)
            basis.append(rows[0]['interest_balance']);income.append(rows[0]['income']);b.commit(rows)
        self.assertEqual(basis,[90.]*3+[120.]*3+[170.]*3)
        self.assertAlmostEqual(sum(income[:3]),90.*.12/4)
        self.assertEqual(b.audit()['components'][0]['prior_quarter_beginning'],[80.]*3+[100.]*3+[140.]*3)
        self.assertEqual(b.audit()['components'][0]['prior_quarter_ending'],[100.]*3+[140.]*3+[200.]*3)

    def test_monthly_and_quarterly_income_agree(self):
        monthly=runtime();quarterly=runtime(4);mi=[];qi=[]
        for i,cash in enumerate([160.,800.,140.,30.,900.,200.]):
            rows,_=monthly.period(i,{}, {},cash,0.,0.);mi.append(rows[0]['income']);monthly.commit(rows)
        for i,cash in enumerate([140.,200.]):
            rows,_=quarterly.period(i,{}, {},cash,0.,0.);qi.append(rows[0]['income']);quarterly.commit(rows)
        self.assertAlmostEqual(sum(mi[:3]),qi[0]);self.assertAlmostEqual(sum(mi[3:]),qi[1])

    def test_current_period_cash_does_not_change_current_income(self):
        b=runtime()
        x,_=b.period(0,{}, {},100.,0.,0.);y,_=b.period(0,{}, {},1000000.,0.,0.)
        self.assertEqual(x[0]['income'],y[0]['income'])
        self.assertEqual(b.rows['cash']['ending'],[])  # solver previews are not committed

    def test_historical_boundary_used_only_in_first_quarter(self):
        hist=[160.,800.,140.,30.,900.,200.]
        first=prior_quarter_average(100.,80.,[],0,12)[0]
        changed=prior_quarter_average(100.,20.,[],0,12)[0]
        self.assertNotEqual(first,changed)
        self.assertEqual(prior_quarter_average(100.,80.,hist,6,12),prior_quarter_average(100.,20.,hist,6,12))

    def test_history_and_cadence_are_required(self):
        for value in (None,'80',True,-1.,float('nan'),float('inf')):
            c=cash_component();c['prior_quarter_opening_balance']=value
            with self.subTest(value=value),self.assertRaisesRegex(ValueError,'beginning balance'):
                validate_model({'periods_per_year':12,'balance_components_model':{'components':[c]}})
        c=cash_component();del c['prior_quarter_opening_balance']
        with self.assertRaises(ValueError):validate_model({'balance_components_model':{'components':[c]}})
        with self.assertRaises(ValueError):prior_quarter_average(100.,80.,[],0,1)
        with self.assertRaises(ValueError):prior_quarter_average(100.,80.,[],3,12)

    def test_explicit_zero_history_is_valid(self):
        c=cash_component();c['prior_quarter_opening_balance']=0.
        validate_model({'balance_components_model':{'components':[c]}})
        self.assertEqual(prior_quarter_average(100.,0.,[],0,12)[0],50.)

    def test_reject_non_cash_and_independent_income_balance(self):
        for change in ({'treatment':'off_book'},{'income_method':'separate_balance_yield'}):
            c=cash_component();c.update(change)
            with self.subTest(change=change),self.assertRaises(ValueError):
                validate_model({'balance_components_model':{'components':[c]}})

    def test_new_measure_does_not_change_opening_cash_or_equity(self):
        c=configured([cash_component()]);original=copy.deepcopy(c)
        q=run_pf_a(c);control=copy.deepcopy(c)
        control['assumptions']['balance_components_model']['components'][0]['interest_balance_measure']='prior_end'
        base=run_pf_a(control)
        self.assertEqual(c,original)
        for key in ('cash','equity','paidIn','totalAssets','borrow'):
            self.assertEqual(q['bs'][key][0],base['bs'][key][0])
        self.assertAlmostEqual(q['balance_components']['components'][0]['interest_balance'][0],(80.+q['bs']['cash'][0])/2)

    def test_exact_audit_and_public_units(self):
        from .run_q import run_v2
        from .audit_workbook import calculation_audit_workbook
        from openpyxl import load_workbook
        c=configured([cash_component()]);r=run_v2(c)
        row=r['balance_components']['components'][0]
        self.assertEqual(row['prior_quarter_beginning'][0],.08)
        buf=io.BytesIO();calculation_audit_workbook(c,r).save(buf);buf.seek(0)
        sheet=load_workbook(buf,data_only=True)['Balance Components']
        rows={x[1]:x for x in list(sheet.values)[4:]}
        self.assertEqual(rows['Previous-quarter beginning balance'][4],.08)
        self.assertAlmostEqual(rows['Balance used for pricing'][4],(row['opening']+.08)/2,places=5)


if __name__=='__main__':unittest.main()
