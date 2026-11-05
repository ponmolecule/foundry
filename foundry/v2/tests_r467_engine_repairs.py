"""Public monetary units and legacy component identity regression coverage."""
import copy
import json
import unittest
from pathlib import Path
from .component_switches import inventory, states, prepare
from .parity import _conv_fixed_assets
from .run_q import run_v2


class EngineRepairs(unittest.TestCase):
    def test_component_depreciation_public_units_and_no_mutation(self):
        from .tests_r464_fixed_asset_drivers import Drivers
        driver=Drivers()
        for ppy in (12, 4, 1):
            with self.subTest(ppy=ppy):
                raw=driver.resolve(driver.config(),ppy,ppy)
                before=copy.deepcopy(raw)
                public=_conv_fixed_assets(raw)
                r=raw['formula_level']['components'][0]
                p=public['formula_level']['components'][0]
                for key in ('amount','multiplier','depreciation'):
                    self.assertEqual(p[key],[(x/1000 if key=='depreciation' else round(x/1000,2)) for x in r[key]])
                for key in ('raw_driver','driver'):
                    self.assertEqual(p[key],r[key])
                self.assertEqual(raw,before)

    def test_run_payload_and_consumer_use_same_unit(self):
        c=json.loads(Path('foundry/fixtures/universal_template_bank.json').read_text())
        c['assumptions']['fixed_assets']={'mode':'formula_level','assets':[], 'formula_level':{
            'level_basis':'gross','opening_level':100000,'base_spec':{'source':'entered','trajectory':'flat','value':0},
            'components':[{'component_id':'tech','driver_spec':{'source':'link','link':{
                'kind':'workforce_role_count','series_id':'wf-count-ops-universal'}},
                'multiplier_spec':{'source':'entered','trajectory':'flat','value':12000},
                'depreciation_rate_spec':{'source':'entered','trajectory':'flat','value':.25,'period':'year'}}],
            'depreciation':{'kind':'component_rates','base_rate_spec':{'source':'entered','trajectory':'flat','value':0,'period':'year'}}}}
        fa=run_v2(c)['fixed_assets'];part=fa['formula_level']['components'][0]
        self.assertGreater(part['amount'][0],0)
        self.assertAlmostEqual(part['depreciation'][0],part['amount'][0]*.25/12,places=2)
        self.assertAlmostEqual(fa['depreciation_expense'][1],part['depreciation'][0],places=2)

    def test_legacy_feed_channel_aliases_are_scoped(self):
        c={'assumptions':{'cac_feeds':{'practices':{'series_id':'shared',
            'channels':[{'series_id':'shared','method':'explicit','params':{}}]}}}}
        before=copy.deepcopy(c)
        rows=states(c)
        self.assertEqual([r['id'] for r in rows],['cac_feeds.practices','cac_feeds.practices.channels.0'])
        self.assertEqual(rows[1]['parent'],rows[0]['id'])
        self.assertIs(prepare(c),c)
        self.assertEqual(c,before)
        c['assumptions']['cac_feeds']['practices']['scenario_enabled']=False
        rows=states(c)
        self.assertFalse(rows[1]['effective'])
        self.assertEqual(rows[1]['blocked_by'],['cac_feeds.practices'])
        off=prepare(c)
        self.assertTrue(off['assumptions']['cac_feeds']['practices']['channels'][0]['_scenario_off'])
        self.assertNotIn('_scenario_off',c['assumptions']['cac_feeds']['practices']['channels'][0])

    def test_explicit_inclusion_collisions_still_rejected(self):
        c={'assumptions':{'lending_products':[{'inclusion_id':'same'},{'inclusion_id':'same'}]}}
        with self.assertRaisesRegex(ValueError,'inclusion IDs must be unique'):states(c)

    def test_groups_and_owners_with_scoped_legacy_ids(self):
        c={'assumptions':{'cac_feeds':{'x':{'series_id':'shared','channels':[{'series_id':'shared'}]}},
            'nie_detail':{'workforce':{'roles':[{'series_id':'role','owner_component_id':'cac_feeds.x.channels.0'}]}},
            'component_groups':[{'id':'offering','members':['cac_feeds.x'],'scenario_enabled':False}]}}
        self.assertTrue(all(not r['effective'] for r in states(c)))
        c['assumptions']['component_groups'][0]['scenario_enabled']=True
        self.assertTrue(all(r['effective'] for r in states(c)))

if __name__=='__main__':unittest.main()
