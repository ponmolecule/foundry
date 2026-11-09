"""Statement-linked liability stocks use the same solved flows as the statements."""
import json,copy,unittest,math
from pathlib import Path
from .run_q import run_v2
from .other_liabilities import prepare_other_liabilities,other_liability_period
from .tests_other_assets import flat

def model():
 return {'opening_balance':0,'base_spec':flat(0),'components':[
  {'component_id':sid,'name':sid,'terms':[{'term_id':sid,'driver_spec':{'source':'link','link':{'kind':'bank_statement_flow','series_id':sid,'observation':'quarter_to_date'}},'multiplier_spec':flat(mult)}]}
  for sid,mult in [('total_interest_expense',.25),('total_noninterest_expense',.5)]]}
class Tests(unittest.TestCase):
 def test_qtd_scope_and_validation(self):
  a={'other_liabilities_mode':'formula_level','other_liabilities_model':model()}
  p=prepare_other_liabilities(a,6,12);flows={'total_interest_expense':100,'total_noninterest_expense':200};hist={k:[v]*6 for k,v in flows.items()}
  self.assertEqual([other_liability_period(p,i,statement_flows=flows,flow_history=hist)['total'] for i in range(6)],[125,250,375,125,250,375])
  with self.assertRaisesRegex(ValueError,'history'):other_liability_period(p,1,statement_flows=flows)
  with self.assertRaisesRegex(ValueError,'unavailable'):other_liability_period(p,0)
  with self.assertRaisesRegex(ValueError,'finite'):other_liability_period(p,0,statement_flows={**flows,'total_interest_expense':math.nan})
  for field,value in [('series_id','ni'),('observation','future')]:
   bad=copy.deepcopy(a);bad['other_liabilities_model']['components'][0]['terms'][0]['driver_spec']['link'][field]=value
   with self.assertRaises(ValueError):prepare_other_liabilities(bad,6,12)
 def test_both_profiles_and_monthly(self):
  for fixture,ppy in [('core_bank_test_base.json',12),('core_bank_test_base.json',4),('parity/configs/pf_b_base.json',4)]:
   c=json.loads(Path('foundry/fixtures',fixture).read_text());a=c['assumptions'];a.update(other_liabilities_mode='formula_level',other_liabilities_model=model(),periods_per_year=ppy)
   if ppy==12:a.update(n_periods=12,capital_raises=[],scheduled_borrowings=[])
   r=run_v2(c);inc=r['financials']['is'];detail=r['other_liabilities'];width=ppy//4
   if 'intDep' in inc:inc.update(depExp=inc['intDep'],borrExp=inc['intBorrow'],overhead=inc['fixedOpex'],prodOpex=inc['opexProd'])
   for i in range(len(inc['fees'])):
    inds=range(i//width*width,i+1)
    for comp,expected in zip(detail['components'],[
      sum((inc['depExp'][k]+inc['borrExp'][k])*.25 for k in inds),
      sum((inc['overhead'][k]+inc['prodOpex'][k]+inc.get('feeOpex',[0]*len(inc['fees']))[k])*.5 for k in inds)]):
     self.assertAlmostEqual(comp['amount'][i],expected,delta=.02)
     self.assertEqual(comp['terms'][0]['observation'],'quarter_to_date')
 def test_borrowing_feedback(self):
  c=json.loads(Path('foundry/fixtures/core_bank_test_base.json').read_text())
  a=c['assumptions'];a.update(other_liabilities_mode='formula_level',other_liabilities_model=model(),borrow_rate_ann=.08)
  c.setdefault('target_state',{})['initial_capital']=1000
  for dep in a['deposit_products']:dep.update(opening_balance=0,new_deposits_per_period=0)
  r=run_v2(c);inc=r['financials']['is'];self.assertGreater(max(r['financials']['bs']['borrow']),0)
  for i,value in enumerate(r['other_liabilities']['components'][0]['amount']):
   self.assertAlmostEqual(value,.25*(inc['depExp'][i]+inc['borrExp'][i]),delta=.02)
 def test_entered_paths_and_joint_assets(self):
  from .tests_r476_other_asset_flows import model as asset_model
  from .fiw import build_fiw,diff_import
  c=json.loads(Path('foundry/fixtures/core_bank_test_base.json').read_text());a=c['assumptions'];a.update(other_liabilities_mode='formula_level',other_liabilities_model=model(),other_assets_mode='formula_level',other_assets_model=asset_model())
  r=run_v2(c);self.assertTrue(r['other_assets_detail']);self.assertTrue(r['other_liabilities'])
  content=build_fiw(c)[0];imported,report=diff_import(content,c)
  self.assertEqual(imported['assumptions']['other_liabilities_model'],a['other_liabilities_model'])
  old=r['other_liabilities']['components'][0]['amount'];a['deposit_products'][0]['rate_paid_ann']+=.01
  self.assertNotEqual(old,run_v2(c)['other_liabilities']['components'][0]['amount'])
if __name__=='__main__':unittest.main()
