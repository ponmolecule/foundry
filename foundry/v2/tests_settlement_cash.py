"""Settlement observations, cash conservation, numeric acceptance and posting identity."""
import copy,io,unittest
from openpyxl import load_workbook
from .settlement_balances import prepare,bind
from .balance_components import BalanceComponents
from .tests_balance_components import configured,component,flat
from .engine_q_a import run_pf_a
from .run_q import run_v2
from .audit_workbook import calculation_audit_workbook
from .validate_q import validate_errors_v2


def product():
 return {'name':'Neutral service','call_report_line':'obs','_fee_product':True,'fee_streams':[{'name':'Service income','quantity_series_id':'service','basis':'transaction','driver':{'source':'constant','trajectory':'flat','params':{'base':100}},'rate':{'behavior':'flat','params':{'pricing_basis':'per_unit','per_unit':10}},'cost':{'kind':'none','params':{}}}]}
def settlement(period='month',sign=1):
 return {'component_id':'settle','kind':'settlement','name':'Settlement obligation','opening_balance':0,'settlement':{'period':period,'sign':sign,'weights':[1,1],'opening_history':[0],'sources':[{'series_id':'service','measure':'reported_fee_income'}]}}
def model():
 c=configured([component('cover','cash_allocation',0,cap_at_available_cash=True,interest_balance_measure='prior_end',prior_interest_initialization='zero'),component('rest','residual_cash',0,interest_balance_measure='prior_end',prior_interest_initialization='zero')]);a=c['assumptions'];a['obs_exposures'].append(product());a['other_liabilities_mode']='formula_level';a['other_liabilities_model']={'opening_balance':0,'base_spec':flat(0),'components':[settlement()]}
 comps=a['balance_components_model']['components'];comps[0]['terms']=[{'source_spec':{'source':'liability_component','component_id':'settle'},'factors':[]}]
 for comp,spread in zip(comps,[-.005,0]):comp['yield_spec']={'source':'reference_rate','index':'effr','spread_spec':flat(spread,'rate')}
 return c

class Tests(unittest.TestCase):
 def test_source_formula_m1_to_m5(self):
  # Amounts here are $000s; production uses dollars internally.
  comps=[component('cover','cash_allocation',0,cap_at_available_cash=True,interest_balance_measure='prior_end'),component('rest','residual_cash',0,interest_balance_measure='prior_end')]
  for c,spread in zip(comps,[-.005,0]):c['yield_spec']={'source':'reference_rate','index':'effr','spread_spec':flat(spread,'rate')}
  b=BalanceComponents({'balance_components_model':{'components':comps}}, {},{},5,12);b.set_opening_cash(0)
  cash=[28911.6,27794.7,29808.8,38503,40000];pay=[0,0,6398.5,13365.2,14000]
  expected=[0,81.9162,78.75165,81.792225,103.523]
  for i,(ca,pa,target) in enumerate(zip(cash,pay,expected)):
   rows,extra=b.period(i,{('rate','effr'):.034},{'cover':pa},ca,.99,cash[i-1] if i else 0)
   self.assertEqual(extra,0);self.assertAlmostEqual(sum(r['income'] for r in rows),target,places=8);self.assertAlmostEqual(sum(r['ending'] for r in rows),ca);b.commit(rows)
 def test_cap_when_payable_exceeds_cash(self):
  b=BalanceComponents({'balance_components_model':{'components':[component('cover','cash_allocation',200,.12,cap_at_available_cash=True),component('rest','residual_cash',0,.24)]}}, {},{},1,12)
  rows,extra=b.period(0,{}, {'cover':200},100,.9,0);self.assertEqual(rows[0]['ending'],100);self.assertEqual(rows[0]['requested_balance'],200);self.assertEqual(rows[1]['ending'],0);self.assertEqual(sum(r['income'] for r in rows),1);self.assertEqual(extra,0)
 def test_strict_and_capped_priority_conserve_cash(self):
  b=BalanceComponents({'balance_components_model':{'components':[component('strict','cash_allocation',20),component('first','cash_allocation',100,cap_at_available_cash=True),component('second','cash_allocation',100,cap_at_available_cash=True),component('rest','residual_cash',0)]}}, {},{},1,12)
  rows,_=b.period(0,{}, {'strict':20,'first':100,'second':100},100,0,0);self.assertEqual([r['ending'] for r in rows],[20,80,0,0])
 def test_opening_cap_does_not_force_cash(self):
  b=BalanceComponents({'balance_components_model':{'components':[component('cover','cash_allocation',0,opening_balance=200,cap_at_available_cash=True),component('rest','residual_cash',0)]}}, {},{},1,12);b.set_opening_cash(100);self.assertEqual(b.rows['cover']['opening'],100);self.assertEqual(b.rows['rest']['opening'],0)
 def test_cap_never_creates_borrowing_to_fund_allocation(self):
  c=configured([component('cover','cash_allocation',1e9,0,cap_at_available_cash=True),component('rest','residual_cash',0,0)])
  control=copy.deepcopy(c);control['assumptions']['balance_components_model']['components'][0]['terms'][0]['source_spec']['value']=0
  x=run_pf_a(c);y=run_pf_a(control)
  self.assertEqual(x['bs']['cash'],y['bs']['cash']);self.assertEqual(x['bs']['borrow'],y['bs']['borrow'])
  self.assertLess(x['balance_components']['components'][0]['ending'][0],1e9)
 def test_cash_interest_flag_preserves_balances(self):
  b=BalanceComponents({'balance_components_model':{'cash_interest_enabled':False,'components':[component('cover','cash_allocation',50,.12,cap_at_available_cash=True),component('rest','residual_cash',0,.12)]}}, {},{},1,12)
  rows,extra=b.period(0,{}, {'cover':50},100,.99,0);self.assertEqual(sum(r['income'] for r in rows)+extra,0);self.assertEqual(sum(r['ending'] for r in rows),100)
 def test_weighted_revenue_history_and_negative_sign(self):
  a={'obs_exposures':[product()]};raw=settlement(sign=-1);raw['settlement']['opening_history']=[-5];row=prepare(raw,a,12);bind(row,{'service':{'reported_fee_income':[-10,-20,-30]}},3);self.assertEqual(row['resolved_balance'],[15,30,50]);self.assertEqual(row['terms'][1]['driver'],[-5,-10,-20])
 def test_net_measure_is_explicit(self):
  raw=settlement();raw['settlement'].update(weights=[1],opening_history=[],sources=[{'series_id':'service','measure':'net_fee_income'}]);row=prepare(raw,{'obs_exposures':[product()]},12);bind(row,{'service':{'reported_fee_income':[100],'fee_product_cost':[25]}},1);self.assertEqual(row['resolved_balance'],[75])
 def test_missing_history_source_duplicates_and_invalid_weights_rejected(self):
  for update in ({'opening_history':[]},{'weights':[-1]},{'sources':[{'series_id':'missing'}]},{'sources':[{'series_id':'service'},{'series_id':'service'}]},{'sources':[{'series_id':'service','measure':'net_fee_income'},{'series_id':'service','measure':'reported_fee_income'}]}):
   raw=settlement();raw['settlement'].update(update)
   with self.assertRaises(ValueError):prepare(raw,{'obs_exposures':[product()]},12)
 def test_wrong_sign_never_clips(self):
  row=prepare(settlement(),{'obs_exposures':[product()]},12)
  with self.assertRaises(ValueError):bind(row,{'service':{'reported_fee_income':[-10]}},1)
 def test_cadence_is_explicit(self):
  with self.assertRaises(ValueError):prepare(settlement(),{'obs_exposures':[product()]},4)
  row=prepare(settlement('quarter'),{'obs_exposures':[product()]},4);bind(row,{'service':{'reported_fee_income':[100,200]}},2);self.assertEqual(row['resolved_balance'],[100,300])
 def test_live_engine_posting_once_and_stock_reconciliation(self):
  c=model();before=copy.deepcopy(c);x=run_pf_a(c);self.assertEqual(c,before)
  self.assertEqual(x['other_liabilities_detail']['components'][0]['amount'][:3],[1000,2000,2000]);self.assertEqual(x['bs']['otherLiab'][1:4],[1000,2000,2000])
  control=copy.deepcopy(c);control['assumptions']['balance_components_model']['enabled']=False;control['assumptions']['other_liabilities_mode']='flat'
  y=run_pf_a(control);self.assertEqual(x['is']['fees'],y['is']['fees']);self.assertEqual(x['fee_stream_economics']['service']['reported_fee_income'][:3],[1000,1000,1000]);self.assertEqual(x['is']['cashInt'][0],0)
  rows=x['balance_components']['components']
  for i in range(36):
   self.assertAlmostEqual(sum(r['ending'][i] for r in rows),x['bs']['cash'][i+1]);self.assertAlmostEqual(sum(r['income'][i] for r in rows),x['is']['cashInt'][i])
   self.assertAlmostEqual(x['bs']['totalAssets'][i+1],x['bs']['deposits'][i+1]+x['bs']['borrow'][i+1]+x['bs']['borrowSched'][i+1]+x['bs']['otherLiab'][i+1]+x['bs']['equity'][i+1]+x['bs']['accruedOpex'][i+1],delta=.01)
 def test_flag_does_not_hide_other_independent_income(self):
  c=model();c['assumptions']['balance_components_model']['cash_interest_enabled']=False;x=run_pf_a(c);self.assertTrue(all(v==0 for v in x['is']['cashInt']));self.assertEqual(x['fee_stream_economics']['service']['reported_fee_income'][0],1000)
 def test_audit_contains_lags_cash_cap_and_posted_income(self):
  c=model();r=run_v2(c);out=io.BytesIO();calculation_audit_workbook(c,r).save(out);out.seek(0);w=load_workbook(out,data_only=True)
  text=' '.join(str(v) for ws in w for row in ws.values for v in row if v is not None)
  for label in ['Requested allocation before cash cap','Selected eligible revenue before holding weights','lag 1','Income posted']:self.assertIn(label,text)
  public=r['other_liabilities']['components'][0];self.assertEqual(public['eligible_revenue'][0],1);self.assertEqual(r['balance_components']['components'][0]['requested_balance'][0],1)
 def test_unknown_index_missing_liability_fail_closed(self):
  c=model();c['assumptions']['balance_components_model']['components'][0]['yield_spec']['index']='unknown'
  with self.assertRaises(ValueError):run_pf_a(c)
  c=model();c['assumptions']['other_liabilities_mode']='flat'
  with self.assertRaises(ValueError):run_pf_a(c)
 def test_inactive_source_is_zero_and_active_missing_is_rejected(self):
  a={'obs_exposures':[product()]};a['obs_exposures'][0]['fee_streams'][0]['timing']={'start_period':3,'end_period':3}
  raw=settlement();row=prepare(raw,a,12);bind(row,{'service':{'reported_fee_income':[None,None,100]}},4);self.assertEqual(row['resolved_balance'],[0,0,100,100])
  row=prepare(raw,a,12)
  with self.assertRaises(ValueError):bind(row,{},4)
 def test_deleted_or_duplicate_source_and_no_overlap_model(self):
  a={'obs_exposures':[product(),product()]}
  with self.assertRaises(ValueError):prepare(settlement(),a,12)
  c=model();c['assumptions']['interest_balance_model']={'enabled':True}
  self.assertTrue(any('not both' in str(e) for e in validate_errors_v2(c)))
 def test_runtime_repriced_source_rejected(self):
  a={'obs_exposures':[product()]};a['obs_exposures'][0]['fee_streams'][0]['rate']['behavior']='durbin_capped'
  with self.assertRaises(ValueError):prepare(settlement(),a,12)

if __name__=='__main__':unittest.main()
