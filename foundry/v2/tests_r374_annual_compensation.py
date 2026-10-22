import copy,unittest
from .tests_workforce_additive import _cfg
from .engine_q_a import run_pf_a
from .engine_q_b import run_pf_b
from .annual_compensation import build_plan
from .workforce import normalize_workforce_additive_component


def config(ppy=12):
    c=_cfg(ppy);c['step_0']['modules']=[];a=c['assumptions'];a['lending_products']=[];a['deposit_products']=[]
    a['obs_exposures']=[dict(name='Fee business',call_report_line='obs',notional=1000000000,
                           growth_per_period=0,fee_yield_ann=.06,opex_pct_ann=0,opex_fixed_per_period=0)]
    w=a['nie_detail']['workforce'];w['roles']=[dict(role='Role '+str(i),series_id='role-'+str(i),count=1,
        annual_comp=salary,hire_period=1,payroll_load_rate=.2) for i,salary in enumerate([500000,375000,250000,350000,250000,375000])]
    p=w['additive_components'][0];p.update(allocation='model_year_equal',salary_floor=dict(rate=.3,role_series_ids=['role-'+str(i) for i in range(6)]),payroll_load_rate=.04)
    p['terms'][0]['metric']='fee_income'
    return c


class AnnualCompensationTests(unittest.TestCase):
    def test_full_year_revenue_and_selected_salary_floor(self):
        c=config();before=copy.deepcopy(c);r=run_pf_a(c)
        row=r['workforce']['annual_pool_calculations'][0];self.assertEqual(c,before)
        for y in row['years']:
            self.assertAlmostEqual(y['selected_base_pay'],2100000)
            self.assertAlmostEqual(y['salary_floor'],630000)
            self.assertAlmostEqual(y['band_award'],1000000)
            self.assertAlmostEqual(y['per_period'],1000000*1.04/12)
        self.assertTrue(all(abs(x-1000000*1.04/12)<1e-6 for x in r['workforce']['additive_comp']))
        c['assumptions']['obs_exposures'][0]['fee_yield_ann']=.02
        floor=run_pf_a(c)['workforce']['annual_pool_calculations'][0]
        self.assertAlmostEqual(floor['years'][0]['band_award'],200000)
        self.assertAlmostEqual(floor['amounts'][0],52500*1.04)
        c['assumptions']['nie_detail']['workforce']['roles'][0]['annual_comp']=1000000
        updated=run_pf_a(c)['workforce']['annual_pool_calculations'][0]
        self.assertAlmostEqual(updated['years'][0]['salary_floor'],780000)

    def test_quarterly_both_profiles_and_postings(self):
        for engine in (run_pf_a,run_pf_b):
            c=config(4)
            if engine is run_pf_b:
                import json
                from pathlib import Path
                for k,v in json.loads(Path('foundry/fixtures/parity/configs/pf_b_base.json').read_text())['assumptions'].items():c['assumptions'].setdefault(k,v)
            r=engine(c);row=r['workforce']['annual_pool_calculations'][0]
            self.assertAlmostEqual(row['amounts'][0],260000)
            self.assertAlmostEqual(sum(r['workforce']['additive_comp'][:4]),1040000)
            bare=copy.deepcopy(c);bare['assumptions']['nie_detail']['workforce']['additive_components']=[]
            base=engine(bare)
            self.assertAlmostEqual(sum(r['is']['workforceComp'][:4])-sum(base['is']['workforceComp'][:4]),1040000)

    def test_role_selection_hiring_and_schedule_changes(self):
        c=config();w=c['assumptions']['nie_detail']['workforce'];p=w['additive_components'][0]
        p['salary_floor']['role_series_ids']=['role-0'];w['roles'][0]['hire_period']=7
        w['roles'][0]['compensation_spec']={'source':'entered','trajectory':'explicit','cadence':'year','values':[500000,600000],'extend':'hold'}
        row=run_pf_a(c)['workforce']['annual_pool_calculations'][0]
        self.assertAlmostEqual(row['years'][0]['selected_base_pay'],250000)
        self.assertAlmostEqual(row['years'][1]['selected_base_pay'],600000)

    def test_seven_years_growth_and_crossover(self):
        c=config();a=c['assumptions'];a['n_periods']=84
        a['obs_exposures'][0].update(fee_yield_ann=.02,growth_per_period=.02)
        r=run_pf_a(c);row=r['workforce']['annual_pool_calculations'][0]
        self.assertEqual(len(row['years']),7)
        winners=[]
        for y in range(7):
            rev=sum(r['is']['fees'][y*12:(y+1)*12])
            award=max(630000,.02*max(0,rev-10000000))
            self.assertAlmostEqual(row['years'][y]['award'],award,places=5)
            self.assertTrue(all(abs(v-award*1.04/12)<1e-6 for v in row['amounts'][y*12:(y+1)*12]))
            winners.append(award>630000)
        self.assertFalse(winners[0]);self.assertTrue(winners[-1])

    def test_invalid_and_feedback_guard(self):
        for edit in [lambda p:p['terms'][0].update(source='bank_total_assets'),lambda p:p.update(payroll_load_rate=float('nan')),
                     lambda p:p['salary_floor'].update(role_series_ids=[]),lambda p:p['observation_lag'].update(value=1)]:
            c=config();edit(c['assumptions']['nie_detail']['workforce']['additive_components'][0])
            with self.assertRaises(ValueError):run_pf_a(c)
        c=config();c['assumptions']['n_periods']=13
        with self.assertRaisesRegex(ValueError,'complete model years'):run_pf_a(c)
        c=config();c['assumptions']['nie_detail']['workforce']['additive_components'][0]['salary_floor']['role_series_ids']=['missing']
        with self.assertRaisesRegex(ValueError,'unavailable'):run_pf_a(c)
        c=config();c['assumptions']['nie_detail']['workforce']['additive_components'][0]['terms'][0]['metric']='net_interest_income'
        with self.assertRaisesRegex(ValueError,'feedback dependency'):run_pf_a(c)
        from .annual_compensation import run_with_annual_pools
        calls=[]
        def feedback(cfg,**kwargs):
            calls.append(kwargs)
            return {'workforce':{},'_comp_projection_inputs':{'income_statement_flow_history':{'fee_income':[1000000 if kwargs.get('_comp_probe') else 2000000]*24},'role_base_pay':{'role-'+str(i):[100]*24 for i in range(6)}}}
        with self.assertRaisesRegex(ValueError,'feedback dependency'):run_with_annual_pools(config(),feedback)

    def test_public_audit_and_no_feature_baseline(self):
        from .run_q import run_v2
        from .audit_workbook import calculation_audit_workbook
        c=config();r=run_v2(c);audit=r['workforce']['annual_pool_calculations'][0]
        self.assertEqual(audit['units'],'dollars');self.assertAlmostEqual(audit['years'][0]['award'],1000000)
        wb=calculation_audit_workbook(c,r);rows=list(wb['Workforce Component Detail'].values)
        text=' '.join(str(x) for row in rows for x in row)
        self.assertIn('full_model_year',text);self.assertNotIn('ERROR:',text)
        old=_cfg();a=run_pf_a(old);w=old['assumptions']['nie_detail']['workforce'];w['additive_components'][0].update(allocation='event',payroll_load_rate=0)
        b=run_pf_a(old);self.assertEqual(a,b)
