import copy
import unittest
from foundry.v2.engine_q_a import run_pf_a
from foundry.v2.income_modules import fee_stream_q
from foundry.v2.tests_r405_product_balance_cost import stream
from foundry.v2.tests_portfolio_paydowns import setup

class BeginningBalanceCost(unittest.TestCase):
    def test_measure_and_missing_context(self):
        s=stream('period_begin');s['cost']['params']['pct']=.005
        self.assertAlmostEqual(fee_stream_q(s,1,{'own_balance_begin':1_200_000,'own_balance':2_000_000,'own_balance_end':2_800_000},12)[1],500)
        with self.assertRaises(ValueError): fee_stream_q(s,1,{'own_balance':1},12)

    def test_original_funding_profile_matches_opex_in_months_and_quarters(self):
        original,_=setup()
        moved=copy.deepcopy(original)
        s=stream('period_begin');s['cost']['params']['pct']=.005
        moved['assumptions']['lending_products'][0]['fee_streams']=[s]
        moved['assumptions']['nie_detail']['categories'][0]['linked_components']=[]
        for ppy,n in [(12,36),(4,12)]:
            a=copy.deepcopy(original);b=copy.deepcopy(moved)
            for c in (a,b): c['assumptions'].update(periods_per_year=ppy,n_periods=n)
            old=run_pf_a(a);new=run_pf_a(b)
            self.assertEqual(len(old['is']['pretax']),len(new['is']['pretax']))
            for x,y in zip(old['is']['pretax'],new['is']['pretax']): self.assertAlmostEqual(x,y,places=6)
            p=next(p for p in new['products'] if p['name']=='Scheduled portfolio')
            if ppy==12:
                self.assertEqual(p['passCost'][0],0.0)
                self.assertGreater(p['passCost'][2],0)
            else:
                self.assertGreater(p['passCost'][0],0)

if __name__=='__main__':unittest.main()
