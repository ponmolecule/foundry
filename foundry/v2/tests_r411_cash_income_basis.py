"""A separately specified accrual balance prices cash without booking another asset."""
import copy
import unittest
from .tests_balance_components import configured,component,flat
from .balance_components import BalanceComponents

class CashIncomeBasis(unittest.TestCase):
    def runtime(self,c,n=3,ppy=12):
        return BalanceComponents(configured([c])['assumptions'],{},{},n,ppy)

    def test_source_quarter_and_rate_changes(self):
        c=component('cash','cash_allocation',1_102_916_383,rate=.039,
                    opening_balance=298_391_758,income_method='separate_balance_yield',
                    income_balance_spec=flat((309_139_757+298_391_758)/2,'money'))
        m=self.runtime(c);total=0
        for i in range(3):
            stocks=m.stocks(i,{})
            rows,unassigned=m.period(i,{},stocks,stocks['cash'],0,stocks['cash'])
            self.assertEqual(rows[0]['ending'],1_102_916_383)
            self.assertEqual(rows[0]['income_basis'],303_765_757.5)
            self.assertEqual(unassigned,0)
            total+=rows[0]['income'];m.commit(rows)
        self.assertAlmostEqual(total,2_961_716.135625,places=6)
        q=self.runtime(c,n=1,ppy=4)
        rows,_=q.period(0,{},q.stocks(0,{}),1_102_916_383,0,298_391_758)
        self.assertAlmostEqual(rows[0]['income'],total,places=6)
        c['yield_spec']=flat(.04,'rate')
        changed=self.runtime(c);rows,_=changed.period(0,{},changed.stocks(0,{}),1_102_916_383,0,298_391_758)
        self.assertAlmostEqual(rows[0]['income'],303_765_757.5*.04/12)
        self.assertEqual(rows[0]['ending'],1_102_916_383)

    def test_missing_basis_caps_and_residual_rejected(self):
        base=component('cash','cash_allocation',100,rate=.04,income_method='separate_balance_yield',income_balance_spec=flat(90,'money'))
        for change in ({'income_balance_spec':None},{'cap_at_available_cash':True},{'treatment':'residual_cash'}):
            c=copy.deepcopy(base);c.update(change)
            with self.assertRaises(ValueError):self.runtime(c)

    def test_engine_posts_income_once_and_no_separate_asset(self):
        from .engine_q_a import run_pf_a
        c=component('cash','cash_allocation',100,rate=.039,income_method='separate_balance_yield',income_balance_spec=flat(303_765_757.5,'money'))
        cfg=configured([c]);cfg['assumptions']['cash_yield']=0
        result=run_pf_a(copy.deepcopy(cfg))
        self.assertEqual(result['bs']['earningAssets'][1],0)
        rows=result['balance_components']['components'][0]
        self.assertEqual(rows['ending'][0],100)
        self.assertAlmostEqual(rows['income'][0],987_238.711875,places=6)
        self.assertAlmostEqual(result['is']['cashInt'][0],rows['income'][0],places=6)

    def test_legacy_cash_unchanged(self):
        c=component('cash','cash_allocation',120,rate=.12,opening_balance=100,interest_balance_measure='average')
        m=self.runtime(c);rows,_=m.period(0,{},m.stocks(0,{}),120,0,100)
        self.assertAlmostEqual(rows[0]['income'],1.1)

if __name__=='__main__':unittest.main()
