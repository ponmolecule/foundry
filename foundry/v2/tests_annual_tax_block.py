import copy
import unittest
from .tests_external_tax import cfg, inp, rule
from .tax_blocks import plan
from .external_tax import ExternalTaxLedger, validate


def setup(ppy=12):
    c=cfg();a=c['assumptions'];a.update(periods_per_year=ppy,n_periods=ppy*3,tax_rate=.21)
    a['tax_policy']={'nol_utilization_limit_pct':.8}
    m=a['external_tax'];m['inputs'] += [dict(inp('opening',250),measure='level'),inp('state',.065,'scalar')]
    return c


def draft():
    return dict(kind='annual_state_federal',name='Annual provision',fiscal_year_end_month=12,
                deduct_state=True,set_current=True,bindings=dict(taxable_income='bank_pretax',
                state_rate='state',federal_rate='configured_tax_rate',opening_losses='opening',
                utilization_limit='configured_nol_limit'))


def calculate(path,ppy=4,c=None):
    c=plan(c or setup(ppy),draft())['cfg'];x=ExternalTaxLedger(c,c['assumptions'],ppy)
    for i,value in enumerate(path,1):
        r=x.evaluate(i,value)
        assert x.evaluate(i,value)==r
        x.commit(r)
    return x,c


class AnnualTaxBlockTests(unittest.TestCase):
    def test_annual_independent_totals_and_monthly_quarterly_parity(self):
        for path in ([-300,100,100,300,-200,-100,0,0,500,-100,200,300],
                     [1000,-900,-300,500]*3,[0]*12):
            q,c=calculate(path);m,_=calculate([p/3 for p in path for _ in range(3)],12)
            opening=250
            for y in range(3):
                income=sum(path[y*4:y*4+4]);state=max(0,income*.065)
                base=income-state;used=min(opening,max(0,base)*.8)
                expected=state+(max(0,base)-used)*.21
                self.assertAlmostEqual(expected,sum(r['tax'] for r in q.rows[y*4:y*4+4]))
                opening=opening+max(0,-base)-used
                self.assertAlmostEqual(opening,q.rows[y*4+3]['nol'])
            for i,r in enumerate(q.rows):
                self.assertAlmostEqual(r['tax'],sum(v['tax'] for v in m.rows[i*3:i*3+3]))

    def test_recovery_reverses_provision_without_creating_future_loss_benefit(self):
        x,_=calculate([1000,-900,-300,500]+[0]*8)
        self.assertGreater(x.rows[0]['tax'],0)
        self.assertLess(x.rows[1]['tax'],0)
        self.assertAlmostEqual(sum(r['tax'] for r in x.rows[:3]),0)
        self.assertEqual(x.rows[2]['dtaNet'],0)

    def test_preview_cancel_semantics_and_opt_in_posting(self):
        c=setup();before=copy.deepcopy(c);d=draft();d['set_current']=False
        p=plan(c,d)
        self.assertEqual(c,before)
        self.assertEqual(p['cfg']['assumptions']['external_tax']['inputs'],c['assumptions']['external_tax']['inputs'])
        self.assertEqual(p['summary']['current_after'],'provision')
        self.assertEqual(len(p['summary']['generated']),10)

    def test_adopts_existing_partial_rules_and_keeps_ids_and_inputs(self):
        c=setup();m=c['assumptions']['external_tax']
        flag=inp('old_flag',0,'scalar');flag['amount_spec']=dict(source='entered',trajectory='explicit',cadence='month',values=[int(i%12==0) for i in range(36)])
        m['inputs'].append(flag)
        m['rules']=[rule('income_ytd','bank_pretax+(1-old_flag)*prior(income_ytd,0)'),
                    rule('state_ytd','max(0,income_ytd*state)'),
                    rule('state_provision','state_ytd-(1-old_flag)*prior(state_ytd,0)'),
                    rule('federal_base_ytd','income_ytd-state_ytd')]
        p=plan(c,draft())
        self.assertEqual(len(p['summary']['reused']),4)
        self.assertEqual(len(p['summary']['generated']),6)
        self.assertEqual(p['cfg']['assumptions']['external_tax']['inputs'],m['inputs'])
        new=p['cfg']['assumptions']['external_tax']['rules']
        self.assertEqual(next(x for x in new if x['id']=='income_ytd')['expression'],'bank_pretax + (1 - tax_year_start) * prior(income_ytd, 0)')
        self.assertIn('old_flag',m['rules'][0]['expression'])
        x=ExternalTaxLedger(p['cfg'],p['cfg']['assumptions'],12)
        self.assertGreater(x.evaluate(1,10000)['tax'],0)

    def test_edit_reuses_rules_without_duplicates_or_losing_standalone_work(self):
        c=setup();c['assumptions']['external_tax']['rules']=[rule('unrelated','0')]
        p=plan(c,draft());d=draft();d['id']=p['block']['id'];d['deduct_state']=False
        e=plan(p['cfg'],d)
        self.assertEqual(len(e['cfg']['assumptions']['external_tax']['blocks']),1)
        self.assertEqual(len(e['cfg']['assumptions']['external_tax']['rules']),11)
        self.assertIn('unrelated',[r['id'] for r in e['cfg']['assumptions']['external_tax']['rules']])

    def test_salary_income_rates_and_state_deduction_remain_live(self):
        x,_=calculate([100]*12);y,_=calculate([200]*12)
        self.assertNotEqual(x.rows[3]['tax'],y.rows[3]['tax'])
        c=setup(4);d=draft();d['deduct_state']=False;p=plan(c,d)['cfg']
        z=ExternalTaxLedger(p,p['assumptions'],4)
        self.assertGreater(z.evaluate(1,1000)['tax'],calculate([1000]*12)[0].rows[0]['tax'])

    def test_rejects_invalid_rates_opening_inputs_and_periods(self):
        for key,value in [('fiscal_year_end_month',True),('fiscal_year_end_month',13),('deduct_state',None)]:
            d=draft();d[key]=value
            with self.assertRaises(ValueError):plan(setup(),d)
        for source,value in [('state',1.1),('opening',-1)]:
            c=setup();next(x for x in c['assumptions']['external_tax']['inputs'] if x['id']==source)['amount_spec']['value']=value
            with self.assertRaises(ValueError):plan(c,draft())
        d=draft();d['bindings']['opening_losses']='provision'
        with self.assertRaises(ValueError):plan(setup(),d)
        d=draft();d['fiscal_year_end_month']=2
        with self.assertRaises(ValueError):plan(setup(4),d)

    def test_partial_first_tax_year_rejected_instead_of_inventing_history(self):
        c=setup();d=draft();d['fiscal_year_end_month']=6
        with self.assertRaisesRegex(ValueError,'begin at tax-year start'):plan(c,d)

    def test_fiscal_calendar_resets_are_automatic(self):
        c=setup();c.setdefault('charter_profile',{})['target_opening']='2027-07-01'
        d=draft();d['fiscal_year_end_month']=6
        p=plan(c,d)
        x=ExternalTaxLedger(p['cfg'],p['cfg']['assumptions'],12)
        for i in range(1,14):r=x.evaluate(i,100);x.commit(r)
        self.assertEqual(x.rows[12]['operands']['tax_year_start'],1)
        self.assertEqual(x.rows[12]['year'],x.rows[11]['year']+1)

    def test_engine_and_workbook_expose_live_calculation_once(self):
        from .run_q import run_v2
        from .audit_workbook import calculation_audit_workbook
        c=plan(setup(),draft())['cfg'];r=run_v2(c)
        self.assertEqual(r['tax_interim']['method'],'external')
        for row in r['tax_interim']['rows']:
            self.assertAlmostEqual(row['taxCurrent'],row['stateProvision']+row['federalProvision'],delta=.010001)
        wb=calculation_audit_workbook(c,r)
        text=' '.join(str(v) for row in wb['Income Taxes'].values for v in row)
        self.assertIn('Prior-year NOL used',text)
        self.assertNotIn('ERROR:',text)
