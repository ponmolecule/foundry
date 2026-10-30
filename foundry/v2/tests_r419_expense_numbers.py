"""Output-only category snapshots agree with the existing expense engine paths."""
import copy,json,unittest
from pathlib import Path
from .run_q import run_v2

class ExpenseNumbersTests(unittest.TestCase):
    def test_full_native_category_paths(self):
        for ppy,n in [(12,60),(4,20)]:
            with self.subTest(ppy=ppy):
                cfg=json.loads((Path(__file__).parent.parent/'fixtures'/('universal_template_bank.json' if ppy==12 else 'core_bank_test_base.json')).read_text())
                if ppy==4:
                    cfg['assumptions']['nie_detail']={'categories':[{'name':'Rent','series_id':'rent','per_period':12000},{'name':'Insurance','series_id':'insurance','per_period':6000}], 'workforce':{'roles':[]},'fdic_bp_ann':0}
                cfg['assumptions'].update(periods_per_year=ppy,n_periods=n)
                before=copy.deepcopy(cfg);r=run_v2(cfg);self.assertEqual(cfg,before)
                ns=r['nie_detail_series'];cats=cfg['assumptions']['nie_detail']['categories']
                self.assertEqual(len(ns['category_details']),len(cats))
                for c,d in zip(cats,ns['category_details']):
                    self.assertEqual(d['name'],c['name']);self.assertEqual(d['series_id'],c.get('series_id',''))
                    for k in ['base','components','total']:self.assertEqual(len(d[k]),n)
                    for b,c,t in zip(d['base'],d['components'],d['total']):self.assertAlmostEqual(b+c,t)
                for i in range(n):
                    self.assertAlmostEqual(sum(d['total'][i] for d in ns['category_details']),ns['categories_total'][i],delta=.005*(len(cats)+2))

if __name__=='__main__':unittest.main()
