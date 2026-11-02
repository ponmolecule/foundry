"""Live lending band mix, consumer isolation, monthly-first aggregation and persistence."""
import copy,json,unittest
from .tests_r429_composition import setup
from .cac_feeder import cac_customer_count_measure_series_map,cac_auc_rollforward
from .loan_balance import resolve_linked_loan_balance
from .balance_measures import monthly_balance_measure_series

AMOUNTS=[6493634.,13998822.,29239418.,110763089.]
def case():
 a=setup();a['balance_components_model']={'inputs':[{'id':'tpv','name':'TPV','unit':'money_per_unit','amount_time_basis':'year','spec':{'source':'weighted_sum','unit':'money_per_unit','components':[{'id':'c'+str(i),'name':'Band '+str(i),'amount_spec':{'value':v,'unit':'money_per_unit'},'weight_spec':{'value':.25,'unit':'share'}} for i,v in enumerate(AMOUNTS)]}}]}
 p={'name':'Lines','balance_mode':'linked_customer_level','structure':'revolving','balance_driver':{'source':'customer_acquisition_count','series_id':'practices-count','measure':'period_end','average_balance_per_customer_spec':{'source':'input_ref','input_id':'tpv','weight_source':'active_population','population_band_map':{'c'+str(i):'b'+str(i) for i in range(4)},'factors':[{'value':.04109589041,'unit':'share'}]}}}
 return a,p
class Tests(unittest.TestCase):
 def test_monthly_and_quarterly(self):
  for measure in ['period_end','period_average']:
   a,p=case();p['balance_driver']['measure']=measure;original=copy.deepcopy(a)
   roll=cac_auc_rollforward(a['cac_feeds']['Practices'],60,12,assumptions=a)
   expected=[0.]*60
   for i,b in enumerate(roll['population_composition']['bands'].values()):
    c=b['customer_end_by_month'] if measure=='period_end' else monthly_balance_measure_series(b['opening'],b['customer_end_by_month'],'period_average')
    expected=[x+y*AMOUNTS[i]*.04109589041 for x,y in zip(expected,c)]
   for ppy in [12,4]:
    n=60*ppy//12;counts=cac_customer_count_measure_series_map(a,n,ppy)
    out=resolve_linked_loan_balance(p,a,counts,n,ppy)
    want=expected if ppy==12 else expected[2::3] if measure=='period_end' else [sum(expected[i:i+3])/3 for i in range(0,60,3)]
    for x,y in zip(want,out['ending_balance']):self.assertAlmostEqual(x,y,delta=1e-5)
   self.assertEqual(a,original)
   restored=json.loads(json.dumps(p));self.assertEqual(restored,p)
 def test_mapping_changes_live_amounts_not_shared_consumers(self):
  a,p=case();counts=cac_customer_count_measure_series_map(a,60,12)
  before=copy.deepcopy(a);live=resolve_linked_loan_balance(p,a,counts,60,12)
  static=copy.deepcopy(p);del static['balance_driver']['average_balance_per_customer_spec']['weight_source']
  baseline=resolve_linked_loan_balance(static,a,counts,60,12)
  for weights in a['cac_feeds']['Practices']['population_composition']['channel_shares'].values():weights.update({b:float(b=='b3') for b in weights})
  after=resolve_linked_loan_balance(p,a,counts,60,12)
  self.assertNotEqual(live['ending_balance'],after['ending_balance'])
  self.assertEqual(baseline['ending_balance'],resolve_linked_loan_balance(static,a,counts,60,12)['ending_balance'])
  self.assertEqual(a['balance_components_model'],before['balance_components_model'])
 def test_saved_configuration_through_full_engine(self):
  from pathlib import Path
  from .run_q import run_v2
  from .validate_q import validate_errors_v2
  c=json.loads(Path('foundry/fixtures/core_bank_test_base.json').read_text())
  a,p=case();loan=c['assumptions']['lending_products'][0];loan.update(p)
  c['assumptions'].update(a);c['assumptions']['lending_products']=[loan]
  self.assertEqual(validate_errors_v2(copy.deepcopy(c)),[])
  original=copy.deepcopy(c);out=run_v2(copy.deepcopy(c))
  rows=[x for x in out['products'] if x['family']=='lending']
  self.assertTrue(rows[0]['lendingAssumptionDetail'])
  restored=json.loads(json.dumps(c))
  again=run_v2(restored)
  self.assertEqual(out['run_hash'],again['run_hash'])
  self.assertEqual(c,original)
 def test_invalid_mapping_and_zero(self):
  a,p=case();s=p['balance_driver']['average_balance_per_customer_spec'];s['population_band_map']['c0']='b1'
  with self.assertRaisesRegex(ValueError,'every acquisition band'):resolve_linked_loan_balance(p,a,{},60,12)
  a,p=case();s=p['balance_driver']['average_balance_per_customer_spec'];s['factors'][0]['unit']='money'
  with self.assertRaisesRegex(ValueError,'dimensionless'):resolve_linked_loan_balance(p,a,{},60,12)
  a,p=case();f=a['cac_feeds']['Practices'];f['channels']=[];f['population_composition']['channel_shares']={}
  counts=cac_customer_count_measure_series_map(a,60,12)
  self.assertEqual(resolve_linked_loan_balance(p,a,counts,60,12)['ending_balance'],[0.]*60)
if __name__=='__main__':unittest.main()
