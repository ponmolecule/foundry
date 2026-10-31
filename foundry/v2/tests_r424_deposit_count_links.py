import copy,unittest
from .tests_r380_customer_deposits import config
from .run_q import run_v2
from .validate_q import validate_errors_v2
from .deposit_balance import count_source_catalog,stream_count_balance
from .audit_workbook import _product_rows

def setup(ppy=12):
 c=config(ppy);a=c['assumptions'];p=a['deposit_products'][0]
 root={'name':'People','quantity_series_id':'people','basis':'account','driver':{'source':'customer_acquisition_count','ref':'accounts','measure':'period_end','trajectory':'flat','params':{}},'rate':{'behavior':'flat','params':{'fee_per_period':0}},'cost':{'kind':'none','params':{}}}
 child=copy.deepcopy(root);child.update(name='Savings accounts',quantity_series_id='savers');child['driver']={'source':'stream_ref','ref':'People','trajectory':'derived','params':{'multiple':.1}}
 a['obs_exposures']=[{'name':'Population','_fee_product':True,'call_report_line':'obs','fee_streams':[child,root]}]
 p['balance_driver'].update(source='fee_quantity',series_id='savers',balance_per_customer_spec={'source':'entered','trajectory':'flat','value':62500})
 return c
class Tests(unittest.TestCase):
 def test_linked_deposit_and_audit(self):
  for ppy in (4,12):
   c=setup(ppy);before=copy.deepcopy(c);self.assertEqual(validate_errors_v2(copy.deepcopy(c)),[])
   r=run_v2(c);self.assertEqual(c,before);q=r['fee_stream_quantities']['series']['savers'];p=next(p for p in r['products'] if p['family']=='deposit');calc=p['depositCustomerCalculation']
   self.assertEqual(calc['periodCount'],q)
   for count,bal in zip(q,calc['endingBalanceDollars']):self.assertAlmostEqual(bal,count*62500)
   self.assertTrue(_product_rows(r,c['assumptions']['n_periods']))
 def test_matches_existing_acquisition_deposit_math(self):
  for ppy in (12,):
   c=setup(ppy);legacy=copy.deepcopy(c);d=legacy['assumptions']['deposit_products'][0]['balance_driver'];d.update(source='customer_acquisition_count',series_id='accounts',balance_share_spec={'source':'entered','trajectory':'flat','value':.1})
   self.assertEqual(run_v2(c)['financials'],run_v2(legacy)['financials'])
 def test_stable_identity_and_no_duplicate_income(self):
  c=setup();a=run_v2(c);streams=c['assumptions']['obs_exposures'][0]['fee_streams'];streams[0]['name']='Renamed';c['assumptions']['obs_exposures'][0]['name']='New product';streams.reverse();b=run_v2(c)
  self.assertEqual(a['financials'],b['financials'])
 def test_rejections(self):
  c=setup();a=c['assumptions'];p=a['deposit_products'][0];n=a['n_periods']
  with self.assertRaises(ValueError):stream_count_balance(p,a,n,12,{'savers':[1]})
  p['balance_driver']['measure']='period_average'
  with self.assertRaises(ValueError):stream_count_balance(p,a,n,12,{'savers':[1]*n})
  p['balance_driver']['measure']='period_end';a['obs_exposures'][0]['fee_streams'][1]['driver']['source']='bank_aggregate'
  self.assertFalse(count_source_catalog(a))
 def test_period_end_amounts_no_quarter_flow_division(self):
  c=setup(4);a=c['assumptions'];p=a['deposit_products'][0];p['balance_driver']['balance_per_customer_spec']={'source':'entered','trajectory':'explicit','cadence':'month','values':list(range(1,61))}
  d=stream_count_balance(p,a,20,4,{'savers':[10]*20});self.assertEqual(d['endingBalanceDollars'][:2],[30,60])
if __name__=='__main__':unittest.main()
