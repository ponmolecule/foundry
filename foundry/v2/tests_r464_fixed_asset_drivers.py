"""Timing/grouping and mixed-rate depreciation on a common monthly grid."""
import copy
import unittest
from unittest.mock import patch
from .fixed_assets import fixed_asset_formula_level


def spec(v, period=None):
    s = dict(source='entered', trajectory='flat', value=v)
    if period: s['period'] = period
    return s

class Drivers(unittest.TestCase):
    def config(self):
        return dict(mode='formula_level', formula_level=dict(
            level_basis='gross', opening_level=20000,
            opening_accumulated_depreciation=1000, base_spec=spec(5000),
            components=[dict(component_id='chairs', driver_spec=dict(source='link',
                link=dict(kind='workforce_role_count',series_id='staff')),
                lag_months=1, initial_driver=49, driver_divisor=50,
                driver_rounding='floor', multiplier_spec=spec(10000),
                depreciation_rate_spec=spec(1/3,'year'))],
            depreciation=dict(kind='component_rates',base_rate_spec=spec(.2,'year'))))
    def resolve(self, cfg, n, ppy, counts=None):
        counts = counts or [50,99,100,149,150,199,200,249,250,299,300,349]
        with patch('foundry.v2.series.resolve_series_spec', side_effect=lambda ns,a,n,p,**kw: counts[:n]), patch('foundry.v2.fixed_assets._monthly_workforce_driver', side_effect=lambda ns,a,n,p,ctx: counts[:n]):
            return fixed_asset_formula_level(cfg,{},n,ppy)
    def test_order_and_opening(self):
        r=self.resolve(self.config(),6,12)
        self.assertEqual(r['gross'],[20000,5000,15000,15000,25000,25000,35000])
        self.assertEqual(r['formula_level']['components'][0]['driver'],[0,1,1,2,2,3])
        self.assertAlmostEqual(r['depreciation_expense'][2],5000*.2/12+10000/36)
        self.assertEqual(r['capex'][2],10000)
    def test_cadence(self):
        c=self.config();m=self.resolve(c,12,12)
        for ppy in [4,1]:
            q=self.resolve(c,ppy,ppy);span=12//ppy
            for i in range(1,ppy+1):
                self.assertAlmostEqual(q['gross'][i],m['gross'][i*span])
                self.assertAlmostEqual(q['net'][i],m['net'][i*span])
                self.assertAlmostEqual(q['depreciation_expense'][i],sum(m['depreciation_expense'][(i-1)*span+1:i*span+1]))
                self.assertAlmostEqual(q['capex'][i],sum(m['capex'][(i-1)*span+1:i*span+1]))
    def test_native_workforce_hire_window(self):
        c=self.config()
        a={'nie_detail':{'workforce':{'roles':[dict(series_id='staff',count=100,hire_period=2)]}}}
        q=fixed_asset_formula_level(c,a,2,4)
        # Q2 hiring begins M4; one month lag first sees that count in M5.
        self.assertEqual(q['gross'],[20000,5000,25000])
        self.assertAlmostEqual(q['depreciation_expense'][2],3*5000*.2/12+2*20000/36)

    def test_invalid_and_net(self):
        for field,value in [('lag_months',-1),('driver_divisor',0),('initial_driver',float('nan')),('driver_rounding','bad')]:
            c=self.config();c['formula_level']['components'][0][field]=value
            with self.assertRaises(ValueError): self.resolve(c,3,12)
        c=self.config();c['formula_level']['level_basis']='net'
        with self.assertRaises(ValueError): self.resolve(c,3,12)
    def test_preserved_settings_and_cap(self):
        c=self.config();c['formula_level']['depreciation']['base_rate_spec']=spec(100,'year')
        r=self.resolve(c,12,12)
        self.assertTrue(all(x>=0 for x in r['net']))
        self.assertTrue(all(a<=g for a,g in zip(r['accumulated_depreciation'],r['gross'])))

if __name__=='__main__': unittest.main()
