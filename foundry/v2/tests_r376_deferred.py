"""Causal regression checks for automatic customer flows and expense-derived liabilities."""
import copy, json, unittest
from pathlib import Path
from .account_activity import catalog, resolve, ensure_flow_ids
from .cac_feeder import cac_auc_rollforward
from .engine_q_a import run_pf_a
from .engine_q_b import run_pf_b
from .run_q import run_v2
from .tests_opex_extensions import base_cfg
from .source_catalog import catalog as source_catalog
from .other_liabilities import prepare_other_liabilities


def config(ppy=12):
    c=base_cfg(ppy);a=c['assumptions'];a['capital_raises']=[]
    a['nie_detail']['categories']=[
        {'series_id':'office','name':'Office','flow_spec':{'trajectory':'flat','value':120000,'period':'year'}},
        {'series_id':'insurance','name':'Insurance','flow_spec':{'trajectory':'flat','value':36000,'period':'year'},'settlement':{'mode':'annual','first_payment_period':1}},
    ]
    a['cac_feeds']={'Practices':{'series_id':'auc','customer_count_series_id':'customers','beginning_customers':100,'attrition_rate':0,
        'channels':[{'name':'Sales','method':'explicit','params':{'new_customers_by_year':[120]},'avg_auc_per_customer':0}]}}
    a['other_liabilities_mode']='formula_level'
    a['other_liabilities_model']={'opening_balance':0,'base_spec':{'source':'entered','trajectory':'flat','value':0},'components':[
        {'component_id':'payable','name':'Accounts Payable','terms':[{'term_id':'office-days',
         'driver_spec':{'source':'link','link':{'kind':'operating_expense_flow','series_id':'operating_expense_categories'}},
         'exclude_category_ids':['insurance'],'days_spec':{'source':'entered','trajectory':'flat','value':30},'year_days':360,
         'multiplier_spec':{'source':'entered','trajectory':'flat','value':1}}]}]}
    return c


class DeferredTests(unittest.TestCase):
    def test_auto_flows_stable_identity_and_no_economic_changes(self):
        a=config()['assumptions'];f=a['cac_feeds']['Practices'];before=cac_auc_rollforward(copy.deepcopy(f),12,12,assumptions=copy.deepcopy(a))
        rows=catalog(a);sid=next(x['series_id'] for x in rows if x.get('field')=='new_customers' and 'channel' not in x)
        after=cac_auc_rollforward(f,12,12,assumptions=a);self.assertEqual(before['monthly'],after['monthly']);self.assertEqual(before['annual'],after['annual'])
        result,_=resolve(a,12,12);self.assertAlmostEqual(sum(result[sid]['values']),120)
        old=copy.deepcopy(f['activity_series_ids']);ch=copy.deepcopy(f['channels'][0]['activity_series_ids'])
        a['cac_feeds']['Renamed']=a['cac_feeds'].pop('Practices');f['channels'][0]['name']='Renamed channel';f['channels'].insert(0,{'name':'New','method':'explicit','params':{'new_customers_by_year':[0]}});ensure_flow_ids(a)
        self.assertEqual(old,f['activity_series_ids']);self.assertEqual(ch,f['channels'][1]['activity_series_ids'])
        f['activity_series_ids']['new_customers']='authored-custom';ensure_flow_ids(a);self.assertEqual(f['activity_series_ids']['new_customers'],'authored-custom')

    def test_legacy_straight_line_never_publishes_fake_gross(self):
        a=config()['assumptions'];f=a['cac_feeds']['Practices'];f['intra_period_path']='straight_line';f['activity_series_ids']={'new_customers':'old-id'}
        before=copy.deepcopy(f);self.assertEqual(catalog(a),[]);r,_=resolve(a,12,12);self.assertEqual(r,{});self.assertEqual(before,f)
        reason=next(x for x in source_catalog(a) if x['driver']=='unavailable');self.assertEqual(reason['consumers'],[]);self.assertIn('not gross',reason['unavailable_reason'])

    def test_payable_month_quarter_engine_and_live_updates(self):
        for ppy in (12,4):
            c=config(ppy);a=c['assumptions'];r=run_pf_a(c)
            self.assertAlmostEqual(r['bs']['otherLiab'][1],10000)
            t=r['other_liabilities_detail']['components'][0]['terms'][0]
            self.assertAlmostEqual(t['driver'][0],120000/ppy);self.assertEqual(t['days'][0],30)
            self.assertAlmostEqual(t['multiplier'][0],30/(360/ppy))
            a['nie_detail']['categories'][0]['flow_spec']['value']=240000
            self.assertAlmostEqual(run_pf_a(c)['bs']['otherLiab'][1],20000)
            if ppy==4:
                cb=json.loads(Path('foundry/fixtures/parity/configs/pf_b_base.json').read_text());cb['assumptions'].update({k:copy.deepcopy(a[k]) for k in ('nie_detail','other_liabilities_model','other_liabilities_mode','n_periods')});self.assertAlmostEqual(run_pf_b(cb)['bs']['otherLiab'][0],20000)

    def test_individual_expenses_additives_and_no_double_post(self):
        c=config();a=c['assumptions'];cat=a['nie_detail']['categories'][0]
        a['nie_detail']['workforce']={'mode':'roles','roles':[{'series_id':'ops','role':'Operations','count':2,'annual_comp':0,'hire_period':1}]}
        cat['linked_components']=[{'driver':'workforce_count','series_id':'ops','amount_spec':{'trajectory':'flat','value':6000,'period':'year'}}]
        # Additive category expenses are included, without posting a second P&L expense.
        base=copy.deepcopy(c);del base['assumptions']['other_liabilities_model'];base['assumptions'].pop('other_liabilities_mode')
        r=run_pf_a(c);b=run_pf_a(base);self.assertEqual(r['is']['otherOpex'],b['is']['otherOpex'])
        term=a['other_liabilities_model']['components'][0]['terms'][0];term['driver_spec']['link']['series_id']='office';term['exclude_category_ids']=[]
        self.assertAlmostEqual(run_pf_a(c)['bs']['otherLiab'][1],11000)
        term['days_spec']['value']=15;self.assertAlmostEqual(run_pf_a(c)['bs']['otherLiab'][1],5500)

    def test_invalid_basis_missing_sources_and_overlapping_settlement(self):
        for change in ('basis','days','missing','overlap'):
            c=config();a=c['assumptions'];t=a['other_liabilities_model']['components'][0]['terms'][0]
            if change=='basis':t['year_days']=0
            if change=='days':t['days_spec']['value']=-1
            if change=='missing':t['exclude_category_ids']=['missing']
            if change=='overlap':a['nie_detail']['categories'][0]['settlement']={'mode':'quarterly','first_payment_period':3}
            with self.assertRaises(ValueError):prepare_other_liabilities(a,12,12)

    def test_public_payload_and_browser_fixture(self):
        c=config();r=run_v2(c)
        self.assertAlmostEqual(r['financials']['bs']['otherLiab'][1],10)
        self.assertIn('account_activity',r);self.assertEqual(r['customer_acquisition']['Practices']['flowEligibility'],'gross')
        self.assertEqual(r['other_liabilities']['components'][0]['name'],'Accounts Payable')
        from .audit_workbook import calculation_audit_workbook
        from .fiw import build_fiw
        audit=calculation_audit_workbook(c,r)
        labels=[str(row[1] or '') for row in audit['Other Liabilities'].iter_rows(values_only=True)]
        self.assertTrue(any('days payable' in label for label in labels))
        import io, openpyxl
        fiw=openpyxl.load_workbook(io.BytesIO(build_fiw(c)[0]))
        keys=[str(row[0] or '') for row in fiw['ASSM_OTHER_LIAB'].iter_rows(values_only=True)]
        self.assertTrue(any('.days_spec' in key for key in keys))
        self.assertTrue(any('.exclude_category_ids.0' in key for key in keys))


if __name__=='__main__':unittest.main()
