"""Attrition editor round-trip value is consumed by the engine without two-decimal rounding."""
import json
import subprocess
import unittest
from pathlib import Path
from .cac_feeder import cac_auc_rollforward


class PrecisionTests(unittest.TestCase):
    def test_authoring_round_trip_and_engine(self):
        node = subprocess.run(['node', str(Path('web/tests_r357_precision_capacity.cjs'))],
                              check=True, text=True, capture_output=True)
        authored = json.loads(node.stdout)
        self.assertTrue(authored['ok'])
        rate = authored['stored_rate']
        self.assertEqual(rate, .0083333)
        feed = {'beginning_customers':1000, 'channels':[], 'intra_period_path':'monthly_flows',
                'driver_specs':{'attrition_rate':{'source':'entered','trajectory':'flat',
                                                 'value':rate,'period':'month'}}}
        # JSON is the same numeric persistence/transport representation as a saved model.
        feed = json.loads(json.dumps(feed))
        result = cac_auc_rollforward(feed,12,12)
        self.assertAlmostEqual(result['monthly'][0]['cust_lost'],8.3333,places=10)
        self.assertAlmostEqual(result['monthly'][11]['end_cust'],1000*(1-rate)**12,places=8)
        self.assertGreater(abs(result['monthly'][11]['end_cust'] - 1000*(1-.0083)**12),.3)

if __name__ == '__main__': unittest.main()
