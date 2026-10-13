"""General balance formula and independently specified income invariants."""
import copy,io
from openpyxl import load_workbook
from .tests_balance_components import configured,component,flat
from .balance_components import BalanceComponents
from .growth import GrowthContext
from .engine_q_a import run_pf_a
from .run_q import run_v2
from .audit_workbook import calculation_audit_workbook

def targets(values,**kw):
    return dict(source='entered',trajectory='explicit',cadence='year',values=values,unit='money',resolution='step',extend='hold',year_end_targets=True,target_path='ramp',**kw)

def approx(a,b):assert abs(a-b)<1e-6,(a,b)

def runtime(comps,n=36,ppy=12,context=None):return BalanceComponents(configured(comps)['assumptions'],{},{},n,ppy,context)

def main():
    # Formula is generalized: selected upstream stock × multiplier minus another stock.
    c=component('asset','earning_asset',0,rate=.03425,balance_floor='zero')
    c['terms']=[{'source_spec':{'source':'bank_series','series_id':'deposits','timing':'current_period'},'factors':[flat(1.04)]},
                {'source_spec':{'source':'bank_series','series_id':'gross_loans','timing':'current_period'},'sign':-1}]
    m=runtime([c]);b={('current_period','deposits'):20797100,('current_period','gross_loans'):0}
    v=m.stocks(2,b);approx(v['asset'],21628984);r,_=m.period(2,b,v,0,0,0);approx(r[0]['income'],21628984*.03425/12)
    b[('current_period','gross_loans')]=100000000;assert m.stocks(2,b)['asset']==0
    strict=copy.deepcopy(c);strict.pop('balance_floor');
    try:runtime([strict]).stocks(0,b)
    except ValueError:pass
    else:raise AssertionError('Negative stock silently accepted')
    # Annual closing targets ramp from an explicit previous target, with no forward-looking smooth interpretation.
    stock=component('capital-stock','earning_asset',0,income_method='entered_amount',income_amount_spec={**flat(28400,'money'),'period':'year'})
    stock['terms']=[{'source_spec':targets([900000,900000,1045000]),'factors':[]}]
    m=runtime([stock]);approx(m.stocks(0,{})['capital-stock'],75000);approx(m.stocks(2,{})['capital-stock'],225000)
    approx(m.stocks(11,{})['capital-stock'],900000);approx(m.stocks(12,{})['capital-stock'],900000);approx(m.stocks(35,{})['capital-stock'],1045000)
    r,_=m.period(0,{},m.stocks(0,{}),0,0,0);approx(r[0]['income'],28400/12)
    # Different use case: declining targets, non-zero opening, full-target path and calendar anchors.
    other=component('inventory','earning_asset',0);other['terms']=[{'source_spec':targets([600,300],target_opening=1200),'factors':[]}]
    x=runtime([other]);approx(x.stocks(0,{})['inventory'],1150);approx(x.stocks(23,{})['inventory'],300)
    other['terms'][0]['source_spec']['target_path']='full';assert runtime([other]).stocks(0,{})['inventory']==600
    other['terms'][0]['source_spec'].update(target_path='ramp',target_anchor='calendar_year')
    x=runtime([other],context=GrowthContext(2028,7));approx(x.stocks(0,{})['inventory'],850);approx(x.stocks(5,{})['inventory'],600);approx(x.stocks(6,{})['inventory'],575)
    # Independent balance basis generates income, never another booked balance.
    reserve=component('restricted-asset','earning_asset',0,rate=.03425,income_method='separate_balance_yield',income_balance_spec={**flat(5220000,'money')})
    reserve['terms']=[{'source_spec':targets([5220000,11745000,21141000]),'factors':[]}]
    m=runtime([reserve]);r,_=m.period(0,{},m.stocks(0,{}),0,0,0);approx(r[0]['ending'],435000);approx(r[0]['income'],5220000*.03425/12)
    # Equivalent quarter-end levels, and constant annual income summed exactly over each year.
    q=runtime([stock,reserve],n=12,ppy=4)
    monthly=runtime([stock,reserve]);
    for i in range(12):
        for sid in ['capital-stock','restricted-asset']:approx(q.stocks(i,{})[sid],monthly.stocks(i*3+2,{})[sid])
    qr,_=q.period(0,{},q.stocks(0,{}),0,0,0);approx(qr[0]['income'],28400/4);approx(qr[1]['income'],5220000*.03425/4)
    # All periodic amount units are explicit, including a per-month amount in a quarterly model.
    for period,value in [('year',120),('quarter',30),('month',10),('model_period',30)]:
        t=copy.deepcopy(stock);t['income_amount_spec']={**flat(value,'money'),'period':period};x=runtime([t],n=4,ppy=4);rows,_=x.period(0,{},x.stocks(0,{}),0,0,0);approx(rows[0]['income'],30)
    # Full engine: custom components change assets once; exact and public audit units agree.
    cfg=configured([stock,reserve]);cfg['assumptions']['capital_initial']=30000000
    raw=run_pf_a(copy.deepcopy(cfg));public=run_v2(copy.deepcopy(cfg));rows=raw['balance_components']['components'];assert rows[0]['income_method']=='entered_amount'
    approx(raw['bs']['earningAssets'][1],510000);approx(public['balance_components']['components'][1]['income_basis'][0],5220)
    expected=28400/12+5220000*.03425/12;approx(raw['is']['cashInt'][0],expected)
    zero=copy.deepcopy(cfg)
    for z in zero['assumptions']['balance_components_model']['components']:
        z['income_method']='balance_yield';z['yield_spec']=flat(0,'rate')
    zr=run_pf_a(zero);approx(raw['bs']['earningAssets'][1],zr['bs']['earningAssets'][1])
    # Product-specific stable catalog bindings use the completed lending/deposit stocks.
    a=cfg['assumptions'];a['lending_products'][0]['source_catalog_id']='stable-loan';sid='lending.stable-loan.balance'
    linked=component('offset','earning_asset',0);linked['terms']=[{'source_spec':{'source':'catalog_balance','series_id':sid,'measure':'period_end'}}]
    a['balance_components_model']['components']=[linked];rr=run_pf_a(cfg);assert len(rr['balance_components']['components'][0]['ending'])==36
    loan=next(p for p in rr['products'] if p['family']=='lending')
    for actual,expected in zip(rr['balance_components']['components'][0]['ending'],loan['bal'][1:]):approx(actual,expected)
    buffer=io.BytesIO();calculation_audit_workbook(configured([stock,reserve]),run_v2(configured([stock,reserve]))).save(buffer);buffer.seek(0);wb=load_workbook(buffer,data_only=True)
    assert any('restricted-asset.income_basis' in row for row in wb['Balance Components'].values)
    # Unsupported monetary types, circular financial inputs, invalid signs and missing targets fail closed.
    bad=[]
    t=copy.deepcopy(stock);t['income_amount_spec'].pop('period');bad.append(t)
    t=copy.deepcopy(stock);t['terms'][0]['sign']=0;bad.append(t)
    t=copy.deepcopy(stock);t['terms'][0]['source_spec']['values']=[];bad.append(t)
    t=copy.deepcopy(stock);t['terms'][0]['source_spec']['unit']='rate';bad.append(t)
    t=component('cash','cash_allocation',0,income_method='entered_amount',income_amount_spec={**flat(120,'money'),'period':'year'});bad.append(t)
    t=copy.deepcopy(c);t['terms'][0]['source_spec']['series_id']='equity';bad.append(t)
    t=copy.deepcopy(linked);t['terms'][0]['source_spec']['series_id']='missing';bad.append(t)
    for t in bad:
        try:runtime([t])
        except ValueError:pass
        else:raise AssertionError(('Unsupported case passed',t))
    print('PASS generalized signed/floored formulas, annual closing targets, independent income, calendar/quarter timing, exact posting/audit units, stable product links and 7 rejected inputs')

if __name__=='__main__':main()
