"""New templates are neutral; saved/example configurations are not rewritten."""
import copy,json,unittest
from pathlib import Path
from .new_engagement import neutral_template,FUNDING_DEFAULT_KEYS
from .run_q import run_v2
class Tests(unittest.TestCase):
 def test_all_template_sources(self):
  for path in ('foundry/fixtures/parity/configs/pf_a_base.json','foundry/fixtures/patrick_default_v31.json','foundry/fixtures/universal_template_bank.json'):
   original=json.loads(Path(path).read_text());before=copy.deepcopy(original);new=neutral_template(original)
   self.assertEqual(original,before)
   for key in FUNDING_DEFAULT_KEYS:self.assertEqual(new['assumptions'][key],0)
   if 'nie_detail' in new['assumptions']:self.assertEqual(new['assumptions']['nie_detail']['fdic_bp_ann'],0)
   expected=copy.deepcopy(before)
   for key in FUNDING_DEFAULT_KEYS:expected['assumptions'][key]=0
   if 'nie_detail' in expected['assumptions']:expected['assumptions']['nie_detail']['fdic_bp_ann']=0
   self.assertEqual(new,expected,'Only requested default assumptions change')
 def test_blank_input(self):
  out=neutral_template({'assumptions':{}})
  self.assertEqual(out['assumptions'],{key:0 for key in FUNDING_DEFAULT_KEYS})
 def test_existing_explicit_inputs_preserved(self):
  c=json.loads(Path('foundry/fixtures/core_bank_test_base.json').read_text());before=copy.deepcopy(c);a=c['assumptions'];a.update(cash_target_pct_deposits=.05,cash_yield=.025,borrow_rate_ann=.055)
  r=run_v2(c);self.assertEqual(c['assumptions']['cash_yield'],.025)
  self.assertTrue(any(r['financials']['is']['cashInt']))
if __name__=='__main__':unittest.main()
