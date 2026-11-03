"""Economic exclusion, identity preservation and r458 regression gates."""
import copy, json, unittest
from pathlib import Path
from .component_switches import prepare, inventory, states, disclosure
from .engine_q_a import run_pf_a
from .run_q import run_v2
from .tests_fee_quantity_links import fixture, quantities


class Tests(unittest.TestCase):
    def test_r458_full_output_baseline(self):
        import hashlib
        manifest=json.loads(Path('foundry/fixtures/r458_all_on_hashes.json').read_text())
        for path,expected in manifest['sha256'].items():
            with self.subTest(path=path):
                result=run_v2(json.loads(Path(path).read_text()))
                digest=hashlib.sha256(json.dumps(result,sort_keys=True,default=str).encode()).hexdigest()
                self.assertEqual(digest,expected)

    def test_all_on_exact_and_restore(self):
        c=fixture();baseline=run_v2(c);draft=copy.deepcopy(c)
        for r in inventory(draft):r['node']['scenario_enabled']=True
        self.assertEqual(run_pf_a(c),run_pf_a(draft))
        draft['assumptions']['obs_exposures'][1]['scenario_enabled']=False
        original=copy.deepcopy(draft);run_v2(draft);self.assertEqual(draft,original)
        draft['assumptions']['obs_exposures'][1]['scenario_enabled']=True
        self.assertEqual(run_v2(draft)['financials'],baseline['financials'])

    def test_off_product_zero_link_all_scenarios(self):
        c=fixture();p=c['assumptions']['obs_exposures'][1];p['scenario_enabled']=False
        r=run_v2(c)
        self.assertTrue(all(v==0 for v in quantities(r,'tpv')))
        self.assertTrue(all(v==0 for v in quantities(r,'migrated')))
        self.assertTrue(r['component_inclusion']['warnings'])
        for overlay in ({},{'charge_off_mult':2.5},{'dfast_severe_rates':{'ci':.2}}):
            cc=copy.deepcopy(c);cc['scenario_overlays']=overlay
            e=run_pf_a(cc)
            for p in e['products']:
                if p['family']=='obs':self.assertEqual(p['fees'],[0.]*36)

    def test_leaf_equals_controlled_deletion(self):
        c=fixture();c['assumptions']['obs_exposures'][0]['fee_streams'][0]['scenario_enabled']=False
        deleted=copy.deepcopy(c);deleted['assumptions']['obs_exposures'][0]['fee_streams']=[]
        off=run_pf_a(c);gone=run_pf_a(deleted)
        self.assertEqual(off['bs'],gone['bs']);self.assertEqual(off['is'],gone['is'])

    def test_parent_groups_keep_child_switch(self):
        c=fixture();p=c['assumptions']['obs_exposures'][1];p['inclusion_id']='owner';p['scenario_enabled']=False
        p['fee_streams'][0]['scenario_enabled']=False
        c['assumptions']['component_groups']=[dict(id='g1',name='Offering',members=['owner']),
                                            dict(id='g2',name='Second',members=['owner'],scenario_enabled=False)]
        p['scenario_enabled']=True
        self.assertFalse(next(r for r in states(c) if r['id']=='owner')['effective'])
        c['assumptions']['component_groups'][1]['scenario_enabled']=True
        self.assertFalse(next(r for r in states(c) if r['id']=='tpv')['effective'])
        self.assertTrue(next(r for r in states(c) if r['id']=='owner')['effective'])

    def test_off_skips_inputs_not_structure(self):
        c=fixture();p=c['assumptions']['lending_products'][0];p['scenario_enabled']=False
        p['yield_ann']='invalid';p['balance_mode']='nonexistent';p['loan_rollforward']={'bad':True}
        run_v2(c)
        c['assumptions']['component_groups']=[dict(id='g',members=['missing'])]
        with self.assertRaisesRegex(ValueError,'Unknown group member'):run_v2(c)

    def test_owned_workforce_floor_zero_shared_stays(self):
        from .tests_workforce_capacity import fixture as workforce_fixture
        c=workforce_fixture();a=c['assumptions'];a['lending_products'][0]['inclusion_id']='owner'
        a['lending_products'][0]['scenario_enabled']=False
        roles=a['nie_detail']['workforce']['roles'];roles[1]['owner_component_id']='owner'
        r=run_pf_a(c)
        self.assertTrue(all(x==0 for x in r['workforce']['counts'][1]))
        self.assertTrue(any(x>0 for x in r['workforce']['counts'][0]))
        self.assertTrue(disclosure(c)['shared'])

    def test_off_channel_preserves_published_source(self):
        from .tests_workforce_capacity import fixture as workforce_fixture
        c=workforce_fixture();feed=next(iter(c['assumptions']['cac_feeds'].values()))
        feed['channels'][0]['scenario_enabled']=False
        r=run_v2(c)
        self.assertTrue(r['component_inclusion']['excluded'])
        prepared=prepare(c)
        from .cac_feeder import cac_auc_rollforward
        f=next(iter(prepared['assumptions']['cac_feeds'].values()))
        roll=cac_auc_rollforward(f,12,12,assumptions=prepared['assumptions'])
        self.assertEqual([x['new_cust'] for x in roll['monthly']],[0.]*12)

    def test_off_deposit_quantity_and_saved_assumption(self):
        from .tests_r380_customer_deposits import config as deposit_fixture
        c=deposit_fixture();a=c['assumptions'];p=a['deposit_products'][0]
        p['source_catalog_id']='saved';p['scenario_enabled']=False
        saved=copy.deepcopy(p)
        other=copy.deepcopy(p);other.update(name='Enabled copy',source_catalog_id='consumer',scenario_enabled=True)
        other['balance_driver']['balance_per_customer_spec']={'source':'deposit_customer_amount','series_id':'saved'}
        a['deposit_products'].append(other)
        r=run_v2(c)
        off=next(x for x in r['products'] if x['name']==p['name'])
        self.assertEqual(off['bal'],[0.]*len(off['bal']))
        on=next(x for x in r['products'] if x['name']=='Enabled copy')
        self.assertGreater(on['bal'][-1],0)
        self.assertEqual(p,saved)

    def test_opening_reconciliation_cash_not_equity(self):
        c=fixture();a=c['assumptions'];p=a['lending_products'][0]
        p['opening_balance']=1_000_000;p['scenario_enabled']=False
        r=run_v2(c);bridge=r['component_inclusion']['comparison']
        self.assertEqual(bridge['opening_reconciliation']['equity'],0)
        self.assertEqual(bridge['opening_reconciliation']['sec'],0)
        self.assertGreater(bridge['opening_reconciliation']['cash']-bridge['opening_reconciliation']['borrow'],0)
        for d,f,x,t in zip(bridge['direct_removal'],bridge['funding_plug_effect'],
                           bridge['capital_tax_interaction_residual'],bridge['total_net_income_change']):
            self.assertAlmostEqual(d+f+x,t,places=8)

    def test_owned_pool_and_expense_zero_with_identity(self):
        from .tests_cost_recovery import _assumptions
        from .cost_pools import cost_pool_series_map
        c=fixture();a=c['assumptions'];a.update(_assumptions(12,36))
        owner=a['lending_products'][0];owner.update(inclusion_id='owner',scenario_enabled=False)
        for node in [a['cost_pools'][0],a['nie_detail']['categories'][0],a['nie_detail']['workforce']['roles'][0]]:
            node['owner_component_id']='owner'
        prepared=prepare(c);aa=prepared['assumptions']
        self.assertEqual(aa['nie_detail']['workforce']['roles'][0]['expense_series_id'],'wf-exp-platform')
        self.assertEqual(cost_pool_series_map(aa,36,12)['pool-platform'],[0.]*36)
        run_v2(c)

    def test_off_feed_opening_and_all_activity_zero(self):
        from .tests_workforce_capacity import fixture as workforce_fixture
        from .cac_feeder import cac_auc_rollforward
        c=workforce_fixture();feed=next(iter(c['assumptions']['cac_feeds'].values()))
        feed.update(beginning_customers=100,beginning_auc=100000,scenario_enabled=False)
        p=prepare(c);roll=cac_auc_rollforward(next(iter(p['assumptions']['cac_feeds'].values())),12,12,assumptions=p['assumptions'])
        self.assertEqual([x['new_cust'] for x in roll['monthly']],[0.]*12)
        self.assertEqual([x['end_cust'] for x in roll['monthly']],[0.]*12)
        run_v2(c)

    def test_profile_b_opening_cash_offset(self):
        from .engine_q_b import run_pf_b
        from .component_switches import comparison
        c=json.loads(Path('foundry/fixtures/parity/configs/pf_b_base.json').read_text())
        c['assumptions']['lending_products'][0]['scenario_enabled']=False
        r=run_pf_b(c);b=comparison(c,r)
        self.assertEqual(b['opening_reconciliation']['equity'],0)
        self.assertEqual(b['opening_reconciliation']['sec'],0)
        self.assertGreater(b['opening_reconciliation']['cash'],0)

    def test_export_disclosure(self):
        c=fixture();c['assumptions']['obs_exposures'][1]['scenario_enabled']=False;r=run_v2(c)
        from .audit_workbook import calculation_audit_workbook
        wb=calculation_audit_workbook(c,r)
        self.assertIn('Component Inclusion',wb.sheetnames)
        from .exec_pdf import exec_summary_pdf
        self.assertTrue(exec_summary_pdf(c,r).startswith(b'%PDF'))

if __name__=='__main__':unittest.main()
