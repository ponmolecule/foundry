import copy,json,unittest,io
from pathlib import Path
from .run_q import run_v2
from .preopening import totals
from .fiw import build_fiw,diff_import
from .audit_workbook import calculation_audit_workbook
class Tests(unittest.TestCase):
 def test_income_opening_and_no_forecast_posting(self):
  for fixture in ['core_bank_test_base.json','parity/configs/pf_b_base.json']:
   c=json.loads(Path('foundry/fixtures',fixture).read_text());c['assumptions'].update(cash_yield=0,securities_yield=0,sweep_securities_yield=0,borrow_rate_ann=0)
   c['pre_opening']={'expenses':[{'category':'Costs','total':14570893.860}]}
   b=run_v2(c);c['pre_opening']['incomes']=[{'category':'Earned interest','total':10470365.1}];r=run_v2(c)
   if 're' in r['financials']['bs']:
    self.assertAlmostEqual(r['financials']['bs']['re'][0]-b['financials']['bs']['re'][0],10470.3651,delta=.02)
   self.assertEqual(r['pre_open']['income_total'],10470365.1)
   self.assertAlmostEqual(r['pre_open']['net_income'],-4100528.76,places=6)
   self.assertAlmostEqual(r['pre_open']['cushion']-b['pre_open']['cushion'],10470365.1,places=5)
   self.assertEqual(r['financials']['is']['cashInt' if 'cashInt' in r['financials']['is'] else 'intCash'],b['financials']['is']['cashInt' if 'cashInt' in r['financials']['is'] else 'intCash'])
 def test_fiw_audit_income_only_and_validation(self):
  c=json.loads(Path('foundry/fixtures/core_bank_test_base.json').read_text());c['pre_opening']={'incomes':[{'category':'Interest','total':12345.678}]}
  r=run_v2(c);self.assertEqual(r['pre_open']['burn_total'],0)
  raw=build_fiw(c)[0];im,report=diff_import(raw,c);self.assertEqual(im['pre_opening'],c['pre_opening'])
  from openpyxl import load_workbook
  wb=load_workbook(io.BytesIO(raw));sheet=wb['ASSM_PREOPEN_INCOME']
  # Import an edited monetary assumption, rather than relying on a no-op round trip.
  for row in sheet:
   if str(row[0].value).endswith('.total'):row[3].value=23.456789
  out=io.BytesIO();wb.save(out);edited,report=diff_import(out.getvalue(),c)
  self.assertEqual(edited['pre_opening']['incomes'][0]['total'],23456.789)
  audit=calculation_audit_workbook(c,r);self.assertIn('Pre-opening',audit.sheetnames)
  for v in [-1,float('nan'),float('inf'),'100',True]:
   bad=copy.deepcopy(c);bad['pre_opening']['incomes'][0]['total']=v
   with self.assertRaises(ValueError):totals(bad)
 def test_legacy_and_profit(self):
  self.assertEqual(totals({'pre_opening':{'expenses':[{'category':'Legal','total':100}]}})['net_income'],-100)
  self.assertEqual(totals({'pre_opening':{'incomes':[{'category':'Fees','total':200}]}})['net_income'],200)
if __name__=='__main__':unittest.main()
