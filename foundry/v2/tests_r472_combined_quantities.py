import copy, unittest
from .fixed_assets import fixed_asset_formula_level
from .tests_r471_asset_sources import config,component,flat

def path(vals):return {'source':'entered','trajectory':'explicit','cadence':'month','values':vals,'extend':'hold'}
class CombinedQuantities(unittest.TestCase):
    def model(self):
        c=config([component('Grouped asset',flat(10000),1/3,path([49,50,52,53,99,100,102,103,149,150,152,153]))])
        p=c['formula_level']['components'][0];p.update(driver_terms=[{'sign':-1,'driver_spec':flat(3)}],driver_divisor=50,driver_rounding='floor')
        return c
    def test_combine_before_rounding(self):
        c=self.model();before=copy.deepcopy(c);r=fixed_asset_formula_level(c,{},12,12);self.assertEqual(c,before)
        p=r['formula_level']['components'][0]
        self.assertEqual(p['raw_driver'],[46,47,49,50,96,97,99,100,146,147,149,150])
        self.assertEqual(p['driver'],[0,0,0,1,1,1,1,2,2,2,2,3])
        self.assertEqual(p['amount'],[v*10000 for v in p['driver']])
    def test_native_flow_and_stock_aggregation(self):
        c=self.model();m=fixed_asset_formula_level(c,{},12,12)
        for ppy in (1,4):
            q=fixed_asset_formula_level(c,{},ppy,ppy);span=12//ppy
            self.assertEqual(q['gross'],[0]+m['gross'][span::span])
            for i in range(ppy):self.assertAlmostEqual(q['depreciation_expense'][i+1],sum(m['depreciation_expense'][i*span+1:(i+1)*span+1]))
    def test_add_subtract_and_lag_order(self):
        c=self.model();p=c['formula_level']['components'][0];p['driver_terms'].append({'sign':1,'driver_spec':flat(4)});p.update(lag_months=1,initial_driver=100)
        r=fixed_asset_formula_level(c,{},3,12)['formula_level']['components'][0]
        self.assertEqual(r['raw_driver'],[50,51,53]);self.assertEqual(r['driver'],[2,1,1])
    def test_invalid_quantities_fail_closed(self):
        for terms in ([{'sign':0,'driver_spec':flat(3)}],[{'sign':True,'driver_spec':flat(3)}],[{'sign':-1,'driver_spec':flat(1000)}],[{'sign':1,'driver_spec':flat(1)}]*32):
            c=self.model();c['formula_level']['components'][0]['driver_terms']=terms
            with self.assertRaises(ValueError):fixed_asset_formula_level(c,{},12,12)
    def test_linked_sources_resolve_monthly_before_quarter_grouping(self):
        from unittest.mock import patch
        c=self.model();p=c['formula_level']['components'][0]
        def link(sid):return {'source':'link','link':{'kind':'workforce_role_count','series_id':sid}}
        p['driver_spec']=link('total');p['driver_terms']=[{'sign':-1,'driver_spec':link('excluded')}]
        def values(ns,a,n,ppy,*args,**kwargs):return ([49,52,53]*4)[:n] if ns['link']['series_id']=='total' else [3]*n
        with patch('foundry.v2.fixed_assets._monthly_workforce_driver',side_effect=values), patch('foundry.v2.series.resolve_series_spec',side_effect=values):
            r=fixed_asset_formula_level(c,{},4,4)
        self.assertEqual(r['gross'],[0,10000,10000,10000,10000])
        self.assertAlmostEqual(r['depreciation_expense'][1],10000/36)
    def test_no_terms_keeps_existing_output(self):
        c=self.model();p=c['formula_level']['components'][0];del p['driver_terms'];r=fixed_asset_formula_level(c,{},12,12);p['driver_terms']=[]
        self.assertEqual(r,fixed_asset_formula_level(c,{},12,12))
if __name__=='__main__':unittest.main()
