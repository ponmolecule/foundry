"""General external tax rules: live allocation, settlements, DTA/DTL, audit, fail closed."""
import copy,json
from pathlib import Path
from .external_tax import ExternalTaxLedger,validate,parse
from .engine_q_a import run_pf_a
from .run_q import run_v2
from .validate_q import validate_errors_v2
from .audit_workbook import calculation_audit_workbook

def inp(sid,value,unit='money',period='model_period'):
    return {'id':sid,'name':sid,'unit':unit,'source':'entered','amount_spec':{'source':'entered','trajectory':'flat','value':value,'period':period}}
def rule(sid,expr,unit='money'):return {'id':sid,'name':sid,'unit':unit,'expression':expr}
def cfg():
    c=json.loads(Path('foundry/fixtures/core_bank_test_base.json').read_text());a=c['assumptions'];a['periods_per_year']=12;a['n_periods']=12;a.pop('capital_raises',None)
    a['tax_mode']='external';a['external_tax']={'inputs':[inp('provision',100)],'rules':[],'outputs':{'current':'provision'},'payment_mode':'same_period','deferred_mode':'none'}
    return c

def main():
    c=cfg();a=c['assumptions'];m=a['external_tax']
    assert not validate_errors_v2(c),validate_errors_v2(c)
    x=ExternalTaxLedger(c,a,12);r=x.evaluate(1,1000);assert r['tax']==100 and r['payments']==100 and r['settlementNet']==0
    assert x.evaluate(1,1000)==r and not x.rows,'solver evaluations must be pure'
    x.commit(r)
    try:x.commit(r)
    except ValueError:pass
    else:raise AssertionError('double commit')
    m['payment_mode']='scheduled';m['inputs'].append(inp('paid',40));m['outputs']['payments']='paid';m['opening_payable']=20
    x=ExternalTaxLedger(c,a,12);r=x.evaluate(1,1000);assert r['taxPayable']==80;x.commit(r);assert x.evaluate(2,1000)['taxPayable']==140
    m['inputs'][1]['amount_spec']['value']=200
    x=ExternalTaxLedger(c,a,12);assert x.evaluate(1,1000)['taxReceivable']==80
    m.update(deferred_mode='balances',opening_deferred_asset=25,opening_deferred_liability=10)
    m['inputs'] += [inp('asset',50),inp('liability',30)];m['outputs'].update(deferred_asset='asset',deferred_liability='liability')
    x=ExternalTaxLedger(c,a,12);r=x.evaluate(1,1000);assert r['taxDeferred']==-5 and r['tax']==95
    # Generic group allocation; no source-engagement labels or constants.
    c=cfg();a=c['assumptions'];m=a['external_tax'];m['inputs']=[inp('other_profit',2000),inp('tax_rate',.25,'scalar'),inp('opening_losses',10000),inp('limit',.8,'scalar')]
    m['rules']=[rule('group_income','bank_pretax + other_profit'),rule('losses','max(0, prior(losses, opening_losses) - used)'),rule('used','min(prior(losses, opening_losses), max(0, group_income) * limit)'),rule('group_tax','max(0, group_income - used) * tax_rate'),rule('share','safe_div(max(0, bank_pretax), max(0, bank_pretax) + max(0, other_profit), 0)','scalar'),rule('allocated','group_tax * share')]
    m['outputs']={'current':'allocated'}
    x=ExternalTaxLedger(c,a,12);r=x.evaluate(1,1000);assert abs(r['tax']-50)<1e-9;assert r['operands']['losses']==7600;x.commit(r)
    assert abs(x.evaluate(2,2000)['tax']-100)<1e-9
    # Zero denominator has explicit fallback; division without fallback fails.
    m['inputs'][0]['amount_spec']['value']=0
    x=ExternalTaxLedger(c,a,12);assert x.evaluate(1,0)['tax']==0
    bad=copy.deepcopy(a);bad['external_tax']['rules']=[rule('a','b'),rule('b','a')];bad['external_tax']['outputs']={'current':'a'}
    try:validate(bad,c)
    except ValueError as e:assert 'Circular' in str(e)
    else:raise AssertionError('cycle')
    for expr in ['__import__("os")','bank_net_income','group_tax / 0','bank_pretax * bank_pretax']:
        b=cfg();b['assumptions']['external_tax']['rules']=[rule('bad',expr)];b['assumptions']['external_tax']['outputs']={'current':'bad'}
        try:ExternalTaxLedger(b,b['assumptions'],12).evaluate(1,100)
        except (ValueError,KeyError):pass
        else:raise AssertionError(expr)
    # Monthly monetary flows SUM to quarters; stock payment ledger is not summed.
    c=cfg();a=c['assumptions'];a['periods_per_year']=4;a['n_periods']=12;m=a['external_tax'];m['inputs'][0]['amount_spec'].update(trajectory='explicit',cadence='month',values=list(range(1,37)),period='month')
    x=ExternalTaxLedger(c,a,4);assert x.evaluate(1,100)['tax']==6
    # Engine balance sheet identities, settlement modes, exact audit and public units.
    c=cfg();a=c['assumptions'];m=a['external_tax'];m['payment_mode']='scheduled';m['inputs'].append(inp('paid',0));m['outputs']['payments']='paid';m['opening_payable']=-50
    r=run_pf_a(c)
    for i in range(1,13):
        assert abs(r['bs']['taxPayable'][i]-max(0,-50+100*i))<1e-6
        assert abs(r['is']['tax'][i-1]-100)<1e-6
        bs=r['bs'];liabs=bs['deposits'][i]+bs['borrow'][i]+bs['borrowSched'][i]+bs['otherLiab'][i]+bs['accruedOpex'][i]
        assert abs(bs['totalAssets'][i]-liabs-bs['equity'][i])<.001
    pub=run_v2(c);assert abs(pub['tax_interim']['rows'][0]['taxCurrent']-.1)<1e-9
    wb=calculation_audit_workbook(c,pub)
    assert any('Cash tax payment' in str(row) for row in wb['Income Taxes'].values)
    assert any('taxPayable' in str(row) for row in wb['All Series'].values)
    # A live monetary fee quantity is consumed at runtime, without revenue/cost reposting.
    linked=json.loads(Path('foundry/fixtures/universal_template_bank.json').read_text())
    la=linked['assumptions'];la['tax_mode']='external';la['external_tax']={'inputs':[{'id':'flow','source':'linked_quantity','unit':'money','source_series_id':'fee-qty-api-universal','multiplier':.05}],'rules':[],'outputs':{'current':'flow'},'payment_mode':'same_period'}
    lr=run_pf_a(linked)
    quantities=lr['fee_stream_quantities']['fee-qty-api-universal']
    assert all(abs(t-q*.05)<1e-6 for t,q in zip(lr['is']['tax'],quantities))
    # Balance inputs sample the end; flow inputs above sum months.
    stock=cfg();sa=stock['assumptions'];sa['periods_per_year']=4;sm=sa['external_tax'];sm['deferred_mode']='balances'
    sm['inputs'].append({'id':'deferred_stock','source':'entered','unit':'money','measure':'level','amount_spec':{'source':'entered','trajectory':'explicit','cadence':'month','values':list(range(1,37))}})
    sm['outputs']['deferred_asset']='deferred_stock'
    assert ExternalTaxLedger(stock,sa,4).evaluate(1,100)['dtaNet']==3
    # Endogenous tax affects treasury income through the existing fixed-point solver.
    live=cfg();lm=live['assumptions']['external_tax'];lm['rules']=[rule('tax_rule','max(0, bank_pretax) * 0.2')];lm['outputs']['current']='tax_rule'
    lrun=run_pf_a(live)
    assert all(abs(t-max(0,p)*.2)<.001 for t,p in zip(lrun['is']['tax'],lrun['is']['pretax']))
    # Deferred recognition changes NI and tax assets/liabilities consistently, not cash tax.
    dc=cfg();da=dc['assumptions'];da['cash_yield']=0;da['securities_yield']=0;da['borrow_rate_ann']=0
    dm=da['external_tax'];dm['inputs'][0]['amount_spec']['value']=0
    d0=run_pf_a(dc)
    dm['deferred_mode']='balances';dm['inputs'] += [dict(inp('dta_level',50),measure='level'),dict(inp('dtl_level',20),measure='level')]
    dm['outputs'].update(deferred_asset='dta_level',deferred_liability='dtl_level')
    dr=run_pf_a(dc)
    assert dr['is']['taxDeferred'][0]==-30
    fund=lambda r:r['bs']['cash'][1]+r['bs']['sec'][1]-r['bs']['borrow'][1]
    assert abs(fund(dr)-fund(d0))<.001, 'noncash deferred provision must not cause a cash payment'
    bs=dr['bs'];assert abs(bs['totalAssets'][1]-bs['deposits'][1]-bs['borrow'][1]-bs['borrowSched'][1]-bs['otherLiab'][1]-bs['accruedOpex'][1]-bs['equity'][1])<.001
    calculated=copy.deepcopy(c);calculated['assumptions']['tax_mode']='calculated'
    calculated['assumptions'].pop('external_tax');legacy=copy.deepcopy(calculated);legacy['assumptions'].pop('tax_mode')
    assert run_pf_a(calculated)==run_pf_a(legacy)
    print('PASS external tax: live allocation, recurrence, units, prior state, monthly flows, settlements, deferred balances, safety, solver purity, audit and legacy identity')
if __name__=='__main__':main()
