"""Setup stays visible and can be revised without reinterpreting entered inputs."""
import copy,json,math,unittest
from pathlib import Path
from .engagement_setup import initialize,policy,apply,values
from .fiw import build_fiw,diff_import
from .engine_q_a import _build_rate_curve_set

def shell():
 c=json.loads(Path('foundry/fixtures/core_bank_test_base.json').read_text());a=c['assumptions'];a.update(periods_per_year=12,n_periods=36,capital_raises=[],scheduled_borrowings=[],lending_products=[],deposit_products=[],obs_exposures=[]);a.pop('nie_detail',None)
 c['charter_profile']={'charter_type':'state_nonmember','state':'Texas','regulator':'FDIC + state supervisor','target_opening':'2028-01-01','cblr_election':True};c.update(proposed_bank='Example',client_legal_name='Example (in organization)',hq='Texas',scenario_name='Example — engagement baseline',pre_opening={'expenses':[]});return initialize(c)

class Tests(unittest.TestCase):
 def test_renderer_empty_asset_shell_does_not_lock_setup(self):
  c=shell();c['assumptions']['fixed_assets']={'mode':'simple','assets':[]}
  self.assertTrue(policy(c)['early'])
  x=apply(c,{'periods_per_year':4,'target_opening':'2029-01-01'})
  self.assertEqual(values(x)['periods_per_year'],4);self.assertEqual(values(x)['target_opening'],'2029-01-01')
 def test_r318_baseline_with_empty_asset_shell_is_compatible(self):
  from .engagement_setup import _digest
  c=shell();c['authoring_setup']['creation_inputs']['fixed_assets']=_digest({'mode':'simple','assets':[]})
  self.assertTrue(policy(c)['early'])
  c['assumptions']['fixed_assets']={'mode':'schedule','assets':[{'cost':1000}]}
  self.assertFalse(policy(c)['early'])
 def test_legacy_empty_asset_shell_is_not_entered_data(self):
  c={'assumptions':{'fixed_assets':{'mode':'simple','assets':[]}}}
  self.assertTrue(policy(c)['early'])
 def test_asset_formula_and_unknown_fields_remain_protected(self):
  for fa in ({'mode':'formula_level','formula_level':{'opening_level':1000}}, {'mode':'simple','assets':[],'future_input':1}):
   c=shell();c['assumptions']['fixed_assets']=fa;self.assertFalse(policy(c)['early'])
 def test_early_horizon_preserves_capital_and_preopening(self):
  c=shell();c['pre_opening']['expenses']=[{'description':'Legal','amount':12000,'month_offset':-1}];before=copy.deepcopy(c)
  x=apply(c,{'years':5});self.assertEqual(x['assumptions']['n_periods'],60);self.assertEqual(x['pre_opening'],c['pre_opening']);self.assertEqual(x['target_state'],c['target_state']);self.assertEqual(c,before);self.assertTrue(policy(x)['early'])
 def test_horizon_edit_does_not_rewrite_unselected_identity_fields(self):
  c=shell();before=copy.deepcopy(c);x=apply(c,{'years':5})
  self.assertEqual(x['charter_profile'],before['charter_profile']);self.assertEqual(x['proposed_bank'],before['proposed_bank']);self.assertEqual(x['hq'],before['hq']);self.assertEqual(x['target_state'],before['target_state'])
 def test_noop_preserves_every_field(self):
  c=shell();self.assertEqual(apply(c,{}),c)
 def test_early_charter_updates_regulator(self):
  c=shell();x=apply(c,{'charter_type':'national'});self.assertEqual(x['charter_profile']['regulator'],'OCC')
 def test_early_cadence_rescales_template_flows_and_rates(self):
  c=shell();c['assumptions']['deposit_products']=[{'name':'Demand','opening_balance':0,'growth_per_period':.01,'runoff_per_period':.005,'rate_type':'fixed','rate_paid_ann':.02,'new_deposits_per_period':12000}];c=initialize(c)
  x=apply(c,{'periods_per_year':4});d=x['assumptions']['deposit_products'][0];self.assertEqual(x['assumptions']['n_periods'],12);self.assertEqual(d['new_deposits_per_period'],36000);self.assertAlmostEqual(d['growth_per_period'],1.01**3-1);self.assertAlmostEqual(d['runoff_per_period'],1-.995**3);self.assertEqual(d['rate_paid_ann'],.02)
 def test_late_cadence_opening_charter_and_shrink_rejected_atomically(self):
  c=shell();c['assumptions']['deposit_products']=[{'name':'Demand','opening_balance':10000,'rate_type':'fixed','rate_paid_ann':0}];before=copy.deepcopy(c)
  self.assertFalse(policy(c)['early'])
  for patch in ({'periods_per_year':4},{'target_opening':'2029-01-01'},{'charter_type':'national'},{'years':1}):
   with self.assertRaises(ValueError):apply(c,patch)
   self.assertEqual(c,before)
 def test_late_horizon_extension_is_not_an_arbitrary_lock(self):
  c=shell();c['assumptions']['deposit_products']=[{'name':'Demand','opening_balance':10000,'rate_type':'fixed','rate_paid_ann':0}];x=apply(c,{'years':5});self.assertEqual(x['assumptions']['n_periods'],60);self.assertFalse(policy(x)['early']);self.assertEqual(x['assumptions']['deposit_products'],c['assumptions']['deposit_products'])
 def test_late_identity_capital_cblr_editable(self):
  c=shell();c['assumptions']['cac_feeds']={'Example':{'value':1}} # bad unrelated intake must not be repaired/erased
  x=apply(c,{'name':'New Example','initial_capital':35000000,'cblr_election':False});self.assertEqual(x['proposed_bank'],'New Example');self.assertEqual(x['target_state']['initial_capital'],35000000);self.assertFalse(x['charter_profile']['cblr_election']);self.assertEqual(x['assumptions']['cac_feeds'],c['assumptions']['cac_feeds'])
 def test_manual_curves_extend_without_changing_anchors_or_old_points(self):
  c=shell();a=c['assumptions'];a['rate_curves']={k:{'edited':True,'path_q':[.04]*12,'dated_anchors':{'2028-03-31':.04,'2030-12-31':.04},'longer_run':.03} for k in ('sofr','effr','prime')};c=initialize(c);before=copy.deepcopy(c);x=apply(c,{'years':5})
  for k in ('sofr','effr','prime'):
   self.assertEqual(x['assumptions']['rate_curves'][k]['dated_anchors'],a['rate_curves'][k]['dated_anchors']);self.assertEqual(x['assumptions']['rate_curves'][k]['path_q'][:12],[.04]*12);self.assertEqual(len(x['assumptions']['rate_curves'][k]['path_q']),20);self.assertTrue(x['assumptions']['rate_curves'][k]['edited'])
  self.assertEqual(c,before)
 def test_generated_curve_sampling_rebuilds_required_grid_preserving_source(self):
  c=shell();a=c['assumptions'];a['rate_curves']={k:{'edited':False,'path_q':[.04]*12,'dated_anchors':{'2028-03-31':.04,'2030-12-31':.04},'longer_run':.03} for k in ('sofr','effr','prime')};c=initialize(c);x=apply(c,{'years':5});self.assertEqual(len(x['assumptions']['rate_path_q']),20)
  for k in ('sofr','effr','prime'):self.assertEqual(x['assumptions']['rate_curves'][k]['dated_anchors'],a['rate_curves'][k]['dated_anchors'])
 def test_manual_curve_without_dates_cannot_be_overwritten(self):
  c=shell();c['assumptions']['rate_curves']={'sofr':{'edited':True,'path_q':[.04]*12}};before=copy.deepcopy(c)
  with self.assertRaisesRegex(ValueError,'lacks dated anchors'):apply(c,{'years':5})
  self.assertEqual(c,before)
 def test_invalid_inputs_rejected(self):
  c=shell()
  for p in ({'years':99},{'years':True},{'initial_capital':float('nan')},{'periods_per_year':6},{'charter_type':'fake'},{'target_opening':'2028-02-31'},{'cblr_election':'yes'},{'oops':1}):
   with self.assertRaises(ValueError):apply(c,p)
 def test_implicit_horizon_ramp_cannot_retime_existing_revenue(self):
  c=shell();c['assumptions']['obs_exposures']=[{'name':'Managed','managed_notional':{'day1':0,'target':100000,'trajectory':'ramp_to_target'}}];before=copy.deepcopy(c)
  with self.assertRaisesRegex(ValueError,'explicit ramp duration'):apply(c,{'years':5})
  self.assertEqual(c,before)
 def test_missing_future_source_values_prevent_extension(self):
  c=shell();c['assumptions']['deposit_products']=[{'name':'Deposits','call_report_line':'depDDA','opening_balance':0,'rate_type':'fixed','rate_paid_ann':0,'balance_mode':'level','ending_balance_spec':{'source':'entered','trajectory':'explicit','cadence':'year','values':[1000,2000,3000],'extend':'error'}}];before=copy.deepcopy(c)
  with self.assertRaisesRegex(ValueError,'additional inputs'):apply(c,{'years':5})
  self.assertEqual(c,before)
 def test_native_schedule_is_never_reinterpreted_during_cadence_change(self):
  c=shell();c['assumptions']['some_future_source']={'cadence':'model_period','values':[1,2,3]};c=initialize(c)
  with self.assertRaisesRegex(ValueError,'deliberate reauthoring'):apply(c,{'periods_per_year':4})
 def test_period_event_cadence_conversion_preserves_calendar_offset(self):
  c=shell();c['assumptions']['some_future_source']={'start_period':13,'ramp_periods':6};c=initialize(c);x=apply(c,{'periods_per_year':4});self.assertEqual(x['assumptions']['some_future_source'],{'start_period':5,'ramp_periods':2})
 def test_period_event_cannot_be_silently_rounded_to_a_quarter(self):
  c=shell();c['assumptions']['some_future_source']={'start_period':2};c=initialize(c)
  with self.assertRaisesRegex(ValueError,'exactly'):apply(c,{'periods_per_year':4})
 def test_existing_populated_engagement_no_baseline_is_conservative(self):
  c=shell();del c['authoring_setup'];c['assumptions']['deposit_products']=[{'opening_balance':10000}];self.assertFalse(policy(c)['early']);before=copy.deepcopy(c);policy(c);self.assertEqual(c,before)
 def test_preopening_and_generated_cache_do_not_lock(self):
  c=shell();c['pre_opening']['expenses']=[{'amount':2000}];c['assumptions']['rate_curves']={'sofr':{'edited':False,'path_q':[.05]*12}};c['assumptions']['rate_path_q']=[.05]*12;self.assertTrue(policy(c)['early'])
 def test_saved_baseline_survives_workbook_roundtrip(self):
  c=shell();b,_=build_fiw(c);x,_=diff_import(b,copy.deepcopy(c));self.assertEqual(x,c);self.assertTrue(policy(x)['early'])
 def test_changing_link_identity_is_a_real_dependency(self):
  c=shell();c['assumptions']['deposit_products']=[{'ending_balance_spec':{'source':'link','link':{'kind':'fee_quantity','series_id':'original'}}}];c=initialize(c);c['assumptions']['deposit_products'][0]['ending_balance_spec']['link']['series_id']='another';self.assertFalse(policy(c)['early'])
 def test_api_body_policy_apply_and_error_have_no_persistence_side_effect(self):
  # Execute the exact route body without importing this environment's missing FastAPI.
  import ast
  tree=ast.parse(Path('app.py').read_text());node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='v31_engagement_setup')
  self.assertEqual(ast.literal_eval(node.decorator_list[0].args[0]),'/api/v31/engagement-setup')
  self.assertIn('Depends(gate)',ast.unparse(node.args))
  node.decorator_list=[]
  class Response:
   def __init__(self,body,status_code=200):self.body=body;self.status_code=status_code
  ns={'JSONResponse':Response,'Depends':lambda x:None,'gate':None};exec(compile(ast.Module(body=[node],type_ignores=[]),'app.py','exec'),ns)
  route=ns['v31_engagement_setup'];c=shell();before=copy.deepcopy(c)
  r=route({'action':'policy','cfg':c});self.assertEqual(r.status_code,200);self.assertTrue(r.body['early'])
  r=route({'action':'apply','cfg':c,'patch':{'years':5}});self.assertEqual(r.status_code,200);self.assertEqual(r.body['cfg']['assumptions']['n_periods'],60)
  r=route({'action':'apply','cfg':c,'patch':{'years':8}});self.assertEqual(r.status_code,422);self.assertEqual(c,before)
if __name__=='__main__':unittest.main()
