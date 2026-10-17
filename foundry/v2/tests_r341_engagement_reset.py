"""r341: a real engagement reset, and a fresh engagement no longer locks itself on first render."""
import copy,json,os,re,subprocess,unittest
from foundry.v2.engagement_setup import initialize,policy,reset,apply,fingerprints
ROOT=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def bank():
    t=json.load(open(os.path.join(ROOT,'foundry/fixtures/parity/configs/pf_a_base.json')))
    t['proposed_bank']='Reset Bank';t['target_state']['initial_capital']=2e7
    t['charter_profile']={'charter_type':'national','target_opening':'2027-01-01','state':'TX','cblr_election':True}
    t['assumptions'].update(periods_per_year=4,n_periods=12)
    t['pre_opening']={'expenses':[{'name':'Legal','amount':250000}]}
    return initialize(t)

def edited():
    c=bank()
    for p in c['assumptions']['lending_products']+c['assumptions']['deposit_products']:
        for k,v in p.items():
            if isinstance(v,(int,float)) and not isinstance(v,bool):p[k]=0
    c['assumptions']['tax_rate']=0.25
    return c

class Reset(unittest.TestCase):
    def test_zeroes_still_lock_and_areas_report_it(self):
        p=policy(edited());self.assertFalse(p['early'])
        locks={a['id'] for a in p['areas'] if a['locks']}
        self.assertEqual(locks,{'lending','deposits','other'})
        self.assertEqual({a['id']:a['count'] for a in p['areas']}['lending'],4)

    def test_partial_reset_keeps_kept_areas_locking(self):
        r=reset(edited(),['lending'])
        self.assertFalse(r['early']);self.assertEqual(r['cleared'],['Lending'])
        self.assertEqual(r['cfg']['assumptions']['lending_products'],[])
        self.assertEqual(len(r['cfg']['assumptions']['deposit_products']),2)
        self.assertIn('Deposit inputs',r['dependencies'])

    def test_reset_all_unlocks_and_cadence_applies(self):
        c=edited();r=reset(c,['all']);out=r['cfg']
        self.assertTrue(r['early']);self.assertFalse(r['was_early'])
        self.assertEqual(out['pre_opening'],c['pre_opening'])
        self.assertEqual(out['target_state']['initial_capital'],2e7)
        self.assertEqual(out['charter_profile'],c['charter_profile'])
        self.assertEqual(out['assumptions']['tax_rate'],0.25,'other settings are kept, not reverted')
        self.assertEqual(out['step_0']['modules'],[],'balance-driven modules follow the emptied product lists')
        self.assertEqual(r['new_errors'],[])
        m=apply(out,{'periods_per_year':12})
        self.assertEqual((m['assumptions']['periods_per_year'],m['assumptions']['n_periods']),(12,36))

    def test_deletes_not_zeroes(self):
        c=edited();c['assumptions']['other_assets_model']={'components':[{'name':'x'}]};c['assumptions']['other_assets_mode']='formula_level'
        c['assumptions']['nie_detail']={'categories':[{'name':'Rent','amount':1}]}
        out=reset(c,['balances','expenses'])['cfg']['assumptions']
        for k in ('other_assets_model','other_assets_mode','nie_detail'):self.assertNotIn(k,out)

    def test_readding_after_reset_locks_again(self):
        out=reset(edited(),['all'])['cfg'];out['assumptions']['lending_products']=[{'opening_balance':1}]
        self.assertFalse(policy(out)['early'])

    def test_edited_curves_reset(self):
        c=bank();c['assumptions']['rate_curves']={'sofr':{'edited':True,'path_q':[.04]*12},'current_policy':{'mid':.04}}
        self.assertFalse(policy(c)['early'])
        r=reset(c,['curves']);self.assertTrue(r['early'])
        self.assertNotIn('sofr',r['cfg']['assumptions']['rate_curves']);self.assertIn('current_policy',r['cfg']['assumptions']['rate_curves'])

    def test_legacy_file_without_baseline(self):
        c=edited();c.pop('authoring_setup')
        r=reset(c,['deposits']);self.assertFalse(r['early']);self.assertEqual(r['dependencies'],['Lending inputs'])
        self.assertTrue(reset(c,['lending','deposits'])['early'])

    def test_rejects_empty_or_unknown(self):
        for bad in ([],['nope'],None,'all'):
            with self.assertRaises(ValueError):reset(bank(),bad)

    def test_generated_catalog_id_does_not_lock(self):
        c=bank()
        for p in c['assumptions']['deposit_products']+c['assumptions']['lending_products']:p['source_catalog_id']='product-source-x'
        self.assertTrue(policy(c)['early'])
        self.assertEqual(fingerprints(c),fingerprints(bank()))

class Console(unittest.TestCase):
    def test_console_wiring(self):
        h=open(os.path.join(ROOT,'web/console_v2.html')).read()
        for f in ('engagementResetOpen','engagementResetToggle','engagementResetConfirm','engagementResetClose','_engResetHtml'):
            self.assertIn('function '+f,h)
        self.assertIn("action:'reset'",h)
        self.assertIn('Reset engagement\\u2026',h)
        self.assertIn('Reset inputs to unlock',h)
        self.assertIn("_engReset=null;   // r341",h)
        r=subprocess.run(['node',os.path.join(ROOT,'web/tests_r341_engagement_reset.cjs')],capture_output=True,text=True)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)

if __name__=='__main__':unittest.main(verbosity=2)
