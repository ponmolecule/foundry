"""A funding deficit must remain visible until financing is explicitly authored."""
import copy
import io
import json
import unittest
from pathlib import Path

from .engine_q_a import run_pf_a
from .engine_q_b import run_pf_b
from .funding import funding_diagnostics
from .validate_q import validate_errors_v2


def config(profile='pf_a'):
    name = 'universal_template_bank.json' if profile == 'pf_a' else 'parity/configs/pf_b_base.json'
    c = json.loads((Path('foundry/fixtures') / name).read_text())
    c['target_state']['initial_capital'] = 1000000.
    c['pre_opening'] = {'expenses': []}
    c['step_0']['modules'] = []
    a = c['assumptions']
    for key in ('lending_products', 'deposit_products', 'obs_exposures', 'securities_afs',
                'securities_htm', 'managed_securities_portfolios', 'capital_raises', 'scheduled_borrowings'):
        a[key] = []
    for key in ('premises_equipment', 'intangibles', 'other_assets', 'other_liabilities',
                'cash_yield', 'securities_yield', 'overhead_per_period', 'cash_target_pct_deposits'):
        a[key] = 0
    for key in ('nie_detail', 'interest_balance_model', 'balance_components_model', 'fixed_assets',
                'other_liabilities_model', 'other_assets_model', 'cost_pools', 'cac_feeds', 'fee_modules'):
        a.pop(key, None)
    a['surplus_allocation_policy'] = 'cash'
    return c


class FundingPolicyTests(unittest.TestCase):
    def test_default_shortfall_never_creates_debt_in_either_profile(self):
        for profile, run in [('pf_a', run_pf_a), ('pf_b', run_pf_b)]:
            c = config(profile)
            c['assumptions']['securities_afs'] = [{'name':'Authored assets', 'opening':1500000., 'yield_ann':0.}]
            r = run(c)
            self.assertEqual(r['funding']['cash_position'][0], -500000.)
            self.assertFalse(r['funding']['feasible'])
            self.assertEqual(r['funding']['first_shortfall_period'], 0)
            self.assertTrue(all(v == 0 for v in r['funding']['automatic_borrowing']))
            self.assertEqual(r['funding']['max_cash_shortfall'], 500000.)

    def test_automatic_borrowing_requires_explicit_opt_in(self):
        for profile, run in [('pf_a', run_pf_a), ('pf_b', run_pf_b)]:
            c = config(profile)
            c['assumptions'].update(funding_shortfall_policy='automatic_borrowing',
                securities_afs=[{'name':'Assets', 'opening':1500000., 'yield_ann':0.}])
            r = run(c)
            self.assertEqual(r['funding']['cash_position'][0], 0)
            self.assertEqual(r['funding']['automatic_borrowing'][0], 500000.)
            self.assertTrue(r['funding']['feasible'])

    def test_deficit_does_not_earn_negative_cash_interest(self):
        c = config(); c['assumptions']['cash_yield'] = .12
        c['assumptions']['securities_afs'] = [{'name':'Assets','opening':1500000.,'yield_ann':0.}]
        r = run_pf_a(c)
        self.assertTrue(all(v == 0 for v in r['is']['cashInt']))

    def test_later_operating_loss_exposes_first_forecast_shortfall(self):
        c = config(); c['assumptions']['overhead_per_period'] = 600000.
        r = run_pf_a(c)
        self.assertEqual(r['funding']['first_shortfall_period'], 2)
        self.assertTrue(all(v == 0 for v in r['bs']['borrow']))
        self.assertLess(r['bs']['cash'][2], 0)

    def test_scheduled_financing_remains_separate(self):
        c = config()
        c['assumptions']['scheduled_borrowings'] = [{'name':'Entered facility','amount':600000.,'quarter':1,'term_q':4,'rate_ann':.04}]
        r = run_pf_a(c)
        self.assertTrue(all(v == 0 for v in r['bs']['borrow']))
        self.assertGreater(max(r['funding']['scheduled_borrowing']), 0)

    def test_positive_cash_can_breach_an_authored_requirement(self):
        d = funding_diagnostics('show_shortfall', [100., 50.], [0., 80.], [0.,0.], [0.,0.], 12)
        self.assertEqual(d['cash_shortfall'], [0.,30.])
        self.assertEqual(d['unfunded_cash'], [0.,0.])
        self.assertEqual(d['first_shortfall_period'], 1)

    def test_signed_cash_preserves_accounting_identity_without_equity_plug(self):
        c = config(); c['assumptions']['securities_afs'] = [{'name':'Assets','opening':1500000.,'yield_ann':0.}]
        r = run_pf_a(c); b = r['bs']
        for i in range(len(b['cash'])):
            self.assertAlmostEqual(b['totalAssets'][i], b['deposits'][i]+b['equity'][i]+b['borrow'][i]+b['borrowSched'][i], places=5)
        self.assertTrue(all(x == 1000000. for x in b['paidIn']))
        for equity, paid, retained, aoci in zip(b['equity'], b['paidIn'], b['re'], b['aoci']):
            self.assertAlmostEqual(equity, paid + retained + aoci, places=5)

    def test_impossible_cash_allocation_is_flagged_and_not_financed(self):
        from .tests_balance_components import configured, component
        c = configured([component('requested','cash_allocation',1e9,rate=0.,opening_balance=0.)])
        r = run_pf_a(c)
        self.assertFalse(r['funding']['feasible'])
        self.assertTrue(all(v == 0 for v in r['bs']['borrow']))
        row = r['balance_components']['components'][0]
        self.assertLess(row['ending'][0], 1e9)

    def test_monthly_and_quarterly_shortfalls_keep_native_period_index(self):
        for ppy in (12, 4):
            c = config(); c['assumptions'].update(periods_per_year=ppy, n_periods=ppy*3,
                securities_afs=[{'name':'Assets','opening':1500000.,'yield_ann':0.}])
            r = run_pf_a(c)
            self.assertEqual(len(r['funding']['cash_shortfall']), ppy*3+1)
            self.assertEqual(r['funding']['periods_per_year'], ppy)
            self.assertEqual(r['funding']['first_shortfall_period'], 0)
            self.assertTrue(all(v == 0 for v in r['bs']['borrow']))

    def test_scenario_constraints_do_not_pass_an_unfunded_plan(self):
        from .run_q import run_v2
        c = config(); c['assumptions']['securities_afs'] = [{'name':'Assets','opening':1500000.,'yield_ann':0.}]
        r = run_v2(c)
        self.assertFalse(r['scenarios']['base']['funding_feasible'])
        self.assertTrue(any(t['key']=='funding_cash_requirement' and t['scenario']=='base' and not t['pass'] for t in r['constraint_tests']))

    def test_automatic_mode_is_disclosed_in_public_flags(self):
        from .run_q import run_v2
        c = config(); c['assumptions'].update(funding_shortfall_policy='automatic_borrowing',
            securities_afs=[{'name':'Assets','opening':1500000.,'yield_ann':0.}])
        r = run_v2(c)
        self.assertTrue(any(f['id']=='MOD-AUTOMATIC-BORROWING' for f in r['flags']))

    def test_funding_policy_workbook_roundtrip(self):
        from .fiw import build_fiw, diff_import
        from openpyxl import load_workbook
        c = config(); data, _ = build_fiw(c); w = load_workbook(io.BytesIO(data))
        for row in w['CONTROL']:
            if row[0].value == 'Funding shortfall policy': row[1].value = 'automatic_borrowing'
        buf = io.BytesIO(); w.save(buf)
        merged, _ = diff_import(buf.getvalue(), c)
        self.assertEqual(merged['assumptions']['funding_shortfall_policy'], 'automatic_borrowing')

    def test_unallocated_negative_cash_never_earns_negative_income(self):
        from .tests_balance_components import configured, component
        c = configured([component('asset','earning_asset',1e12,rate=0.)])
        c['assumptions']['cash_yield'] = .12
        r = run_pf_a(c)
        self.assertLess(r['bs']['cash'][1], 0)
        self.assertTrue(all(x >= 0 for x in r['is']['cashInt']))
        self.assertTrue(all(x == 0 for x in r['is']['cashInt'][1:]))

    def test_requested_allocations_keep_all_periods_in_audit(self):
        from .balance_components import BalanceComponents
        from .tests_balance_components import component
        c = component('allocation','cash_allocation',100.,rate=.12)
        b = BalanceComponents({'balance_components_model':{'components':[c]}}, {}, {}, 3, 12)
        b.allow_cash_shortfall = True
        for i, available in enumerate([200., 50., 200.]):
            rows, _ = b.period(i, {}, {'allocation':100.}, available, 0., 0.)
            b.commit(rows)
        row = b.audit()['components'][0]
        self.assertEqual(row['requested_balance'], [100.,100.,100.])
        self.assertEqual(row['ending'], [100.,50.,100.])

    def test_invalid_policy_is_rejected(self):
        c = config(); c['assumptions']['funding_shortfall_policy'] = 'hidden_plug'
        self.assertTrue(any('funding_shortfall_policy' in str(e) for e in validate_errors_v2(c)))

    def test_public_results_flags_and_exact_audit_expose_shortfall(self):
        from .run_q import run_v2
        from .audit_workbook import calculation_audit_workbook
        from openpyxl import load_workbook
        c = config(); c['assumptions']['securities_afs'] = [{'name':'Assets','opening':1500000.,'yield_ann':0.}]
        r = run_v2(c)
        self.assertEqual(r['funding']['max_cash_shortfall'], 500000.)
        self.assertTrue(any(f['id']=='MOD-FUNDING-SHORTFALL' for f in r['flags']))
        buf = io.BytesIO(); calculation_audit_workbook(c,r).save(buf); buf.seek(0)
        sheet = load_workbook(buf,data_only=True)['Funding Diagnostics']
        self.assertEqual(sheet.cell(4,5).value, 'Open')
        self.assertEqual(sheet.cell(5,5).value, -500.)


if __name__ == '__main__':
    unittest.main()
