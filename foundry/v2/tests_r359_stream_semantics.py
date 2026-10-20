"""Flat source following, derived shares and pricing are independent contracts."""
import copy
import unittest
from .income_modules import fee_stream_q, _validate_fee_stream_shape


def stream(traj='flat',share=None,rate=.0014):
    s={'name':'Fee','quantity_series_id':'fee','basis':'transaction','driver':{'source':'stream_ref',
       'ref':'Purchases','trajectory':traj,'params':{}},'rate':{'behavior':'flat','params':{'per_unit':rate}},
       'cost':{'kind':'none','params':{}}}
    if share is not None:s['driver']['params']['coefficient']={'kind':'pct','semantics':'share','period':'month','trajectory':'flat','value':share}
    return s


class SemanticsTests(unittest.TestCase):
    def test_flat_follows_each_period_and_pricing_remains_separate(self):
        for q,volume in enumerate([100000,200000,300000],1):
            flat,derived=stream(),stream('derived',1)
            a={'stream_qty':{'Purchases':volume},'capture_stream_qty':{}}
            b=copy.deepcopy(a)
            self.assertAlmostEqual(fee_stream_q(flat,q,a,12)[0],volume*.0014)
            self.assertEqual(fee_stream_q(flat,q,{'stream_qty':{'Purchases':volume}},12),fee_stream_q(derived,q,b,12))
            self.assertEqual(a['capture_stream_qty']['fee'][q-1],volume)
            self.assertEqual(b['capture_stream_qty']['fee'][q-1],volume)
    def test_nonidentity_share_changes_quantity_before_pricing(self):
        ctx={'stream_qty':{'Purchases':100000},'capture_stream_qty':{}}
        revenue,_=fee_stream_q(stream('derived',.6),1,ctx,12)
        self.assertEqual(ctx['capture_stream_qty']['fee'][0],60000)
        self.assertAlmostEqual(revenue,84)
        with self.assertRaisesRegex(ValueError,'requires.*derived'):_validate_fee_stream_shape(stream('flat',.6))

if __name__=='__main__':unittest.main()
