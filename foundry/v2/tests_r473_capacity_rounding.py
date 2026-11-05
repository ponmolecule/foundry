import copy,math,unittest
from unittest.mock import patch
from .tests_workforce_capacity import fixture
from .workforce import workforce_capacity_monthly,workforce_role_count_series,workforce_comp_series

class CapacityRounding(unittest.TestCase):
    def resolve(self,source,minimum=5,rounding=None):
        c=fixture();a=c['assumptions'];r=a['nie_detail']['workforce']['roles'][1];r['capacity_count']['minimum_spec']['value']=minimum
        if rounding is not None:r['capacity_count']['rounding']=rounding
        roll={'monthly':[{'new_cust':v-(source[i-1] if i else 0),'end_cust':v} for i,v in enumerate(source)]}
        before=copy.deepcopy(r)
        with patch('foundry.v2.cac_feeder.cac_auc_rollforward',return_value=roll):
            out=workforce_capacity_monthly(r,len(source),assumptions=a)
        self.assertEqual(r,before)
        return out['counts']
    def test_default_and_explicit_none_equal(self):
        source=[0,4.685,200,201,240,241]
        self.assertEqual(self.resolve(source),self.resolve(source,rounding='none'))
        self.assertEqual(self.resolve(source),[0,5,5,5.025,6,6.025])
    def test_up_after_capacity_and_minimum(self):
        self.assertEqual(self.resolve([0,4.685,200,201,240,241],rounding='up'),[0,5,5,6,6,7])
        self.assertEqual(self.resolve([0,1],minimum=5.2,rounding='up'),[0,6])
    def test_invalid_rounding_fails_closed(self):
        with self.assertRaisesRegex(ValueError,'rounding'):self.resolve([1],rounding='bad')
    def test_quarterly_averages_rounded_months(self):
        c=fixture();a=c['assumptions'];r=a['nie_detail']['workforce']['roles'][1];r['capacity_count']['rounding']='up'
        roll={'monthly':[{'new_cust':v,'end_cust':v} for v in [1,40,40]]}
        with patch('foundry.v2.cac_feeder.cac_auc_rollforward',return_value=roll):
            self.assertEqual(workforce_role_count_series(r,1,4,assumptions=a),[2])
    def test_run_and_linked_fixed_assets_use_same_counts(self):
        from .run_q import run_v2
        c=fixture();a=c['assumptions'];r=a['nie_detail']['workforce']['roles'][1];r['capacity_count']['rounding']='up'
        a['fixed_assets']={'mode':'formula_level','formula_level':{'level_basis':'gross','base_spec':{'source':'entered','trajectory':'flat','value':0},'components':[{'component_id':'equipment','name':'Equipment','driver_spec':{'source':'link','link':{'kind':'workforce_role_count','series_id':'ops'}},'multiplier_spec':{'source':'entered','trajectory':'flat','value':1000}}],'depreciation':{'kind':'rate_of_level','rate_spec':{'source':'entered','trajectory':'flat','value':0,'period':'year'}}}}
        before=copy.deepcopy(c);out=run_v2(c);self.assertEqual(c,before)
        counts=out['workforce']['counts'][1];self.assertTrue(all(x==math.ceil(x) for x in counts))
        self.assertEqual(out['fixed_assets']['gross'][1:],counts)
if __name__=='__main__':unittest.main()
