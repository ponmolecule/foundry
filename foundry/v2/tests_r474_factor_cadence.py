import copy, unittest
from .opex_extensions import resolve_linked_components, linked_component_amount

class FactorCadence(unittest.TestCase):
    def resolve(self, spec, ppy=12):
        c={'linked_components':[{'driver':'formula_driver','factors':[
            {'kind':'linked','source':'workforce_count','series_id':'staff'},
            {'kind':'entered','periodized':True,'spec':{'trajectory':'flat','value':100,'period':'month'}},
            {'kind':'entered','periodized':False,'spec':spec}]}]}
        before=copy.deepcopy(c)
        compiled=resolve_linked_components(c,5*ppy,ppy)[0]
        out=[linked_component_amount(compiled,i,{'workforce_count':{'staff':2}}) for i in range(5*ppy)]
        self.assertEqual(c,before)
        return out
    def test_yearly_hold_equals_monthly_schedule(self):
        factors=[1,1.02,1.036324,1.054977832,1.073967432976]
        annual={'source':'entered','trajectory':'explicit','cadence':'year','resolution':'step','values':factors,'extend':'hold'}
        monthly={**annual,'cadence':'month','values':[v for v in factors for _ in range(12)]}
        a=self.resolve(annual);self.assertEqual(a,self.resolve(monthly))
        for year,value in enumerate(factors):
            for actual in a[year*12:year*12+12]:self.assertAlmostEqual(actual,200*value)
        quarterly=self.resolve(annual,4)
        for i,v in enumerate(quarterly):self.assertAlmostEqual(v,sum(a[3*i:3*i+3]))
    def test_quarter_hold_and_interpolation(self):
        spec={'source':'entered','trajectory':'explicit','cadence':'quarter','resolution':'step','values':[1,2,3,4]*5,'extend':'hold'}
        a=self.resolve(spec);self.assertEqual(a[:6],[200]*3+[400]*3)
        smooth=self.resolve({**spec,'resolution':'smooth'})
        self.assertNotEqual(a,smooth)
    def test_legacy_default_monthly_schedule_unchanged(self):
        spec={'source':'entered','trajectory':'explicit','cadence':'month','values':[1+i/100 for i in range(60)]}
        self.assertEqual(self.resolve(spec),self.resolve({**spec,'resolution':'step'}))
if __name__=='__main__':unittest.main()
