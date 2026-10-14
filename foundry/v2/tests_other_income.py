"""Entity income posting, units, cadence, rejected inputs and no-op identity."""
import copy, json
from pathlib import Path
from .other_income import prepare, validate
from .engine_q_a import run_pf_a
from .run_q import run_v2
from .audit_workbook import calculation_audit_workbook


def line(values, cadence='month', period='month'):
    return {'id':'income-1','name':'User income','classification':'dividend','source':'entered',
            'amount_spec':{'source':'entered','trajectory':'explicit','cadence':cadence,
                           'values':values,'extend':'zero','resolution':'step','period':period}}

def main():
    c=json.loads(Path('foundry/fixtures/core_bank_test_base.json').read_text());a=c['assumptions']
    # Independent amount and schedule cadence: annual amounts held per year vs monthly amounts.
    for ppy,n in [(12,12),(4,4)]:
        model={'other_income_model':{'lines':[line([39200,41500,49100]+[0]*9)]}}
        rows=prepare(model,{},n,ppy)
        assert sum(rows[0]['amount'])==129800
        assert rows[0]['amount'][0]==(39200 if ppy==12 else 129800)
        annual={'other_income_model':{'lines':[line([120000], 'year', 'year')]}}
        assert prepare(annual,{},n,ppy)[0]['amount']==[120000/ppy]*n
    quarterly={'other_income_model':{'lines':[line([100,200,300,400], 'model_period', 'model_period')]}}
    assert prepare(quarterly,{},4,4)[0]['amount']==[100,200,300,400]
    linked_a=json.loads(Path('foundry/fixtures/universal_template_bank.json').read_text())['assumptions']
    linked_a['other_income_model']={'lines':[{'id':'link-1','name':'Linked income','source':'linked_quantity','source_series_id':'fee-qty-api-universal','multiplier':.05}]}
    assert prepare(linked_a,{'fee-qty-api-universal':[1000,2000]},2,12)[0]['amount']==[50,100]
    try:prepare(linked_a,{},2,12)
    except ValueError:pass
    else:raise AssertionError('Missing linked quantity accepted')
    linked_a['other_income_model']['lines'][0]['source_series_id']='fee-qty-enabled-accounts-universal'
    try:validate(linked_a)
    except ValueError:pass
    else:raise AssertionError('Count accepted as monetary income')
    old=run_v2(copy.deepcopy(c));empty=copy.deepcopy(c);empty['assumptions']['other_income_model']={'lines':[]}
    assert run_pf_a(empty)==run_pf_a(c)
    # Zero cash/securities yields isolate one-time P&L posting and downstream tax/equity.
    a['cash_yield']=0;a['securities_yield']=0
    base=run_pf_a(copy.deepcopy(c));a['other_income_model']={'lines':[line([120000]+[0]*35)]}
    new=run_pf_a(copy.deepcopy(c))
    assert new['is']['otherIncome'][0]==120000
    assert abs(new['is']['pretax'][0]-base['is']['pretax'][0]-120000)<1e-6
    assert new['is']['fees']==base['is']['fees'] and new['is']['nii']==base['is']['nii']
    assert abs(new['is']['ni'][0]-base['is']['ni'][0]-(120000-new['is']['tax'][0]+base['is']['tax'][0]))<1e-6
    public=run_v2(c);res=public.get('results',public)
    assert res['financials']['is']['otherIncome'][0]==120
    assert res['other_income_detail']['lines'][0]['amount'][0]==120
    wb=calculation_audit_workbook(c,res)
    assert 'Other Income' in wb.sheetnames
    assert any(row[1]=='User income' and 120 in row for row in wb['Other Income'].iter_rows(values_only=True))
    assert any(row[2]=='otherIncome' for row in wb['Income Statement'].iter_rows(values_only=True))
    # Signed net income is explicit, never clipped.
    neg=prepare({'other_income_model':{'lines':[line([-100])]}},{},1,12)
    assert neg[0]['amount']==[-100]
    for bad in [line([float('nan')]),line([1],period='week')]:
        try:prepare({'other_income_model':{'lines':[bad]}},{},1,12)
        except (ValueError,TypeError):pass
        else:raise AssertionError('Invalid income accepted')
    try:validate({'other_income_model':{'lines':[line([1]),line([2])]}})
    except ValueError:pass
    else:raise AssertionError('Duplicate IDs accepted')
    print('PASS Other income cadence, posting, taxes, exact/public/audit units and rejection guards')

if __name__=='__main__':main()
