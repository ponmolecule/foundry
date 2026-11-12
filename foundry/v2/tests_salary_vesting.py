import copy
import unittest
from .vesting_compensation import normalize, build
from .tests_r374_annual_compensation import config
from .engine_q_a import run_pf_a
from .engine_q_b import run_pf_b


def pool():
    return dict(driver='salary_vesting', component_id='lti', name='Deferred awards',
                role_series_ids=['role-0'], award_rate=.3, cliff_years=1, vesting_years=4,
                historical_awards=[dict(model_year=0, amount=80000)])


class SalaryVestingTests(unittest.TestCase):
    def test_cliff_four_installments_and_expiry(self):
        c=normalize(pool(),12)
        r=build(c,{'role-0':[10000]*72},72,12)
        self.assertEqual([y['expense'] for y in r['years']], [20000,29000,38000,47000,36000,36000])
        self.assertEqual([x['award_year'] for x in r['years'][4]['cohorts']],[1,2,3,4])
        self.assertEqual(sum(r['amounts'][:12]),20000)

    def test_older_cohort_and_longer_cliff(self):
        c=pool();c.update(cliff_years=2,historical_awards=[dict(model_year=-1,amount=80000)])
        r=build(normalize(c,4),{'role-0':[30000]*24},24,4)
        self.assertEqual(r['years'][0]['expense'],20000)
        self.assertEqual(r['years'][1]['expense'],20000)
        self.assertEqual(r['years'][2]['expense'],29000)

    def test_month_quarter_aggregation(self):
        c=normalize(pool(),12);m=build(c,{'role-0':[10000]*60},60,12)
        q=build(c,{'role-0':[30000]*20},20,4)
        for i,v in enumerate(q['amounts']):self.assertAlmostEqual(v,sum(m['amounts'][i*3:i*3+3]))

    def test_validation(self):
        for key,value in [('role_series_ids',[]),('award_rate',float('nan')),('cliff_years',0),('vesting_years',1.5),('historical_awards',None)]:
            c=pool();c[key]=value
            with self.assertRaises(ValueError):normalize(c,12)
        c=pool();del c['historical_awards']
        with self.assertRaises(ValueError):normalize(c,12)
        c=pool();c['historical_awards']=[dict(model_year=1,amount=100)]
        with self.assertRaises(ValueError):normalize(c,12)
        with self.assertRaises(ValueError):build(normalize(pool(),12),{},60,12)

    def test_both_engines_post_once_preserve_counts_and_opening(self):
        for engine in (run_pf_a,run_pf_b):
            c=config(4)
            if engine is run_pf_b:
                import json
                from pathlib import Path
                for k,v in json.loads(Path('foundry/fixtures/parity/configs/pf_b_base.json').read_text())['assumptions'].items():c['assumptions'].setdefault(k,v)
            wf=c['assumptions']['nie_detail']['workforce'];wf['additive_components']=[]
            base=engine(c);wf['additive_components']=[pool()];before=copy.deepcopy(c)
            r=engine(c);self.assertEqual(c,before)
            self.assertEqual(r['workforce']['counts'],base['workforce']['counts'])
            plan=r['workforce']['annual_pool_calculations'][0]
            self.assertEqual(plan['years'][0]['award'],150000) # 500k base; excludes 20% load.
            self.assertEqual(plan['years'][1]['expense'],57500)
            for i,v in enumerate(plan['amounts']):
                self.assertAlmostEqual(r['is']['workforceComp'][i]-base['is']['workforceComp'][i],v)
            if engine is run_pf_a:
                for key in r['bs']:
                    if isinstance(r['bs'][key],list):self.assertEqual(r['bs'][key][0],base['bs'][key][0])

    def test_selected_pay_hiring_and_salary_edits(self):
        c=config(12);c['assumptions']['n_periods']=36
        wf=c['assumptions']['nie_detail']['workforce'];wf['additive_components']=[pool()]
        wf['roles'][0]['hire_period']=7
        r=run_pf_a(c)['workforce']['annual_pool_calculations'][0]
        self.assertAlmostEqual(r['years'][0]['selected_base_pay'],250000)
        self.assertAlmostEqual(r['years'][1]['expense'],38750)
        wf['roles'][0]['annual_comp']=1000000
        r=run_pf_a(c)['workforce']['annual_pool_calculations'][0]
        self.assertAlmostEqual(r['years'][1]['expense'],57500)

    def test_explicit_no_history_and_zero_salary(self):
        c=pool();c['historical_awards']=[]
        r=build(normalize(c,12),{'role-0':[0]*60},60,12)
        self.assertEqual(r['amounts'],[0]*60)

    def test_public_result_and_audit_evidence(self):
        from .run_q import run_v2
        from .audit_workbook import calculation_audit_workbook
        c=config();c['assumptions']['nie_detail']['workforce']['additive_components']=[pool()]
        r=run_v2(c)
        self.assertAlmostEqual(r['workforce']['additive_components'][0]['amounts'][0],20000/12/1000,places=2)
        plan=r['workforce']['annual_pool_calculations'][0]
        self.assertEqual(plan['units'],'dollars')
        self.assertEqual(plan['years'][0]['cohorts'][0]['award_year'],0)
        wb=calculation_audit_workbook(c,r)
        text=' '.join(str(v) for row in wb['Workforce Component Detail'].values for v in row)
        self.assertIn('award_cohorts',text)
        self.assertIn('cliff=1 years; duration=4 years',text)
        self.assertNotIn('ERROR:',text)
