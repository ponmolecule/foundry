"""r356 capacity workforce: live links, monthly economics and dependency safety."""
import copy
import json
import unittest
from pathlib import Path
from .workforce import workforce_capacity_monthly, workforce_comp_series, workforce_count_series_by_id
from .engine_q_a import run_pf_a
from .engine_q_b import run_pf_b
from .run_q import run_v2
from .validate_q import validate_config_v2
from .audit_workbook import calculation_audit_workbook


def flat(value, **kw):
    return dict(source='entered', trajectory='flat', value=value, **kw)


def fixture():
    cfg=json.loads(Path('foundry/fixtures/parity/configs/pf_a_base.json').read_text())
    a=cfg['assumptions'];a['periods_per_year']=12;a['n_periods']=12
    sales={'role':'Sales','series_id':'sales','count':1,'annual_comp':12000,'hire_period':1}
    ops={'role':'Servicing','series_id':'ops','count':1,'annual_comp':120000,'hire_period':1,
         'capacity_count':{'series_id':'customers','measure':'cumulative_acquisitions',
                           'capacity_spec':flat(40),'minimum_spec':flat(1)}}
    a['nie_detail']={'categories':[], 'workforce':{'mode':'roles','roles':[sales,ops],
        'total_count_series_id':'total','default_payroll_load_rate':0,
        'default_salary_growth_spec':{'rate':0,'period':'year','method':'step','anchor':'model_year'}}}
    a['cac_feeds']={'Acquisition':{'series_id':'auc','customer_count_series_id':'customers',
        'beginning_customers':0,'beginning_auc':0,'intra_period_path':'monthly_flows',
        'driver_specs':{'attrition_rate':flat(.1/12,period='month')},
        'channels':[{'name':'Direct','method':'fte_productivity','driver_specs':{
            'ftes':{'source':'link','link':{'kind':'workforce_role_count','series_id':'sales','aggregation':'end'}},
            'per_fte':flat(20,period='month'),'comp_per_fte':flat(0,period='month'),
            'avg_auc_per_customer':flat(0)}}]}}
    return cfg


class CapacityTests(unittest.TestCase):
    def test_gross_and_active_and_live_link(self):
        a=fixture()['assumptions'];ops=a['nie_detail']['workforce']['roles'][1]
        d=workforce_capacity_monthly(ops,6,assumptions=a)
        self.assertEqual(d['source'],[20,40,60,80,100,120])
        self.assertEqual(d['counts'],[1,1,1.5,2,2.5,3])
        ops['capacity_count']['measure']='active_customers'
        active=workforce_capacity_monthly(ops,6,assumptions=a)
        self.assertLess(active['source'][-1],120)
        ops['capacity_count']['measure']='cumulative_acquisitions'
        a['nie_detail']['workforce']['roles'][0]['count']=2
        self.assertEqual(workforce_capacity_monthly(ops,6,assumptions=a)['counts'],[1,2,3,4,5,6])

    def test_zero_opening_windows_and_paths(self):
        a=fixture()['assumptions'];ops=a['nie_detail']['workforce']['roles'][1]
        ch=a['cac_feeds']['Acquisition']['channels'][0]
        ch['method']='explicit';ch['driver_specs']={'new_customers':{'source':'entered',
            'trajectory':'explicit','cadence':'month','period':'month','values':[0,0,10,0,0,0]}}
        self.assertEqual(workforce_capacity_monthly(ops,6,assumptions=a)['counts'],[0,0,1,1,1,1])
        a['cac_feeds']['Acquisition']['beginning_customers']=30
        self.assertEqual(workforce_capacity_monthly(ops,6,assumptions=a)['source'],[30,30,40,40,40,40])
        ops['hire_period']=2;ops['end_period']=4
        counts=workforce_count_series_by_id(a['nie_detail']['workforce'],'ops',6,12,assumptions=a)
        self.assertEqual(counts,[0,1,1,1,0,0])
        ops['capacity_count']['minimum_spec']={'source':'entered','trajectory':'explicit','cadence':'month',
            'values':[1,2,3,4,5,6]}
        self.assertEqual(workforce_capacity_monthly(ops,6,assumptions=a)['counts'],[1,2,3,4,5,6])

    def test_real_cycles_and_safe_dependency(self):
        a=fixture()['assumptions'];wf=a['nie_detail']['workforce']
        self.assertEqual(workforce_count_series_by_id(wf,'total',6,12,assumptions=a)[-1],4)
        link=a['cac_feeds']['Acquisition']['channels'][0]['driver_specs']['ftes']['link']
        for sid in ['ops','total']:
            link['series_id']=sid
            with self.assertRaisesRegex(ValueError,'circular workforce capacity'):
                workforce_capacity_monthly(wf['roles'][1],6,assumptions=a)
        link['series_id']='sales'
        self.assertEqual(workforce_capacity_monthly(wf['roles'][1],6,assumptions=a)['counts'][-1],3)

    def test_active_book_can_return_to_zero(self):
        a=fixture()['assumptions'];ops=a['nie_detail']['workforce']['roles'][1]
        ops['capacity_count']['measure']='active_customers'
        feed=a['cac_feeds']['Acquisition'];feed['driver_specs']['attrition_rate']=flat(1,period='month')
        feed['channels']=[{'name':'One cohort','method':'explicit','driver_specs':{'new_customers':
            {'source':'entered','trajectory':'explicit','cadence':'month','period':'month','values':[10,0,0]}}}]
        self.assertEqual(workforce_capacity_monthly(ops,3,assumptions=a)['counts'],[1,0,0])

    def test_bad_inputs(self):
        a=fixture()['assumptions'];ops=a['nie_detail']['workforce']['roles'][1]
        for key,value in [('capacity_spec',0),('capacity_spec',-1),('minimum_spec',-1),('capacity_spec',float('nan'))]:
            r=copy.deepcopy(ops);r['capacity_count'][key]=flat(value)
            with self.assertRaises(ValueError):workforce_capacity_monthly(r,6,assumptions=a)
        r=copy.deepcopy(ops);r['capacity_count']['series_id']='missing'
        with self.assertRaisesRegex(ValueError,'missing'):workforce_capacity_monthly(r,6,assumptions=a)

    def test_quarterly_payroll_is_sum_of_monthly_products(self):
        cfg=fixture();a=cfg['assumptions'];ops=a['nie_detail']['workforce']['roles'][1]
        ops['compensation_spec']={'source':'entered','trajectory':'explicit','cadence':'month',
            'period':'month','values':[100,200,300,400,500,600],'amount_basis':'per_unit'}
        m=workforce_comp_series(a['nie_detail']['workforce'],6,12,assumptions=a)
        q=workforce_comp_series(a['nie_detail']['workforce'],2,4,assumptions=a)
        self.assertEqual(q,[sum(m[:3]),sum(m[3:])])
        a['cac_feeds']['Acquisition']['channels'][0]['driver_specs']['per_fte']=flat(60,period='model_period')
        # 60 per quarter -> 20 per month; original model-period source units survive canonicalization.
        self.assertEqual(workforce_comp_series(a['nie_detail']['workforce'],2,4,assumptions=a),q)

    def test_full_engines_validation_and_audit(self):
        cfg=fixture();validate_config_v2(cfg)
        raw=run_pf_a(copy.deepcopy(cfg))
        self.assertEqual(raw['workforce']['counts'][1][:6],[1,1,1.5,2,2.5,3])
        self.assertEqual(raw['workforce']['role_expenses'][1][:6],[10000,10000,15000,20000,25000,30000])
        public=run_v2(copy.deepcopy(cfg))
        self.assertEqual(public['workforce']['role_expenses'][1][5],30)
        wb=calculation_audit_workbook(cfg,public)
        self.assertIn('Workforce',wb.sheetnames)
        self.assertIn('Workforce Capacity Detail',wb.sheetnames)
        self.assertTrue(any('Capacity source measure' in str(r) for r in wb['Workforce'].values))
        cfg['assumptions']['periods_per_year']=4;cfg['assumptions']['n_periods']=4
        bcfg=json.loads(Path('foundry/fixtures/parity/configs/pf_b_base.json').read_text())
        for key in ['nie_detail','cac_feeds','n_periods']:bcfg['assumptions'][key]=copy.deepcopy(cfg['assumptions'][key])
        b=run_pf_b(bcfg)
        self.assertAlmostEqual(b['workforce']['role_expenses'][1][0],35000)
        self.assertAlmostEqual(b['workforce']['role_expenses'][1][1],75000)

if __name__=='__main__':unittest.main()
