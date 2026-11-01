"""Live acquisition-band deposit amounts: causal mix, measures, mapping and tiers."""
import copy,unittest
from .tests_r429_composition import setup
from .deposit_balance import customer_balance,per_customer_amount
from .cac_feeder import cac_auc_rollforward
from .balance_measures import monthly_balance_measure_series

AMOUNTS=[404711.92264,883608.79509,2029378.03469,7746420.64012]
def product(share=.7):
 return dict(name='Operating tier',balance_mode='linked_customer_level',balance_driver={
  'source':'customer_acquisition_count','series_id':'practices-count','measure':'period_end',
  'balance_share_spec':{'value':share},'balance_per_customer_spec':{
   'source':'weighted_sum','unit':'money_per_unit','weight_source':'active_population','components':[
    dict(id='c'+str(i),name='Band '+str(i),population_band_id='b'+str(i),
         amount_spec={'value':v,'unit':'money_per_unit'},weight_spec={'value':.25,'unit':'share'})
    for i,v in enumerate(AMOUNTS)]}})
class Tests(unittest.TestCase):
 def test_monthly_quarterly_and_measures(self):
  for measure in ['period_end','period_average']:
   a=setup();p=product();p['balance_driver']['measure']=measure;before=copy.deepcopy(a)
   r=cac_auc_rollforward(a['cac_feeds']['Practices'],60,12,assumptions=a)
   expected=[0.]*60
   for i,b in enumerate(r['population_composition']['bands'].values()):
    counts=b['customer_end_by_month'] if measure=='period_end' else monthly_balance_measure_series(b['opening'],b['customer_end_by_month'],'period_average')
    expected=[x+c*AMOUNTS[i]*.7 for x,c in zip(expected,counts)]
   m=customer_balance(p,a,60,12);q=customer_balance(p,a,20,4)
   for x,y in zip(m['endingBalanceDollars'],expected):self.assertAlmostEqual(x,y,delta=1e-5)
   qexpected=expected[2::3] if measure=='period_end' else [sum(expected[i:i+3])/3 for i in range(0,60,3)]
   for x,y in zip(q['endingBalanceDollars'],qexpected):self.assertAlmostEqual(x,y,delta=1e-5)
   self.assertEqual(a,before)
   upper=customer_balance(product(.3),a,60,12)
   if measure=='period_end':
    for lo,hi,total in zip(m['endingBalanceDollars'],upper['endingBalanceDollars'],expected):self.assertAlmostEqual(lo+hi,total/.7,delta=1e-5)
 def test_changes_and_amount_link(self):
  a=setup();p=product();a['deposit_products']=[p];p['source_catalog_id']='lower'
  before=customer_balance(p,a,60,12)['endingBalanceDollars']
  # Reassign every channel to large practices: counts stay same but dollars change.
  for shares in a['cac_feeds']['Practices']['population_composition']['channel_shares'].values():
   shares.update({k:float(k=='b3') for k in shares})
  after=customer_balance(p,a,60,12)['endingBalanceDollars'];self.assertNotEqual(before,after)
  up=product(.3);up['balance_driver']['balance_per_customer_spec']={'source':'deposit_customer_amount','series_id':'lower'}
  for lo,hi in zip(after,customer_balance(up,a,60,12)['endingBalanceDollars']):self.assertAlmostEqual(hi,lo*3/7,delta=1e-5)
  # Stable IDs, not labels or order, determine the band mapping.
  p['balance_driver']['balance_per_customer_spec']['components'].reverse()
  for x,y in zip(after,customer_balance(p,a,60,12)['endingBalanceDollars']):self.assertAlmostEqual(x,y,delta=1e-5)
 def test_amount_factors(self):
  a=setup();p=product();s=p['balance_driver']['balance_per_customer_spec']
  baseline=customer_balance(p,a,60,12)['endingBalanceDollars']
  s['factors']=[{'source':'entered','unit':'scalar','value':2}]
  for x,y in zip(customer_balance(p,a,60,12)['endingBalanceDollars'],baseline):self.assertAlmostEqual(x,y*2,delta=1e-5)
  s['factors'][0]['unit']='money_per_unit'
  with self.assertRaisesRegex(ValueError,'dimensionless'):customer_balance(p,a,60,12)
 def test_bad_mapping_and_zero(self):
  a=setup();p=product();cs=p['balance_driver']['balance_per_customer_spec']['components'];cs[0]['population_band_id']='missing'
  with self.assertRaisesRegex(ValueError,'every acquisition band'):customer_balance(p,a,60,12)
  cs[0]['population_band_id']='b1'
  with self.assertRaisesRegex(ValueError,'every acquisition band'):customer_balance(p,a,60,12)
  p=product();a['cac_feeds']['Practices']['channels']=[];a['cac_feeds']['Practices']['population_composition']['channel_shares']={}
  self.assertEqual(customer_balance(p,a,60,12)['endingBalanceDollars'],[0.]*60)
if __name__=='__main__':unittest.main()
