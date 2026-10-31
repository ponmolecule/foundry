"""Spend stays whole; acquisition effectiveness is a dimensionless monthly path."""
import copy,json,unittest
from pathlib import Path
from .cac_feeder import _channel_monthly,cac_auc_rollforward
from .run_q import run_v2
from .audit_workbook import _cac_monthly_acquisition_rows,calculation_audit_workbook


def channel():
 return {'name':'Digital','method':'spend_cac','params':{},'avg_auc_per_customer':100,'driver_specs':{
 'spend':{'source':'entered','trajectory':'flat','value':21624,'period':'month'},
 'cac':{'source':'entered','trajectory':'flat','value':265}}}

def spec(ch,values,cadence='month'):
 ch['driver_specs']['effectiveness_multiplier']={'source':'entered','trajectory':'explicit','cadence':cadence,'values':values}

class Tests(unittest.TestCase):
 def test_default_and_unity(self):
  ch=channel();before=_channel_monthly(ch,12);old=copy.deepcopy(ch)
  ch['driver_specs']['effectiveness_multiplier']={'source':'entered','trajectory':'flat','value':1}
  after=_channel_monthly(ch,12)
  for x,y in zip(before,after):
   self.assertEqual(x['new_customers'],y['new_customers']);self.assertEqual(x['spend'],y['spend'])
  self.assertNotIn('effectiveness_multiplier',old['driver_specs'])
 def test_digital_ramp_and_cadence(self):
  ch=channel();ramp=[.0425]*3+[.14]*3+[.275]*3+[.425]*3+[.62]*3+[.75]*3+[1]*42;spec(ch,ramp)
  before=copy.deepcopy(ch);rows=_channel_monthly(ch,60);self.assertEqual(ch,before)
  for r,m in zip(rows,ramp):
   self.assertAlmostEqual(r['new_customers'],21624/265*m);self.assertEqual(r['spend'],21624)
   self.assertAlmostEqual(r['new_auc'],r['new_customers']*100)
  self.assertAlmostEqual(rows[0]['new_customers'],3.4679999999999995)
  f={'channels':[ch],'attrition_rate':0};m=cac_auc_rollforward(f,60,12);q=cac_auc_rollforward(f,20,4)
  self.assertEqual(m['monthly'],q['monthly']);self.assertEqual(m['annual'],q['annual'])
  self.assertEqual(m['annual'][0]['total_spend'],21624*12)
 def test_paths_and_zero(self):
  ch=channel();spec(ch,[0,.5,1,1.2],'quarter');rows=_channel_monthly(ch,12)
  for i,r in enumerate(rows):self.assertAlmostEqual(r['new_customers'],21624/265*[0,.5,1,1.2][i//3])
  self.assertIsNone(rows[0]['cac']);self.assertEqual(rows[0]['spend'],21624)
  ch['driver_specs']['effectiveness_multiplier']={'source':'entered','trajectory':'growth','base':.5,'growth_spec':{'rate':1,'period':'year','method':'step','anchor':'model_year'}}
  r=_channel_monthly(ch,24);self.assertAlmostEqual(r[12]['new_customers'],r[0]['new_customers']*2)
 def test_invalid(self):
  for v in (-.1,float('nan'),float('inf')):
   ch=channel();spec(ch,[v])
   with self.assertRaises(ValueError):_channel_monthly(ch,12)
 def test_public_results_audit_and_validation(self):
  from .validate_q import validate_errors_v2
  c=json.loads(Path('foundry/fixtures/core_bank_test_base.json').read_text());ch=channel();spec(ch,[.0425]*3+[.14]*3+[.275]*3+[.425]*3)
  c['assumptions']['cac_feeds']={'Digital feed':{'series_id':'digital-feed','customer_count_series_id':'digital-count','channels':[ch],'beginning_customers':0,'beginning_auc':0,'attrition_rate':0,'intra_period_path':'monthly_flows'}}
  self.assertEqual(validate_errors_v2(copy.deepcopy(c)),[])
  r=run_v2(c);m=r['customer_acquisition']['Digital feed']['monthly'][0];self.assertEqual(m['total_spend'],21.624);self.assertAlmostEqual(m['new_cust'],3.468)
  row=_cac_monthly_acquisition_rows(c,12,12)[0];self.assertEqual(row[-2],.0425);self.assertEqual(row[17],21624)
  wb=calculation_audit_workbook(c,r);self.assertIn('CAC Monthly Acquisition',wb.sheetnames)
if __name__=='__main__':unittest.main()
