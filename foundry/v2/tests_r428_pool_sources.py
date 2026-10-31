"""Sum stable monthly channel flows before conversion; no source income/spend copying."""
import copy,json,unittest
from pathlib import Path
from .cac_feeder import cac_auc_rollforward
from .tests_r427_effectiveness import channel,spec
from .tests_acquisition_channel_links import linked
from .run_q import run_v2
from .validate_q import validate_errors_v2
from .audit_workbook import _cac_monthly_acquisition_rows


def setup():
 direct={'name':'Direct','method':'fte_productivity','derived_series_ids':{'new_customers':'direct'},'driver_specs':{
 'ftes':{'source':'entered','trajectory':'explicit','cadence':'month','values':[.5]+[1]*5+[1.5]*3+[2]*3+[2.5]*3+[3]*3+[3.5]*3+[4]*39},
 'per_fte':{'source':'entered','trajectory':'flat','value':1.6,'period':'month'},
 'productivity_multiplier':{'source':'entered','trajectory':'explicit','cadence':'month','values':[.35]*3+[.5]*3+[.75]*3+[.85]*3+[1]*48}}}
 digital=channel();digital['derived_series_ids']={'new_customers':'digital'};spec(digital,[.0425]*3+[.14]*3+[.275]*3+[.425]*3+[.62]*3+[.75]*3+[1]*42)
 emr=linked('referrals','direct',.25);emr['driver_specs']['pool']['link']['series_ids']=['direct','digital']
 feed={'channels':[emr,direct,digital],'beginning_customers':0,'beginning_auc':0,'attrition_rate':0,'intra_period_path':'monthly_flows'}
 return {'cac_feeds':{'Practices':feed}}

class Tests(unittest.TestCase):
 def test_sum_before_conversion_and_cadence(self):
  a=setup();f=a['cac_feeds']['Practices'];before=copy.deepcopy(a)
  m=cac_auc_rollforward(f,60,12,assumptions=a);q=cac_auc_rollforward(f,20,4,assumptions=a)
  self.assertEqual(a,before);self.assertEqual(m['monthly'],q['monthly']);self.assertEqual(m['annual'],q['annual'])
  for row in m['monthly']:
   ref,direct,digital=row['channels'];self.assertAlmostEqual(ref['new_customers'],.25*(direct['new_customers']+digital['new_customers']))
   self.assertEqual(ref['spend'],0);self.assertEqual(row['total_spend'],21624)
  self.assertAlmostEqual(m['monthly'][0]['channels'][0]['new_customers'],.937)
  self.assertAlmostEqual(m['monthly'][1]['channels'][0]['new_customers'],1.007)
  self.assertAlmostEqual(m['monthly'][0]['new_cust'],4.685)
 def test_rename_reorder_and_live_change(self):
  a=setup();f=a['cac_feeds']['Practices'];r=cac_auc_rollforward(f,60,12,assumptions=a)
  f['channels'].reverse()
  for ch in f['channels']:ch['name']='New '+ch['name']
  f['channels'][2]['driver_specs']['pool']['link'].update(series_id='digital',series_ids=['digital','direct'])
  rr=cac_auc_rollforward(f,60,12,assumptions=a);self.assertEqual(r['customer_end_by_month'],rr['customer_end_by_month'])
  digital=f['channels'].pop(0);a['cac_feeds']['Other feed']={'channels':[digital]};cross=cac_auc_rollforward(f,60,12,assumptions=a);self.assertEqual([x['channels'][2]['new_customers'] for x in rr['monthly']],[x['channels'][1]['new_customers'] for x in cross['monthly']])
  digital['driver_specs']['effectiveness_multiplier']['values'][0]=0
  changed=cac_auc_rollforward(f,60,12,assumptions=a);self.assertAlmostEqual(changed['monthly'][0]['channels'][1]['new_customers'],.07)
 def test_fail_closed(self):
  for mode in ('duplicate','missing','self','cycle','blank','empty','wrong_type','primary','kind','aggregation'):
   with self.subTest(mode=mode):
    a=setup();f=a['cac_feeds']['Practices'];emr,direct,digital=f['channels'];lk=emr['driver_specs']['pool']['link']
    if mode=='duplicate':lk['series_ids']=['direct','direct']
    if mode=='missing':lk['series_ids'][1]='missing'
    if mode=='self':lk['series_ids'][1]='referrals'
    if mode=='cycle':digital.update(method='pool_conversion',driver_specs=linked('x','referrals',1)['driver_specs'])
    if mode=='blank':lk['series_ids'][1]=''
    if mode=='empty':lk['series_ids']=[]
    if mode=='wrong_type':lk['series_ids']='direct'
    if mode=='primary':lk['series_id']='other'
    if mode=='kind':lk['kind']='workforce_role_count'
    if mode=='aggregation':lk['aggregation']='average'
    with self.assertRaises(ValueError):cac_auc_rollforward(f,60,12,assumptions=a)
 def test_public_audit_and_legacy(self):
  a=setup();c=json.loads(Path('foundry/fixtures/core_bank_test_base.json').read_text());c['assumptions'].update(a)
  self.assertEqual(validate_errors_v2(copy.deepcopy(c)),[])
  r=run_v2(c);self.assertAlmostEqual(r['customer_acquisition']['Practices']['monthly'][0]['channels'][0]['new_customers'],.937)
  row=next(x for x in _cac_monthly_acquisition_rows(c,36,12) if x[2]==1 and x[5]=='referrals');self.assertAlmostEqual(row[7],3.748);self.assertAlmostEqual(row[15],.937)
  f=a['cac_feeds']['Practices'];lk=f['channels'][0]['driver_specs']['pool']['link'];lk.pop('series_ids')
  old=cac_auc_rollforward(f,60,12,assumptions=a);lk['series_ids']=['direct'];new=cac_auc_rollforward(f,60,12,assumptions=a);self.assertEqual(old,new)
if __name__=='__main__':unittest.main()
