import copy,unittest
from .tests_managed_securities import _cfg
from .securities import (CASH_END_SERIES_ID,prepare_managed_securities,managed_period_snapshot,commit_managed_snapshot,validate_managed_securities)

class CashTargets(unittest.TestCase):
    def config(self):
        c=_cfg();p=c['assumptions']['managed_securities_portfolios'][0]
        p.update(target_source={'series_id':CASH_END_SERIES_ID,'kind':'bank_balance_sheet','timing':'prior_period','prior_initialization':'opening_source'},target_cadence='quarter',target_path='ramp',interest_balance_measure='period_average')
        p['sleeves']=p['sleeves'][:1];s=p['sleeves'][0];s['opening']=92741927
        s['allocation_spec']['value']=1;s['maturity_rate_spec']['value']=0;s['yield_spec']['value']=.043
        return c

    def test_two_quarters_monthly_matches_quarterly_and_ignores_within_quarter_source_changes(self):
        c=self.config();a=c['assumptions'];self.assertEqual(validate_managed_securities(a,6,12),[])
        m=prepare_managed_securities(a,6,12);q=prepare_managed_securities(a,2,4)
        sources=[298391758,999,888,1102916383,777,666]
        totals=[0.,0.]
        for i,source in enumerate(sources):
            before=copy.deepcopy(m)
            r=managed_period_snapshot(m,i+1,{},12,prior_source_values={CASH_END_SERIES_ID:source})
            self.assertEqual(m,before,'solver iterations must not mutate runtime')
            s=r[0]['sleeves'][0];totals[i//3]+=s['interest_income']
            self.assertAlmostEqual(s['starting']-s['maturing']+s['net_purchases'],s['ending'])
            if i==2:self.assertAlmostEqual(s['ending'],89517527.4)
            if i==5:self.assertAlmostEqual(s['ending'],330874914.9)
            commit_managed_snapshot(m,r)
        for i,source in enumerate([sources[0],sources[3]]):
            r=managed_period_snapshot(q,i+1,{},4,prior_source_values={CASH_END_SERIES_ID:source})
            self.assertAlmostEqual(r[0]['sleeves'][0]['interest_income'],totals[i],places=6)
            commit_managed_snapshot(q,r)
        self.assertAlmostEqual(totals[0],979644.5674,places=4)
        self.assertLess(m[0]['sleeves'][0]['net_purchases'][0],0)

    def test_bad_timing_and_missing_named_sources_fail_closed(self):
        c=self.config();p=c['assumptions']['managed_securities_portfolios'][0]
        p['target_source']['timing']='current_period'
        self.assertTrue(validate_managed_securities(c['assumptions'],6,12))
        p['target_source'].update(timing='prior_period',series_id='balance_component.missing.end')
        self.assertTrue(validate_managed_securities(c['assumptions'],6,12))

    def test_full_engine_named_cash_target_and_posting(self):
        from .tests_balance_components import configured,component
        from .engine_q_a import run_pf_a
        c=configured([component('cash-source','cash_allocation',1000000,rate=0,opening_balance=900000)])
        p=self.config()['assumptions']['managed_securities_portfolios'][0]
        p['target_source']['series_id']='balance_component.cash-source.end';p['sleeves'][0]['opening']=200000
        c['assumptions']['managed_securities_portfolios']=[p];c['assumptions']['securities_afs']=[];c['assumptions']['securities_htm']=[]
        self.assertEqual(validate_managed_securities(c['assumptions'],36,12),[])
        r=run_pf_a(c);mp=r['managed_securities'][0]
        self.assertAlmostEqual(mp['sleeves'][0]['ending'][2],270000)
        self.assertAlmostEqual(mp['sleeves'][0]['ending'][5],300000)
        self.assertAlmostEqual(r['bs']['afsBook'][3],270000)
        self.assertAlmostEqual(r['is']['bookInt'][0],mp['sleeves'][0]['interest_income'][0])

if __name__=='__main__':unittest.main()
