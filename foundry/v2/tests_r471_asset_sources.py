import copy
import unittest
from .fixed_assets import fixed_asset_formula_level
from .parity import _conv_fixed_assets


def flat(v):return {'source':'entered','trajectory':'flat','value':v}
def component(name,amount,rate,driver=None):
    return dict(component_id=name,name=name,driver_spec=driver or flat(1),multiplier_spec=amount,
                depreciation_rate_spec={**flat(rate),'period':'year'})
def config(parts):
    return {'mode':'formula_level','formula_level':dict(level_basis='gross',opening_level=0,
        base_spec=flat(0),components=parts,depreciation={'kind':'component_rates','base_rate_spec':{**flat(0),'period':'year'}})}

class AssetSources(unittest.TestCase):
    def test_independent_levels_and_rates(self):
        c=config([component('Buildings',flat(120000),.1),component('Equipment',flat(36000),1/3)])
        before=copy.deepcopy(c);r=fixed_asset_formula_level(c,{},12,12)
        self.assertEqual(c,before)
        self.assertEqual(r['gross'][1:], [156000]*12)
        self.assertEqual(r['depreciation_expense'][1:],[2000]*12)
        self.assertEqual(r['net'][-1],132000)

    def test_quantity_growth_and_grouping(self):
        c=config([component('Branches',flat(10000),.2,{'source':'entered','trajectory':'explicit','cadence':'month','values':[1,2,3],'extend':'hold'})])
        r=fixed_asset_formula_level(c,{},3,12)
        self.assertEqual(r['gross'][1:],[10000,20000,30000])
        c['formula_level']['components'][0].update(lag_months=1,initial_driver=4,driver_divisor=2,driver_rounding='ceil')
        self.assertEqual(fixed_asset_formula_level(c,{},3,12)['gross'][1:],[20000,10000,10000])

    def test_asset_growth_and_schedule_cadence(self):
        path={'source':'entered','trajectory':'explicit','cadence':'year','values':[120000,240000],'extend':'hold','resolution':'step'}
        c=config([component('Building',path,.1)])
        m=fixed_asset_formula_level(c,{},24,12)
        for ppy in (1,4):
            q=fixed_asset_formula_level(c,{},2*ppy,ppy);span=12//ppy
            self.assertEqual(q['gross'],[m['gross'][0]]+m['gross'][span::span])
            for i in range(2*ppy):self.assertAlmostEqual(q['depreciation_expense'][i+1],sum(m['depreciation_expense'][1+i*span:1+(i+1)*span]))
        c['formula_level']['components'][0]['multiplier_spec']={'source':'entered','trajectory':'growth','base':120000,'growth_spec':{'method':'smooth','rate':.1,'period':'year'}}
        self.assertGreater(fixed_asset_formula_level(c,{},24,12)['gross'][-1],120000)

    def test_small_component_diagnostic_keeps_precision(self):
        r=fixed_asset_formula_level(config([component('Premium',flat(1500),.2)]),{},12,12)
        public=_conv_fixed_assets(r)
        self.assertAlmostEqual(sum(public['formula_level']['components'][0]['depreciation']),.3)

if __name__=='__main__':unittest.main()
