import copy,math,unittest
from .tests_r461_spend_links import fixture
from .run_q import run_v2
from .validate_q import validate_errors_v2

class CostMultiplier(unittest.TestCase):
    def output(self,ppy,path,linked=True):
        c,st,sid,other=fixture(ppy)
        cp=st['cost']['params'];cp['multiplier_path']=copy.deepcopy(path)
        cp['factor_path']={'value':21624,'trajectory':'flat','period':'month'}
        if not linked:del cp['linked_sources']
        from .testing_schedules import fill_schedules_like_r481 as _fill  # r482
        _fill(c['assumptions'])   # schedules entered for the whole horizon
        return run_v2(c)['fee_stream_economics']['series']['digital-cost']

    def test_flat_and_zero(self):
        for ppy in (4,12):
            for linked in (True,False):
                for v in (0,1,1.2,2):
                    r=self.output(ppy,{'value':v,'trajectory':'flat','period':'year'},linked)
                    self.assertTrue(all(math.isclose(x,21624*12/ppy*v) for x in r['fee_product_cost']))
                    self.assertTrue(all(x==0 for x in r['reported_fee_income']))

    def test_growth_schedule_step_smooth_cadence(self):
        for linked in (True,False):
            for period in ('month','quarter','year'):
                for resolution in ('step','smooth'):
                    for trajectory in ('growth','explicit_schedule'):
                        path={'value':1,'trajectory':trajectory,'period':period,'resolution':resolution}
                        if trajectory=='growth':path['growth_spec']={'rate':.02,'period':period,'method':resolution,'anchor':'model_year' if period=='year' else 'model_period'}
                        else:path['schedule']={'1':1,'2':1.2,'3':.5,'4':0,'5':2}
                        monthly=self.output(12,path,linked)['fee_product_cost'];quarter=self.output(4,path,linked)['fee_product_cost']
                        for i,q in enumerate(quarter):self.assertAlmostEqual(q,sum(monthly[3*i:3*i+3]),places=6,msg=str((linked,path,i)))

    def test_variable_sources_then_multiplier(self):
        c,st,sid,other=fixture(4);cp=st['cost']['params']
        cp['linked_sources']=[{'series_id':sid,'share':.5},{'series_id':other,'share':.25}]
        cp['multiplier_path']={'trajectory':'explicit_schedule','period':'month','schedule':{'1':1,'2':2,'3':3}}
        channel=c['assumptions']['cac_feeds']['Accounts']['channels'][0]
        channel['driver_specs']={'spend':{'source':'entered','trajectory':'explicit','cadence':'month','values':[1000,2000,3000]+[0]*57}}
        from .testing_schedules import fill_schedules_like_r481 as _fill  # r482
        _fill(c['assumptions'])
        cost=run_v2(c)['fee_stream_economics']['series']['digital-cost']['fee_product_cost']
        self.assertAlmostEqual(cost[0],(500+250)*1+(1000+250)*2+(1500+250)*3)

    def test_invalid_multiplier(self):
        for v in (-1,float('nan'),float('inf')):
            c,st,_,_=fixture();st['cost']['params']['multiplier_path']={'value':v,'trajectory':'flat','period':'year'}
            self.assertTrue(validate_errors_v2(c))
            st['cost']['params']['multiplier_path']={'value':1,'trajectory':'explicit_schedule','period':'year','schedule':{'1':v}}
            self.assertTrue(validate_errors_v2(c))

if __name__=='__main__':unittest.main()
