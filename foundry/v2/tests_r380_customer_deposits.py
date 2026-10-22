"""Customer-linked deposit stocks: live links, units, timing, validation and compatibility."""
import copy
import unittest
from .tests_deposit_retention import fixture, flat
from .deposit_balance import prepare, customer_balance
from .engine_q_a import run_pf_a
from .run_q import run_v2
from .validate_q import validate_errors_v2
from .audit_workbook import _product_rows


def config(ppy=12):
    c = fixture(); a = c['assumptions']
    a.pop('deposit_retention_pools'); a['deposit_products'] = a['deposit_products'][:1]
    a.update(periods_per_year=ppy, n_periods=60 if ppy == 12 else 20)
    p = a['deposit_products'][0]
    p.pop('retention_pool_id'); p.pop('pool_share_spec')
    p.update(name='Count-linked deposits', balance_mode='linked_customer_level', interest_balance_measure='period_average',
             balance_driver={'source':'customer_acquisition_count', 'series_id':'accounts', 'measure':'period_end', 'balance_per_customer_spec':flat(950)})
    a['cac_feeds'] = {'Accounts':{'customer_count_series_id':'accounts', 'series_id':'auc', 'beginning_customers':0,
        'intra_period_path':'monthly_flows', 'attrition_rate':0,
        'driver_specs':{'attrition_rate':{'source':'entered','mode':'flat','value':.1/12,'period':'month'}},
        'channels':[{'name':'Acquisition','method':'explicit','driver_specs':{'new_customers':{'source':'entered','mode':'flat','value':70000,'period':'month'}},'avg_auc_per_customer':0}]}}
    return c


class CustomerDepositTests(unittest.TestCase):
    def test_monthly_reconciliation_and_live_identity(self):
        c=config(); self.assertEqual(validate_errors_v2(c), [])
        o=run_pf_a(c); p=next(p for p in o['products'] if p['family']=='deposit')
        count=0
        for i in range(60):
            count=count*(1-.1/12)+70000
            self.assertAlmostEqual(p['bal'][i+1], count*950, places=5)
        self.assertAlmostEqual(p['intExp'][0], 66_500_000/2*.12/12)
        a=c['assumptions']; f=a['cac_feeds'].pop('Accounts');a['cac_feeds']['Renamed']=f
        self.assertEqual(run_pf_a(c)['bs']['deposits'],o['bs']['deposits'])
        f['channels'][0]['driver_specs']['new_customers']['value']=35000
        self.assertAlmostEqual(run_pf_a(c)['bs']['deposits'][1],33_250_000)
        a['deposit_products'][0]['balance_driver']['balance_per_customer_spec']=flat(1900)
        self.assertAlmostEqual(run_pf_a(c)['bs']['deposits'][1],66_500_000)

    def test_quarter_end_and_monthly_paired_average(self):
        c=config(4);a=c['assumptions'];p=a['deposit_products'][0]
        r=customer_balance(p,a,20,4)
        self.assertAlmostEqual(r['endingBalanceDollars'][0],208254.8611111111*950)
        m=config();mo=run_pf_a(m)
        qo=run_pf_a(c)
        self.assertAlmostEqual(qo['bs']['deposits'][1],mo['bs']['deposits'][3])
        p['balance_driver']['measure']='period_average'
        p['balance_driver']['balance_per_customer_spec']={'source':'entered','trajectory':'explicit','cadence':'month','values':[100,200,400]+[400]*57,'extend':'error'}
        r=customer_balance(p,a,20,4)
        self.assertAlmostEqual(r['endingBalanceDollars'][0],sum(x*y for x,y in zip(r['monthlyCount'][:3],[100,200,400]))/3)

    def test_validation(self):
        for key,value in [('series_id','missing'),('measure','annual_count'),('balance_per_customer_spec',flat(-1)),('balance_per_customer_spec',flat(float('nan'))),('balance_per_customer_spec',None)]:
            c=config();c['assumptions']['deposit_products'][0]['balance_driver'][key]=value
            with self.assertRaises(ValueError):prepare(c['assumptions'],60,12)
        c=config();c['assumptions']['deposit_products'][0]['new_deposits_per_period']=1
        with self.assertRaises(ValueError):prepare(c['assumptions'],60,12)

    def test_opening_book_and_scheduled_amounts(self):
        c=config();a=c['assumptions'];f=a['cac_feeds']['Accounts'];f['beginning_customers']=120
        p=a['deposit_products'][0];p['opening_balance']=120*950
        p['balance_driver']['balance_per_customer_spec']={'source':'entered','trajectory':'explicit','cadence':'year','values':[950,1000,1100,1200,1300],'resolution':'step','extend':'error'}
        r=customer_balance(p,a,60,12)
        self.assertAlmostEqual(r['monthlyCount'][0],120*.9916666666666667+70000)
        self.assertEqual(r['monthlyDollarsPerCustomer'][11:14],[950,1000,1000])
        out=run_pf_a(c);prod=next(x for x in out['products'] if x['family']=='deposit')
        self.assertAlmostEqual(prod['bal'][0],114000)
        self.assertAlmostEqual(prod['intExp'][0],(114000+r['endingBalanceDollars'][0])/2*.12/12)

    def test_public_units_audit_and_entered_equivalence(self):
        c=config(); raw=run_pf_a(c);pub=run_v2(c); p=next(p for p in pub['products'] if p['family']=='deposit')
        self.assertAlmostEqual(p['detailExact']['bal'][1],66500)
        self.assertEqual(p['depositCustomerCalculation']['monthlyDollarsPerCustomer'][0],950)
        rows=_product_rows(pub,60,raw)
        self.assertTrue(any(r[3]=='$ / customer' and r[4][0]==950 for r in rows))
        self.assertTrue(any(r[3]=='count' and r[4][0]==70000 for r in rows))
        legacy=copy.deepcopy(c);q=legacy['assumptions']['deposit_products'][0];q['balance_mode']='level'
        q['ending_balance_spec']={'source':'entered','trajectory':'explicit','cadence':'month','values':raw['bs']['deposits'][1:],'extend':'error'}
        r=run_pf_a(legacy)
        for k in ('bs','is'):self.assertEqual(raw[k],r[k])


if __name__=='__main__':unittest.main()
