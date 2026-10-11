"""Explicit expense eligibility changes only the configured gross-up charge."""
import copy,json,math
from .gross_up import calculate,validate
from .run_q import run_v2
from .validate_q import validate_errors_v2

def main():
    n=0
    def ck(name,ok):
        nonlocal n
        assert ok,name;n+=1;print('PASS',name)
    raw={'nie_detail':{'other_gross_up_rate':.08,'categories':[{'name':'Expense','linked_components':[{'name':'Formula'}]}],'workforce':{'roles':[{'role':'Staff'}],'additive_components':[{'name':'Bonus'}]}},'fixed_assets':{'assets':[{'name':'Equipment'}]}}
    prepared={'categories':[200.],'_category_series':[[200.]],'linked_components':[{'category_index':0,'_gross_raw':raw['nie_detail']['categories'][0]['linked_components'][0]}],'gross_up_rate':.08}
    product={'name':'Product','_ox':[0,60],'_fcost':[0,70],'fee_streams':[{'name':'Cost','quantity_series_id':'cost','cost':{'kind':'per_account'}}]}
    roles=[{'raw':raw['nie_detail']['workforce']['roles'][0],'period_expenses':{1:80.}}]
    fa={'asset_rows':[{'name':'Equipment','type':'existing','remaining_life_periods':12,'depreciation_per_period':50.}]}
    def run(a=raw):return calculate(a,1,12,prepared,compensation=100,role_rows=roles,additive_values=[20],fdic=30,occ=40,depreciation=50,fixed_assets=fa,products=[product],linked_values=[10],fee_economics={'cost':{'fee_product_cost':[70]}},product_total=60)
    r=run();ck('default base excludes fee costs',r['eligible_base']==490 and math.isclose(r['gross_up'],490*.08/.92))
    ck('all expenses reconcile including excluded costs',sum(x['amount'] for x in r['rows'])==560)
    b=copy.deepcopy(raw);b['nie_detail']['gross_up_eligibility']={'compensation':False,'categories':False,'fdic':False,'occ':False,'depreciation':False,'product_opex':False,'fee_costs':True}
    r=run(b);ck('all expense groups toggle independently',r['eligible_base']==70)
    # Direct line overrides inherit the group; they do not alter the underlying expense.
    product['opex_gross_up_eligible']=False;product['fee_streams'][0]['cost']['gross_up_eligible']=True
    raw['nie_detail']['categories'][0]['gross_up_eligible']=False
    prepared['linked_components'][0]['_gross_raw']['gross_up_eligible']=True
    roles[0]['raw']['gross_up_eligible']=False
    raw['nie_detail']['workforce']['additive_components'][0]['gross_up_eligible']=False
    raw['fixed_assets']['assets'][0]['gross_up_eligible']=False
    r=run();ck('per-line overrides cover roles, bonus, categories, components, depreciation, product and fee cost',r['eligible_base']==150)
    ck('expense amount remains unchanged by eligibility',sum(x['amount'] for x in r['rows'])==560)
    b=copy.deepcopy(raw);b['nie_detail']['gross_up_eligibility']={'fdic':'no'}
    try:validate(b);raise AssertionError('bad boolean accepted')
    except ValueError:ck('reject nonboolean group policy',True)
    b=copy.deepcopy(raw);b['nie_detail']['gross_up_eligibility']={'typo':True}
    try:validate(b);raise AssertionError('unknown group accepted')
    except ValueError:ck('reject unknown expense group',True)
    cfg=json.load(open('foundry/fixtures/core_bank_test_base.json'));a=cfg['assumptions'];a['nie_detail']['other_gross_up_rate']=.08
    before=run_v2(cfg)
    a['nie_detail']['gross_up_eligibility']={'categories':False}
    ck('public policy validates',not validate_errors_v2(cfg));after=run_v2(cfg)
    exact=after['expense_gross_up']['periods'][0];excluded=sum(x['amount'] for x in exact['rows'] if x['group']=='categories')
    # Same-period economics before balance-sheet feedback: direct expense stays unchanged; overhead loses only the category gross-up.
    ck('public engine gross-up audit reconciles',math.isclose(exact['gross_up'],exact['eligible_base']*.08/.92))
    ck('category exclusion reduces first-period overhead by the gross-up only',math.isclose((before['financials']['is']['overhead'][0]-after['financials']['is']['overhead'][0])*1000,excluded*.08/.92,abs_tol=20))
    from .audit_workbook import calculation_audit_workbook
    wb=calculation_audit_workbook(cfg,after);ck('audit workbook exposes expense eligibility','Expense Gross-up' in wb.sheetnames)
    # Profile B retains the same policy contract.
    cfg=json.load(open('foundry/fixtures/parity/configs/pf_b_base.json'));a=cfg['assumptions'];a.setdefault('nie_detail',{'categories':[]});a['nie_detail']['gross_up_eligibility']={'product_opex':False};a['nie_detail']['other_gross_up_rate']=.08
    r=run_v2(cfg);ck('Profile B resolves optional eligibility audit',bool(r['expense_gross_up']['periods']))
    from .new_engagement import neutral_template
    template=json.load(open('foundry/fixtures/universal_template_bank.json'));neutral=neutral_template(template)
    ck('new engagements start at zero gross-up without mutating saved fixtures',neutral['assumptions']['nie_detail']['other_gross_up_rate']==0 and template['assumptions']['nie_detail']['other_gross_up_rate']==.08)
    print(n,'checks passed')
if __name__=='__main__':main()
