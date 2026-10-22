"""Explicit payable-base inclusion semantics and legacy exclusion compatibility."""
import copy, unittest
from .tests_r376_deferred import config
from .engine_q_a import run_pf_a
from .expense_sources import selection, TOTAL
from .run_q import run_v2

class InclusionTests(unittest.TestCase):
    def test_legacy_equivalent_inclusions_preserve_financials(self):
        for ppy in (12,4):
            legacy=config(ppy);explicit=copy.deepcopy(legacy)
            t=explicit['assumptions']['other_liabilities_model']['components'][0]['terms'][0]
            t.pop('exclude_category_ids');t['include_category_ids']=['office']
            a,b=run_pf_a(legacy),run_pf_a(explicit)
            self.assertEqual(a['bs'],b['bs']);self.assertEqual(a['is'],b['is'])
            self.assertEqual(b['other_liabilities_detail']['components'][0]['terms'][0]['include_category_ids'],['office'])

    def test_new_expenses_not_silently_added_to_explicit_base(self):
        c=config();a=c['assumptions'];t=a['other_liabilities_model']['components'][0]['terms'][0]
        t.pop('exclude_category_ids');t['include_category_ids']=['office']
        a['nie_detail']['categories'].append({'series_id':'new','name':'New expense','flow_spec':{'trajectory':'flat','value':24000,'period':'year'}})
        self.assertAlmostEqual(run_pf_a(c)['bs']['otherLiab'][1],10000)
        t['include_category_ids'].append('new');self.assertAlmostEqual(run_pf_a(c)['bs']['otherLiab'][1],12000)
        del t['include_category_ids'];t['exclude_category_ids']=['insurance']
        self.assertAlmostEqual(run_pf_a(c)['bs']['otherLiab'][1],12000) # legacy aggregate semantics retained

    def test_selected_identity_survives_rename_and_reorder(self):
        c=config();a=c['assumptions'];t=a['other_liabilities_model']['components'][0]['terms'][0]
        t.pop('exclude_category_ids');t['include_category_ids']=['office']
        a['nie_detail']['categories'][0]['name']='Renamed office';a['nie_detail']['categories'].reverse()
        self.assertAlmostEqual(run_pf_a(c)['bs']['otherLiab'][1],10000)
        self.assertEqual(selection(a,TOTAL,[],['office']),[1])

    def test_invalid_and_ambiguous_selections_fail_closed(self):
        a=config()['assumptions']
        for included in ([],['missing'],['office','office'],'office',[None]):
            with self.assertRaises(ValueError):selection(a,TOTAL,[],included)
        with self.assertRaises(ValueError):selection(a,TOTAL,['insurance'],['office'])
        with self.assertRaises(ValueError):selection(a,'office',[],['office'])
        with self.assertRaises(ValueError):selection(a,TOTAL,[],['insurance']) # independent settlement overlap
        with self.assertRaises(ValueError):selection(a,TOTAL,['missing'])

    def test_public_and_assumptions_audit_include_selection(self):
        c=config();t=c['assumptions']['other_liabilities_model']['components'][0]['terms'][0]
        del t['exclude_category_ids'];t['include_category_ids']=['office']
        r=run_v2(c);self.assertEqual(r['other_liabilities']['components'][0]['terms'][0]['include_category_ids'],['office'])
        import io, openpyxl
        from .fiw import build_fiw
        wb=openpyxl.load_workbook(io.BytesIO(build_fiw(c)[0]))
        self.assertTrue(any('.include_category_ids.0' in str(row[0]) for row in wb['ASSM_OTHER_LIAB'].iter_rows(values_only=True)))

if __name__=='__main__':unittest.main()
