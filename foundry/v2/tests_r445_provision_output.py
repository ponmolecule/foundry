"""Every lending method exposes its actual provision ledger without changing statement totals."""
import json,unittest
from pathlib import Path
from .run_q import run_v2
from .tests_repayment_profiles import product

class Tests(unittest.TestCase):
 def check_outputs(self,c):
  r=run_v2(c)
  for p in (p for p in r['products'] if p['family']=='lending'):
   d=p['detailExact'];self.assertEqual(len(d['provision']),len(d['co']))
   if p['is_fv']:
    self.assertTrue(all(x==0 for x in d['provision']));continue
   prior=p['alllOpen'][0]
   for j,(acl,co,prov) in enumerate(zip(d['alll'],d['co'],d['provision'])):
    self.assertAlmostEqual(prov,acl-prior+co,delta=.005001 if j==0 else 1e-7);prior=acl
   self.assertIn('allowanceTarget',d)
  return r
 def test_legacy_and_profile_both_cadences(self):
  for ppy,n in [(12,36),(4,12)]:
   c=json.loads(Path('foundry/fixtures/core_bank_test_base.json').read_text());a=c['assumptions'];a.update(periods_per_year=ppy,n_periods=n)
   p=product();p['repayment_profile']['loss_rate_spec']['value']=.04;p['reserve_rate_pct_bal']=.02
   a['lending_products'].append(p);self.check_outputs(c)
 def test_contract_keeps_authored_provision(self):
  from .tests_r369_lending_contracts import config
  self.check_outputs(config())
 def test_template_methods(self):
  self.check_outputs(json.loads(Path('foundry/fixtures/universal_template_bank.json').read_text()))
if __name__=='__main__':unittest.main()
