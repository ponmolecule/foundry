"""Generic block economics, reuse, edit isolation, output selection and ledger/audit."""
import ast,copy,json
from pathlib import Path
from .tests_external_tax import cfg,inp,rule
from .tax_blocks import plan
from .external_tax import ExternalTaxLedger,validate
from .run_q import run_v2
from .engine_q_a import run_pf_a
from .audit_workbook import calculation_audit_workbook


def setup():
    c=cfg();a=c['assumptions'];a['tax_rate']=.25;a['tax_policy']={'nol_utilization_limit_pct':.8}
    m=a['external_tax'];m['inputs']=[inp('income',1000),dict(inp('initial',1600),measure='level'),inp('threshold',20),inp('retained',.25,'scalar'),inp('outside',2000),inp('negative_entity',-100)]
    m['outputs']['current']='income';m['rules']=[rule('positive_existing','max(0, income)'),rule('capacity_existing','configured_nol_limit * positive_existing'),rule('placeholder','0')]
    return c


def loss(c):return plan(c,{'kind':'loss_carryforward','name':'Loss pool','bindings':{'taxable_income':'income','opening_losses':'initial','utilization_limit':'configured_nol_limit','tax_rate':'configured_tax_rate'}})
def rejects(f):
    try:f()
    except (ValueError,TypeError):return
    raise AssertionError('expected rejection')


def main():
    c=setup();before=copy.deepcopy(c);p=loss(c);assert c==before,'preview must be pure'
    assert {r['id'] for r in p['summary']['reused']}=={'positive_existing','capacity_existing'}
    assert p['cfg']['assumptions']['external_tax']['inputs']==c['assumptions']['external_tax']['inputs']
    assert p['summary']['current_before']==p['summary']['current_after']=='income'
    assert not p['summary']['removed_rules']
    assert all(r in p['cfg']['assumptions']['external_tax']['rules'] for r in c['assumptions']['external_tax']['rules'])
    b=p['block'];c=p['cfg'];taxid=b['outputs']['tax'];c['assumptions']['external_tax']['outputs']['current']=taxid
    x=ExternalTaxLedger(c,c['assumptions'],12)
    expected=[(800,0,800,50),(800,0,0,50),(0,0,0,250)]
    for i,(used,new,end,tax) in enumerate(expected,1):
        r=x.evaluate(i,0);assert r['tax']==tax
        assert r['operands'][b['outputs']['used']]==used and r['operands'][b['outputs']['new']]==new and r['operands'][b['outputs']['closing']]==end
        assert x.evaluate(i,0)==r,'repeated solver evaluation must not advance losses'
        x.commit(r)
    # Negative period grows the pool; no silent clipping or fictitious gross tax.
    a=c['assumptions'];a['external_tax']['inputs'][0]['amount_spec'].update(trajectory='explicit',cadence='month',values=[-200,1000]+[0]*10,period='month')
    x=ExternalTaxLedger(c,a,12);r=x.evaluate(1,0);assert r['tax']==0 and r['operands'][b['outputs']['closing']]==1800;x.commit(r)
    assert x.evaluate(2,0)['tax']==50
    # Credit boundary checks independently reconcile retain-full threshold / retained excess.
    base=setup();base['assumptions']['external_tax']['inputs'][0]['amount_spec'].update(trajectory='explicit',cadence='month',values=[0,10,20,100]+[0]*8,period='month')
    q=plan(base,{'kind':'credit_limit','threshold_treatment':'fully_retained','name':'Credit block','set_current':True,'bindings':{'tax_before_credit':'income','threshold':'threshold','retained_share':'retained'}})
    x=ExternalTaxLedger(q['cfg'],q['cfg']['assumptions'],12)
    for i,want in enumerate([0,10,20,40],1):r=x.evaluate(i,0);assert r['tax']==want;x.commit(r)
    # Full credit up to the threshold is a distinct, explicit policy.
    credited=plan(base,{'kind':'credit_limit','name':'Full threshold credit','threshold_treatment':'fully_credited','set_current':True,'bindings':{'tax_before_credit':'income','threshold':'threshold','retained_share':'retained'}})
    xx=ExternalTaxLedger(credited['cfg'],credited['cfg']['assumptions'],12)
    for i,want in enumerate([0,0,0,20],1):rr=xx.evaluate(i,0);assert rr['tax']==want;xx.commit(rr)
    rejects(lambda:plan(base,{'kind':'credit_limit','name':'No implicit treatment','bindings':{'tax_before_credit':'income','threshold':'threshold','retained_share':'retained'}}))
    # Allocation includes positive entities only, no share guessed from product names.
    q=plan(q['cfg'],{'kind':'allocation','name':'Entity share','set_current':True,'bindings':{'amount':q['block']['outputs']['tax'],'participants':['bank_pretax','outside','negative_entity'],'target':'bank_pretax'}})
    x=ExternalTaxLedger(q['cfg'],q['cfg']['assumptions'],12)
    for i in range(1,5):r=x.evaluate(i,1000);x.commit(r)
    assert abs(r['tax']-40/3)<1e-10
    # Signed allocation is explicit and may allocate a negative share; zero base is zero.
    d={'kind':'allocation','name':'Signed share','method':'signed_income','set_current':True,'bindings':{'amount':'income','participants':['bank_pretax','outside'],'target':'bank_pretax'}}
    signed=plan(setup(),d)['cfg'];x=ExternalTaxLedger(signed,signed['assumptions'],12);assert x.evaluate(1,-1000)['tax']==-1000
    assert x.evaluate(1,-2000)['tax']==0
    # Editing preserves IDs and every input; no deletion of unrelated standalone rules.
    edited=copy.deepcopy(b);edited['name']='Renamed loss pool';edited['set_current']=True
    fresh=loss(setup())['cfg'];e=plan(fresh,edited)
    assert e['block']['id']==b['id'] and len(e['cfg']['assumptions']['external_tax']['blocks'])==1
    assert e['cfg']['assumptions']['external_tax']['inputs']==fresh['assumptions']['external_tax']['inputs']
    assert next(r for r in e['cfg']['assumptions']['external_tax']['rules'] if r['id']=='placeholder')['expression']=='0'
    # Invalid selections and unsupported units fail without mutating the engagement.
    for patch in [{'taxable_income':'missing'},{'opening_losses':'income'},{'utilization_limit':'income'}]:
        d={'kind':'loss_carryforward','name':'Invalid','bindings':dict(b['bindings'],**patch)};rejects(lambda:plan(setup(),d))
    bad=setup();bad['assumptions']['external_tax']['inputs'][1]['amount_spec']['value']=-1
    rejects(lambda:loss(bad))
    bad=setup();bad['assumptions']['external_tax']['inputs'].append(inp('bad_share',1.2,'scalar'))
    rejects(lambda:plan(bad,{'kind':'credit_limit','threshold_treatment':'fully_retained','name':'Invalid share','set_current':True,'bindings':{'tax_before_credit':'income','threshold':'threshold','retained_share':'bad_share'}}))
    bad=setup();bad['assumptions']['external_tax']['rules'].append(rule('dynamic_share','bank_pretax / income','scalar'))
    bb=plan(bad,{'kind':'credit_limit','threshold_treatment':'fully_retained','name':'Dynamic share','set_current':True,'bindings':{'tax_before_credit':'income','threshold':'threshold','retained_share':'dynamic_share'}})['cfg']
    rejects(lambda:ExternalTaxLedger(bb,bb['assumptions'],12).evaluate(1,1200))
    # Explicit cadence: same period method at monthly or quarterly cadence, no hidden monthly disaggregation.
    cc=setup();cc['assumptions']['periods_per_year']=4;cc=loss(cc)['cfg'];xx=ExternalTaxLedger(cc,cc['assumptions'],4);assert xx.evaluate(1,0)['operands'][next(iter(cc['assumptions']['external_tax']['blocks']))['outputs']['tax']]==50
    # Real engine/public audit: sole posting and BS identity.
    cc=loss(setup())
    cc=cc['cfg'];cc['assumptions']['external_tax']['outputs']['current']=cc['assumptions']['external_tax']['blocks'][0]['outputs']['tax']
    raw=run_pf_a(cc);pub=run_v2(cc);assert raw['is']['tax'][:3]==[50,50,250]
    assert abs(pub['tax_interim']['rows'][0]['taxCurrent']-.05)<1e-10
    plain=copy.deepcopy(cc);plain['assumptions']['external_tax'].pop('blocks');assert run_pf_a(plain)==raw,'complete engine results equal the materialized rules without block metadata'
    assert run_v2(plain)['config_hash']!=pub['config_hash'],'explicit authoring metadata changes the configuration fingerprint'
    wb=calculation_audit_workbook(cc,pub);assert any('Loss pool' in str(row) for row in wb['Income Taxes'].values)
    for i in range(1,13):
        bs=raw['bs'];assert abs(bs['totalAssets'][i]-bs['deposits'][i]-bs['borrow'][i]-bs['borrowSched'][i]-bs['otherLiab'][i]-bs['accruedOpex'][i]-bs['equity'][i])<.001
    # Preview endpoint is authenticated and delegates to pure planner.
    tree=ast.parse(Path('app.py').read_text());fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='v31_tax_blocks_preview')
    assert ast.literal_eval(fn.decorator_list[0].args[0])=='/api/v31/tax-blocks/preview'
    assert 'Depends(gate)' in ast.unparse(fn)
    print('PASS tax blocks: hand economics, loss exhaustion/new losses, syntax-based reuse, isolated preview, explicit posting, credit boundaries, allocation, audit/BS, cadence and authenticated route')
if __name__=='__main__':main()
