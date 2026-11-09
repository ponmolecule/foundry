"""Responsive statement flows retain dollars, observation scope and solver consistency."""
import copy,json,unittest
from pathlib import Path
from .other_assets import prepare_other_assets, other_asset_period
from .run_q import run_v2
from .tests_other_assets import flat

def model():
 return {'opening_balance':0,'base_spec':flat(0),'components':[
  {'component_id':sid,'name':sid,'terms':[{'term_id':sid,'driver_spec':{'source':'link','link':{'kind':'bank_income_flow','series_id':sid,'observation':'quarter_to_date'}},'multiplier_spec':flat(mult)}]}
  for sid,mult in [('total_interest_income',.25),('total_noninterest_expense',.30)]]}
class Tests(unittest.TestCase):
 def test_monthly_qtd_reset(self):
  p=prepare_other_assets({'other_assets_model':model()},6,12)
  flows={'total_interest_income':100,'total_noninterest_expense':200}
  hist={k:[v]*6 for k,v in flows.items()}
  self.assertEqual([other_asset_period(p,i,income_flows=flows,flow_history=hist)['total'] for i in range(6)], [85,170,255,85,170,255])
 def test_full_engine_both_profiles(self):
  for fixture,ppy in [('core_bank_test_base.json',12),('core_bank_test_base.json',4),('parity/configs/pf_b_base.json',4)]:
   c=json.loads(Path('foundry/fixtures',fixture).read_text());a=c['assumptions']
   a.update(other_assets_mode='formula_level',other_assets_model=model(),periods_per_year=ppy)
   if ppy==12:a.update(n_periods=12,capital_raises=[],scheduled_borrowings=[])
   r=run_v2(c);f=r['financials'];inc=f['is'];stocks=f['bs']['otherAssets']
   if len(stocks)==len(inc['fees'])+1:stocks=stocks[1:]
   if 'intLoans' in inc:
    inc.update(loanInt=inc['intLoans'],secInt=inc['intSec'],cashInt=inc['intCash'],overhead=inc['fixedOpex'],prodOpex=inc['opexProd'])
   width=ppy//4
   for i,stock in enumerate(stocks):
    inds=range(i//width*width,i+1)
    expected=sum(.25*(inc['loanInt'][k]+inc['secInt'][k]+inc['cashInt'][k])+.30*(inc['overhead'][k]+inc['prodOpex'][k]+inc.get('feeOpex',[0]*len(stocks))[k]) for k in inds)
    self.assertAlmostEqual(stock,expected,delta=.02)
   # Audit traces resolve the selected source, not a stale solver guess.
   self.assertEqual(r['other_assets_detail']['components'][0]['terms'][0]['observation'],'quarter_to_date')
 def test_responsive_links(self):
  c=json.loads(Path('foundry/fixtures/core_bank_test_base.json').read_text())
  a=c['assumptions'];a.update(other_assets_mode='formula_level',other_assets_model=model())
  before=run_v2(c)['financials']['bs']['otherAssets']
  a['cash_yield'] += .01
  self.assertNotEqual(before,run_v2(c)['financials']['bs']['otherAssets'])
 def test_invalid_observation_and_days(self):
  m=model();t=m['components'][0]['terms'][0]
  t['driver_spec']['link']['observation']='future'
  with self.assertRaisesRegex(ValueError,'observation'):prepare_other_assets({'other_assets_model':m},3,12)
  t['driver_spec']['link']['observation']='quarter_to_date';t['days_spec']=flat(30)
  with self.assertRaisesRegex(ValueError,'current-period'):prepare_other_assets({'other_assets_model':m},3,12)
 def test_missing_history_rejected(self):
  p=prepare_other_assets({'other_assets_model':model()},3,12)
  with self.assertRaisesRegex(ValueError,'history'):other_asset_period(p,1,income_flows={'total_interest_income':1,'total_noninterest_expense':2})
if __name__=='__main__':unittest.main()
