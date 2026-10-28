import copy
import unittest
from .tests_r408_product_formulas import config
from .product_formula_costs import move_formula

class DuplicateMove(unittest.TestCase):
    def test_same_name_blocks_without_mutation_for_any_existing_stream(self):
        for stream in ({'name':'Account Fraud'}, {'name':'  ACCOUNT FRAUD  ','cost':{'kind':'none'}}):
            c=config();pi=len(c['assumptions']['obs_exposures'])-1
            c['assumptions']['obs_exposures'][pi]['fee_streams']=[stream]
            before=copy.deepcopy(c)
            with self.assertRaisesRegex(ValueError,'already exists'):
                move_formula(c,'obs_exposures',pi,'agreement','fraud')
            self.assertEqual(c,before)

    def test_different_name_preserves_existing_and_moves_exactly_once(self):
        c=config();pi=len(c['assumptions']['obs_exposures'])-1
        c['assumptions']['obs_exposures'][pi]['fee_streams']=[{'name':'Separate cost'}]
        m=move_formula(c,'obs_exposures',pi,'agreement','fraud')
        self.assertEqual([s['name'] for s in m['assumptions']['obs_exposures'][pi]['fee_streams']],['Separate cost','Account Fraud'])
        self.assertEqual(len(c['assumptions']['nie_detail']['categories'][0]['linked_components']),2)
        self.assertEqual(len(m['assumptions']['nie_detail']['categories'][0]['linked_components']),1)

if __name__=='__main__':unittest.main()
