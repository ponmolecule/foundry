"""Undrawn reserve ledger, statement postings, reporting and opt-in isolation."""
import copy,json,unittest
from pathlib import Path
from .run_q import run_v2
from .unused_commitments import resolve,prepare
from .validate_q import validate_config_v2


def reserve(util=.4,rate=.004083333):
    return {'utilization_spec':{'source':'entered','trajectory':'flat','value':util,'unit':'share'},
            'lifetime_loss_rate_spec':{'source':'entered','trajectory':'flat','value':rate,'unit':'share'},'opening_reserve':0}

class Tests(unittest.TestCase):
    def test_ledger_build_release_and_opening(self):
        p={'_bal':[0,100,200,50,0], 'unused_commitment_reserve':reserve(.4,.01)}
        p['unused_commitment_reserve']['opening_reserve']=2
        r=resolve(p,4,12)
        self.assertEqual(r['unusedCommitment'],[150,300,75,0])
        self.assertEqual(r['unusedCommitmentReserve'],[2,1.5,3,.75,0])
        self.assertEqual(r['unusedCommitmentProvision'],[-.5,1.5,-2.25,-.75])
        self.assertEqual(sum(r['unusedCommitmentProvision']),-2)
        p['unused_commitment_reserve']=reserve(1,.01)
        self.assertEqual(resolve(p,4,12)['unusedCommitment'],[0]*4)

    def test_validation_and_cadence(self):
        for util in [0,-.1,1.1,float('nan')]:
            with self.assertRaises(ValueError):prepare({'unused_commitment_reserve':reserve(util)},4,12)
        for rate in [-.1,1.1,float('inf')]:
            with self.assertRaises(ValueError):prepare({'unused_commitment_reserve':reserve(rate=rate)},4,12)
        p={'unused_commitment_reserve':reserve()}
        p['unused_commitment_reserve']['lifetime_loss_rate_spec']={'source':'entered','trajectory':'explicit','cadence':'year','values':[.01,.02],'unit':'share'}
        for ppy in [4,12]:
            vs=prepare(p,ppy*2,ppy)['loss_rate'];self.assertEqual(vs[:ppy],[.01]*ppy);self.assertEqual(vs[ppy:],[.02]*ppy)
        with self.assertRaises(ValueError):prepare(dict(p,measurement='fair_value'),4,12)

    def test_full_statements_reporting_and_save(self):
        c=json.loads(Path('foundry/fixtures/universal_template_bank.json').read_text());a=c['assumptions']
        a['securities_yield']=0;a['cash_yield']=0;a['borrow_rate']=0;a['tax_rate']=0
        # Use an explicit clean retained loan so reserve is the only changed ledger.
        p=a['lending_products'][0];p['unused_commitment_reserve']=reserve()
        saved=copy.deepcopy(c);r=run_v2(c);self.assertEqual(c,saved)
        pub=r['products'][0];d=pub['detailExact'];n=len(d['unusedCommitmentProvision'])
        self.assertEqual(len(d['unusedCommitmentReserve']),n+1)
        for i in range(n):
            self.assertAlmostEqual(d['unusedCommitment'][i],d['bal'][i+1]*1.5)
            self.assertAlmostEqual(d['unusedCommitmentReserve'][i+1],d['unusedCommitment'][i]*.004083333)
            self.assertAlmostEqual(d['unusedCommitmentProvision'][i],d['unusedCommitmentReserve'][i+1]-d['unusedCommitmentReserve'][i])
        self.assertTrue(r['reporting']['ok'],r['reporting']['problems'])
        self.assertTrue(any(x['measure']=='unusedCommitmentProvision' for x in r['reporting']['results']))
        self.assertTrue(any(x['measure']=='unusedCommitmentReserve' for x in r['reporting']['results']))
        self.assertEqual(run_v2(json.loads(json.dumps(c)))['run_hash'],r['run_hash'])
        base=copy.deepcopy(c);del base['assumptions']['lending_products'][0]['unused_commitment_reserve'];b=run_v2(base)
        # Funded balances, charge-offs and funded allowance are unaffected.
        for key in ['bal','co','alll','provision']:
            self.assertEqual(pub['detailExact'][key],b['products'][0]['detailExact'][key])
        bs=r['financials']['bs'];old=b['financials']['bs'];inc=r['financials']['is'];oi=b['financials']['is']
        for i in range(n):
            # Public financial statements have historic cent-of-$000s rounding.
            self.assertAlmostEqual(inc['prov'][i]-oi['prov'][i],d['unusedCommitmentProvision'][i],delta=.021)
            self.assertAlmostEqual(bs['otherLiab'][i+1]-old.get('otherLiab',[a['other_liabilities']/1000]*(n+1))[i+1],d['unusedCommitmentReserve'][i+1],delta=.021)
            self.assertLess(inc['ni'][i],oi['ni'][i])
        # The separate liability must appear in the Call Report and not reduce funded ALLL.
        self.assertEqual(bs['alll'],old['alll'])
        recon=next(x for x in r['reporting']['reconciliation']['measures'] if x['class']=='unused_reserve')
        self.assertTrue(recon['ok']);self.assertIsNotNone(recon['engine_bank'])
        self.assertAlmostEqual(bs['unusedCommitmentReserve'][-1],d['unusedCommitmentReserve'][-1],delta=.011)
        from .audit_workbook import calculation_audit_workbook
        wb=calculation_audit_workbook(c,r)
        self.assertIn('Unused Commitments',wb.sheetnames)
        check=r['presentation']['derived'].get('balanceCheck')
        if check:self.assertTrue(all(abs(x or 0)<.1 for x in check))


    def test_monthly_first_quarterly_stocks_and_provision(self):
        m={'_bal':[0,100,200,300,200,100,0], 'unused_commitment_reserve':reserve()}
        q={'_bal':[0,300,0], 'unused_commitment_reserve':reserve()}
        mr=resolve(m,6,12);qr=resolve(q,2,4)
        self.assertEqual(qr['unusedCommitmentReserve'][1:],mr['unusedCommitmentReserve'][3::3])
        for i in range(2):self.assertAlmostEqual(qr['unusedCommitmentProvision'][i],sum(mr['unusedCommitmentProvision'][i*3:i*3+3]))
        q['unused_commitment_reserve']['utilization_spec']={'source':'entered','trajectory':'explicit','cadence':'month','values':[0,.4,.4,.4,.4,.4],'unit':'share'}
        with self.assertRaises(ValueError):prepare(q,2,4)

    def test_profile_b_fails_closed(self):
        c=json.loads(Path('foundry/fixtures/universal_template_bank.json').read_text())
        c['assumptions']['lending_products'][0]['unused_commitment_reserve']=reserve()
        c['parity_profile']='pf_b'
        with self.assertRaises(Exception):run_v2(c)

if __name__=='__main__':unittest.main()
