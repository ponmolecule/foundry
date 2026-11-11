"""r485: Loan production origination source "Linked deposit balance x percentage".

originations[t] = observed deposit balance[t] x percentage[t] x rate periods/yr / model periods/yr,
fed into the existing loan-production ledger (repayments, charge-offs, allowance, deferred costs).
"""
import copy
import json
import unittest
from pathlib import Path

from .tests_r369_lending_contracts import config
from .lending_contracts import flat
from .engine_q_a import run_pf_a

PCT = 0.01176471   # 1.176471% per month (acceptance case)


def linked(n=24, ppy=12, measure='period_end', period='month', pct=PCT):
    c = config(n, ppy); a = c['assumptions']
    d = a['deposit_products'][0]
    d['name'] = 'Portfolio Partnerships'; d['source_catalog_id'] = 'dep-portfolio-partnerships'
    x = a['lending_products'][0]['loan_rollforward']
    x.update(source='deposit_balance', deposit_id='dep-portfolio-partnerships', balance_measure=measure,
             percentage_spec=flat(pct), percentage_period=period)
    x['deferred'].update(basis='percent_funded', cost_spec=flat(.005), fee_spec=flat(.001))
    return c


def product(r, name):
    return next(p for p in r['products'] if p['name'] == name)


def deposit_paths(r, n):
    d = product(r, 'Portfolio Partnerships')
    bal = d['bal']                      # raw engine: opening + n period ends
    avg = d.get('avg') or [(bal[i] + bal[i + 1]) / 2 for i in range(n)]
    return {'period_begin': bal[:n], 'period_end': bal[1:n + 1], 'period_average': avg[:n]}


class LinkedDepositOriginations(unittest.TestCase):
    def assertSeq(self, a, b, places=6):
        self.assertEqual(len(a), len(b))
        for x, y in zip(a, b):
            self.assertAlmostEqual(x, y, places=places)

    def test_acceptance_ending_balance_monthly(self):
        c = linked(); r = run_pf_a(c); loan = r['products'][0]
        end = deposit_paths(r, 24)['period_end']
        self.assertSeq(loan['origq'], [b * PCT for b in end])
        self.assertSeq(loan['linkedSourceBalance'], end)
        self.assertSeq(loan['linkedPercentage'], [PCT] * 24, 12)
        self.assertSeq(loan['linkedEffectivePercentage'], [PCT] * 24, 12)
        self.assertSeq(loan['linkedOriginations'], loan['origq'])
        src = loan['loanProductionSource']
        self.assertEqual((src['deposit_id'], src['balance_measure'], src['percentage_period'],
                          src['rate_periods_per_year'], src['model_periods_per_year']),
                         ('dep-portfolio-partnerships', 'period_end', 'month', 12, 12))
        self.assertEqual(src['deposit_name'], 'Portfolio Partnerships')

    def test_deposit_change_changes_originations_immediately(self):
        c = linked(); base = run_pf_a(copy.deepcopy(c))['products'][0]['origq']
        c['assumptions']['deposit_products'][0]['opening_balance'] *= 2
        r = run_pf_a(c); loan = r['products'][0]
        self.assertSeq(loan['origq'], [b * PCT for b in deposit_paths(r, 24)['period_end']])
        self.assertGreater(loan['origq'][0], base[0] * 1.2)

    def test_all_balance_measures(self):
        for m in ('period_begin', 'period_end', 'period_average'):
            r = run_pf_a(linked(measure=m)); loan = r['products'][0]
            obs = deposit_paths(r, 24)[m]
            self.assertSeq(loan['linkedSourceBalance'], obs)
            self.assertSeq(loan['origq'], [b * PCT for b in obs])
        r = run_pf_a(linked(measure='period_begin'))
        self.assertAlmostEqual(r['products'][0]['linkedSourceBalance'][0],
                               linked()['assumptions']['deposit_products'][0]['opening_balance'])

    def test_rate_period_conversion(self):
        for ppy, n in ((12, 24), (4, 8)):   # Profile A runs monthly or quarterly
            month = run_pf_a(linked(n, ppy, period='month', pct=.01))['products'][0]
            quarter = run_pf_a(linked(n, ppy, period='quarter', pct=.03))['products'][0]
            year = run_pf_a(linked(n, ppy, period='year', pct=.12))['products'][0]
            self.assertSeq(month['linkedEffectivePercentage'], [.01 * 12 / ppy] * n, 12)
            self.assertSeq(quarter['linkedEffectivePercentage'], [.03 * 4 / ppy] * n, 12)
            self.assertSeq(year['linkedEffectivePercentage'], [.12 / ppy] * n, 12)
            self.assertSeq(month['origq'], quarter['origq'], 4)
            self.assertSeq(month['origq'], year['origq'], 4)
            self.assertEqual(month['loanProductionSource']['model_periods_per_year'], ppy)

    def test_changing_percentage_schedules(self):
        c = linked(); x = c['assumptions']['lending_products'][0]['loan_rollforward']
        x['percentage_spec'] = {'source': 'entered', 'trajectory': 'explicit', 'cadence': 'year',
                                'values': [.01, .02], 'resolution': 'step'}
        r = run_pf_a(c); loan = r['products'][0]; end = deposit_paths(r, 24)['period_end']
        self.assertSeq(loan['origq'], [b * (.01 if i < 12 else .02) for i, b in enumerate(end)])
        x['percentage_spec'] = {'source': 'entered', 'trajectory': 'explicit', 'cadence': 'month',
                                'values': [.001 * (i + 1) for i in range(24)]}
        r = run_pf_a(c); loan = r['products'][0]; end = deposit_paths(r, 24)['period_end']
        self.assertSeq(loan['origq'], [b * .001 * (i + 1) for i, b in enumerate(end)])
        # r482/r484: a short schedule blocks and names the component; nothing is padded.
        x['percentage_spec'] = {'source': 'entered', 'trajectory': 'explicit', 'cadence': 'year', 'values': [.01]}
        from .run_q import run_v2
        with self.assertRaises(ValueError) as e:
            run_v2(copy.deepcopy(c))
        self.assertIn('percentage', str(e.exception)); self.assertIn('Y2 missing', str(e.exception))
        self.assertIn("Lending '", str(e.exception))

    def test_stable_id_after_rename_and_reorder(self):
        c = linked(); before = run_pf_a(copy.deepcopy(c))['products'][0]['origq']
        deps = c['assumptions']['deposit_products']
        deps[0]['name'] = 'Partnerships (renamed)'
        deps.append(deps.pop(0))
        r = run_pf_a(c); loan = r['products'][0]
        self.assertSeq(loan['origq'], before)
        self.assertEqual(loan['loanProductionSource']['deposit_name'], 'Partnerships (renamed)')

    def test_invalid_sources_fail_without_zero(self):
        def bad(edit, msg):
            c = linked(); edit(c['assumptions'])
            with self.assertRaisesRegex(ValueError, msg):
                run_pf_a(c)
        x = lambda a: a['lending_products'][0]['loan_rollforward']
        bad(lambda a: x(a).update(deposit_id=''), 'requires a deposit product')
        bad(lambda a: x(a).pop('deposit_id'), 'requires a deposit product')
        bad(lambda a: x(a).update(deposit_id='nope'), 'does not match')
        bad(lambda a: a['deposit_products'][1].update(source_catalog_id='dep-portfolio-partnerships'), 'more than one')
        bad(lambda a: (a['lending_products'][0].update(source_catalog_id='loan-x'), x(a).update(deposit_id='loan-x')), 'lending balance')
        bad(lambda a: x(a).update(deposit_id='bank.deposits'), 'not a total or retention pool')
        bad(lambda a: x(a).update(deposit_id='deposit_pool.p1.retainedBalance'), 'not a total or retention pool')
        bad(lambda a: (a.update(deposit_retention_pools=[{'id': 'pool-1'}]), x(a).update(deposit_id='pool-1')), 'retention pool')
        bad(lambda a: a['deposit_products'][0].update(retention_pool_id='pool-1'), 'retention-pool deposit')
        bad(lambda a: x(a).pop('balance_measure'), 'beginning, ending or average')
        bad(lambda a: x(a).update(balance_measure='peak'), 'beginning, ending or average')
        bad(lambda a: x(a).pop('percentage_period'), 'Month, Quarter or Year')
        bad(lambda a: x(a).update(percentage_period='week'), 'Month, Quarter or Year')
        bad(lambda a: x(a).update(percentage_spec=flat(-.01)), 'invalid nonnegative')
        bad(lambda a: x(a).update(percentage_spec=flat(float('nan'))), 'invalid nonnegative')
        bad(lambda a: x(a).pop('percentage_spec'), 'requires an entered Series')

    def test_scenario_haircut_and_accounting_preserved(self):
        c = linked(); base = run_pf_a(copy.deepcopy(c)); b = base['products'][0]
        c['scenario_overlays'] = {'origination_volume_haircut': .25, 'charge_off_mult': 2, 'reserve_mult': 2}
        r = run_pf_a(c); v = r['products'][0]; end = deposit_paths(r, 24)['period_end']
        self.assertSeq(v['origq'], [e * PCT * .75 for e in end])
        self.assertEqual(v['loanProductionSource']['volume_multiplier'], .75)
        self.assertSeq(v['linkedSourceBalance'], end)
        # Ledger identities per period; charge-offs are applied, never suppressed.
        p = c['assumptions']['lending_products'][0]; co_ann = p['charge_off_ann'] * 2
        x = p['loan_rollforward']; beg = 0.; allow = 0.
        for i in range(24):
            pay, pre = beg * .05 / 12, beg * .05 / 12; co = beg * co_ann / 12
            end_i = beg + v['origq'][i] - pay - pre - co
            self.assertAlmostEqual(v['principalPayments'][i], pay, 6)
            self.assertAlmostEqual(v['co'][i], co, 6)
            self.assertAlmostEqual(v['principalBalance'][i], end_i, 4)
            self.assertAlmostEqual(v['provision'][i], end_i * .0161 * 2 - allow + co, 4)
            self.assertAlmostEqual(v['deferredCosts'][i], v['origq'][i] * .005, 6)
            beg, allow = end_i, end_i * .0161 * 2
        self.assertGreater(sum(v['co']), 0)

    def test_public_and_audit_scaling(self):
        from .run_q import run_v2
        from .audit_workbook import calculation_audit_workbook
        c = linked(); raw = run_pf_a(copy.deepcopy(c))['products'][0]
        pub = run_v2(copy.deepcopy(c)); pl = pub['products'][0]
        self.assertSeq(pl['linkedSourceBalance'], [v / 1000 for v in raw['linkedSourceBalance']])
        self.assertSeq(pl['linkedOriginations'], [v / 1000 for v in raw['linkedOriginations']])
        self.assertSeq(pl['detailExact']['linkedSourceBalance'], [v / 1000 for v in raw['linkedSourceBalance']])
        self.assertSeq(pl['linkedPercentage'], raw['linkedPercentage'], 12)
        self.assertSeq(pl['linkedEffectivePercentage'], raw['linkedEffectivePercentage'], 12)
        self.assertEqual(pl['loanProductionSource']['percentage_period'], 'month')
        wb = calculation_audit_workbook(c, pub); ws = wb['Loan Rollforward']
        rows = {r[2]: r for r in ws.iter_rows(values_only=True) if r and r[2]}
        self.assertAlmostEqual(rows['linkedSourceBalance'][4], raw['linkedSourceBalance'][0] / 1000, 6)
        self.assertAlmostEqual(rows['linkedOriginations'][4], raw['linkedOriginations'][0] / 1000, 6)
        self.assertAlmostEqual(rows['linkedPercentage'][4], PCT, 12)
        self.assertAlmostEqual(rows['linkedEffectivePercentage'][4], PCT, 12)
        self.assertIn('$000s', rows['linkedSourceBalance'][3])
        self.assertIn('fraction per month', rows['linkedPercentage'][3])
        self.assertIn('× 12 ÷ 12', rows['linkedEffectivePercentage'][3])

    def test_existing_products_unchanged(self):
        # Other origination sources do not publish the linked fields and run as before.
        c = config(12, 12); r = run_pf_a(c)['products'][0]
        self.assertNotIn('loanProductionSource', r); self.assertNotIn('linkedSourceBalance', r)
        root = Path(__file__).resolve().parents[2]
        bank = json.loads((root / 'foundry/fixtures/universal_template_bank.json').read_text())
        out = run_pf_a(bank)
        self.assertFalse(any('loanProductionSource' in p for p in out['products']))


if __name__ == '__main__':
    import sys
    res = unittest.main(exit=False, verbosity=2).result
    print(('PASS' if res.wasSuccessful() else 'FAIL') + f' r485 linked deposit originations: {res.testsRun} tests')
    sys.exit(0 if res.wasSuccessful() else 1)
