import copy,json,unittest,io
from pathlib import Path
from .run_q import run_v2
from .source_catalog import balance_catalog
from .other_assets import prepare_other_assets,other_asset_period
from .other_liabilities import prepare_other_liabilities,other_liability_period
from .tests_other_assets import flat

def model(rows,kind='asset',measure='period_end'):
 return {'opening_balance':0,'base_spec':flat(0),'components':[{'component_id':str(i),'name':x['label'],'terms':[{'term_id':str(i),'driver_spec':{'source':'link','link':{'kind':'catalog_balance','series_id':x['series_id'],'measure':measure}},'multiplier_spec':flat(.0014)}]} for i,x in enumerate(rows)]}
class Tests(unittest.TestCase):
 def test_all_catalog_sources_measures_and_missing(self):
  a={'lending_products':[{'name':'Same','source_catalog_id':'a'},{'name':'Same','source_catalog_id':'b'}], 'deposit_products':[{'name':'Deposit','source_catalog_id':'d'}],'deposit_retention_pools':[{'id':'pool'}]}
  rows=balance_catalog(a)
  for row in rows:
   for measure in row['measures']:
    for kind,prepare,resolve in [('asset',prepare_other_assets,other_asset_period),('liability',prepare_other_liabilities,other_liability_period)]:
     cfg={**a,('other_assets_model' if kind=='asset' else 'other_liabilities_model'):model([row],measure=measure)}
     p=prepare(cfg,1,12);observations={row['series_id']:{measure:1639535.12}}
     self.assertAlmostEqual(resolve(p,0,catalog_balances=observations)['total'],2295.349168)
     with self.assertRaisesRegex(ValueError,'unavailable'):resolve(p,0,catalog_balances={})
  bad={**a,'other_assets_model':model([rows[-1]],measure='quarter_to_date')}
  with self.assertRaises(ValueError):prepare_other_assets(bad,1,12)
 def test_real_products_both_profiles_and_cadences(self):
  for fixture,ppy in [('core_bank_test_base.json',12),('core_bank_test_base.json',4),('parity/configs/pf_b_base.json',4)]:
   c=json.loads(Path('foundry/fixtures',fixture).read_text());a=c['assumptions'];a['periods_per_year']=ppy
   if ppy==12:a.update(n_periods=12,capital_raises=[],scheduled_borrowings=[])
   for key in ['lending_products','deposit_products']:
    for i,p in enumerate(a[key]):p['source_catalog_id']=key+str(i)
   rows=[x for x in balance_catalog(a) if x['key']=='lending_products'];a.update(other_assets_mode='formula_level',other_assets_model=model(rows))
   # Liability consumer uses the same catalog source, not a separate balance implementation.
   a.update(other_liabilities_mode='formula_level',other_liabilities_model=model(rows[:1]))
   r=run_v2(c);products=[p for p in r['products'] if p['family']=='lending'];n=len(r['financials']['is']['fees'])
   for comp,prod in zip(r['other_assets_detail']['components'],products):
    balances=prod['bal'];balances=balances[1:] if len(balances)==n+1 else balances
    for value,bal in zip(comp['amount'],balances):self.assertAlmostEqual(value,bal*.0014,delta=.02)
   for v,x in zip(r['other_liabilities']['components'][0]['amount'],r['other_assets_detail']['components'][0]['amount']):self.assertAlmostEqual(v,x,delta=.02)
   # IDs, not display names or list positions, bind the selection.
   if fixture=='core_bank_test_base.json' and ppy==4:
    old=r['other_assets_detail']['components'][0]['amount'];a['lending_products'][0]['name']='Renamed';a['lending_products'].reverse()
    self.assertEqual(old,run_v2(c)['other_assets_detail']['components'][0]['amount'])
    from .fiw import build_fiw,diff_import
    imported,_=diff_import(build_fiw(c)[0],c);self.assertEqual(imported['assumptions']['other_assets_model'],a['other_assets_model'])
if __name__=='__main__':unittest.main()
