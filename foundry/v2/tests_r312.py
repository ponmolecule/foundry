import copy,json,unittest
from foundry.v2.engine_q_a import _deposit_rate,_prod_rate
from foundry.v2.data_checks import run_checks
from foundry.v2.run_q import run_v2
class Tests(unittest.TestCase):
 def test_beta(self):
  rate=lambda t: [.05,.04,.03][t-1]
  p={'rate_type':'float','deposit_beta':.4,'index_spread':.005}
  self.assertAlmostEqual(_deposit_rate(p,1,rate),.025)
  self.assertAlmostEqual(_deposit_rate(p,2,rate),.021)
  self.assertAlmostEqual(_prod_rate(p,1,rate),.055)
  p.update(deposit_rate_floor=.02,deposit_rate_cap=.024)
  self.assertEqual(_deposit_rate(p,1,rate),.024)
  self.assertEqual(_deposit_rate(p,3,rate),.02)
  p.update(rate_type='fixed',rate_paid_ann=.01)
  self.assertEqual(_deposit_rate(p,1,rate),.01)
 def test_saved_shorter(self):
  old={'assumptions':{'obs_exposures':[]}}
  new={'assumptions':{'obs_exposures':[{'fee_streams':[{'x':{'trajectory':'explicit','values':[10]*8+[1000]+[10]*8}}]}]}}
  before=copy.deepcopy(new)
  self.assertTrue(run_checks(new,saved=old));self.assertEqual(new,before)
 def test_link_warnings(self):
  def st(name,rate):return {'name':name,'quantity_series_id':name,'rate':{'kind':'flat','params':{'per_unit':rate}},'cost':{'kind':'none'},'driver':{'source':'constant'}}
  a,b=st('A',1),st('B',2);b['driver']={'source':'fee_stream_quantity','ref':'A','trajectory':'derived','params':{'coefficient':{'trajectory':'explicit_schedule','schedule':{}}}}
  cfg={'assumptions':{'obs_exposures':[{'name':'Fees','fee_streams':[a,b]}]}}
  self.assertEqual(len(run_checks(cfg)),2)
  a['rate']['params']['per_unit']=0
  self.assertEqual(len(run_checks(cfg)),1)
 def test_real_engine(self):
  with open('foundry/fixtures/core_bank_test_base.json') as f: cfg=json.load(f)
  p=cfg['assumptions']['deposit_products'][0];p.update(rate_type='float',index_spread=.005,deposit_beta=.4,deposit_rate_cap=.02)
  for ppy in (4,12):
   cfg['assumptions'].update(periods_per_year=ppy,n_periods=ppy*3)
   out=run_v2(cfg)
   dep=next(x for x in out['products'] if x['family']=='deposit' and x['name']==p['name'])
   self.assertEqual(len(dep['rateQ']),ppy*3)
   self.assertTrue(all(v<=2+1e-9 for v in dep['rateQ']))
   for avg,rate,expense in zip(dep['avg'],dep['rateQ'],dep['intExp']):
    self.assertAlmostEqual(expense,avg*rate/100/ppy,delta=abs(avg)*.00005/ppy+.02) # Public rateQ rounds to 0.01 percentage points.

if __name__=='__main__':unittest.main()
