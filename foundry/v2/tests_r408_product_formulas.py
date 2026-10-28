import copy
import unittest
from .tests_r386_reuse import setup,attach_formula,linked,factor
from .product_formula_costs import move_formula,verified_move,prepare
from .engine_q_a import run_pf_a
from .run_q import run_v2
from .validate_q import validate_errors_v2


def config(ppy=12):
    c=attach_formula(setup(ppy));a=c['assumptions']
    a.setdefault('obs_exposures',[]).append({'name':'Operating Account','call_report_line':'obs','_fee_product':True,'fee_streams':[]})
    cat=a['nie_detail']['categories'][0]
    cat['linked_components'].append({'driver':'formula_driver','component_id':'fraud','name':'Account Fraud',
        'base_terms':[{'sign':1,'name':p['name'],'factors':[linked('catalog_quantity','deposit.'+p['source_catalog_id']+'.balance',measure='period_end')]} for p in a['deposit_products']],
        'factors':[dict(factor(.001),rate_period='year')]})
    return c

class FormulaCosts(unittest.TestCase):
    def test_transfer_both_formulas_preserves_financials_and_attribution(self):
        for ppy in (12,4):
            for gross in (0,.08):
                c=config(ppy);c['assumptions']['nie_detail']['other_gross_up_rate']=gross
                orig=copy.deepcopy(c);pi=len(c['assumptions']['obs_exposures'])-1
                before=copy.deepcopy(c)
                moved=verified_move(c,'obs_exposures',pi,'agreement','fraud')['config']
                self.assertEqual(c,before)
                c=moved
                c=verified_move(c,'obs_exposures',pi,'agreement','participation')['config']
                self.assertEqual(orig['assumptions']['nie_detail']['categories'][0]['linked_components'][1]['component_id'],'fraud')
                self.assertEqual(c['assumptions']['nie_detail']['categories'][0]['linked_components'],[])
                self.assertEqual(validate_errors_v2(c),[])
                old=run_pf_a(orig);new=run_pf_a(c)
                p=next(x for x in new['products'] if x['name']=='Operating Account')
                expected=old['nie_linked_by_category']['total']
                for x,y in zip(p['passCost'],expected):self.assertAlmostEqual(x,y,places=5)
                public=run_v2(c);row=next(x for x in public['ftp']['rows'] if x['name']=='Operating Account')
                self.assertGreater(row['opex'],0)
                self.assertEqual(new['bs']['deposits'],old['bs']['deposits'])

    def test_reject_referenced_category_and_missing_source(self):
        c=config();pi=len(c['assumptions']['obs_exposures'])-1
        c['assumptions']['test_observer']={'series_id':'agreement'}
        with self.assertRaisesRegex(ValueError,'referenced elsewhere'):move_formula(c,'obs_exposures',pi,'agreement','fraud')
        c=config();m=move_formula(c,'obs_exposures',pi,'agreement','fraud')
        formula=m['assumptions']['obs_exposures'][pi]['fee_streams'][0]['cost']['params']['formula']
        formula['base_terms'][0]['factors'][0]['series_id']='deposit.missing.balance'
        self.assertTrue(validate_errors_v2(m))

    def test_no_silent_net_cost_cycle_or_duplicate_transfer(self):
        c=config();pi=len(c['assumptions']['obs_exposures'])-1
        m=move_formula(c,'obs_exposures',pi,'agreement','fraud')
        with self.assertRaisesRegex(ValueError,'missing or ambiguous'):move_formula(m,'obs_exposures',pi,'agreement','fraud')
        f=m['assumptions']['obs_exposures'][pi]['fee_streams'][0]['cost']['params']['formula']
        f['factors']=[{'kind':'linked','source':'net_fee_income'}]
        with self.assertRaisesRegex(ValueError,'not available before'):prepare(m['assumptions'],60,12)

    def test_links_remain_live_after_transfer(self):
        c=config();pi=len(c['assumptions']['obs_exposures'])-1
        moved=move_formula(move_formula(c,'obs_exposures',pi,'agreement','fraud'),
                           'obs_exposures',pi,'agreement','participation')
        for model in (c,moved):
            model['assumptions']['deposit_products'][0]['name']='Renamed balance owner'
            model['assumptions']['deposit_products'][0]['rate_paid_ann']=.02
            model['assumptions']['cac_feeds']['Accounts']['channels'][1]['driver_specs']['new_customers']['value']=12
        old=run_pf_a(c);new=run_pf_a(moved)
        product=next(p for p in new['products'] if p['name']=='Operating Account')
        for expected,actual in zip(old['nie_linked_by_category']['total'],product['passCost']):
            self.assertAlmostEqual(expected,actual,places=5)

if __name__=='__main__':unittest.main()
