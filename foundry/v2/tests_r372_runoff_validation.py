import copy
import unittest
from .tests_r369_lending_contracts import config
from .validate_q import validate_config_v2, ConfigErrorV2
from .run_q import run_v2


class RunoffValidationTests(unittest.TestCase):
    def test_new_contract_without_legacy_runoff(self):
        c = config(12)
        expected = run_v2(c)['products'][0]
        del c['assumptions']['lending_products'][0]['runoff_per_period']
        before = copy.deepcopy(c)
        validate_config_v2(c)
        actual = run_v2(c)['products'][0]
        self.assertEqual(actual, expected)
        self.assertEqual(c, before)

    def test_legacy_contract_still_requires_runoff(self):
        c = config(12)
        p = c['assumptions']['lending_products'][0]
        del p['runoff_per_period']
        del p['loan_rollforward']
        with self.assertRaisesRegex(ConfigErrorV2, 'runoff_per_period'):
            validate_config_v2(c)

    def test_missing_new_repayment_input_still_blocks_run(self):
        for field in ('payment_rate_spec', 'prepayment_rate_spec'):
            c = config(12)
            p = c['assumptions']['lending_products'][0]
            del p['runoff_per_period']
            del p['loan_rollforward'][field]
            with self.assertRaises(ValueError):
                run_v2(c)
