"""Product-owned formula costs, using the existing typed expense evaluator.

Resolve after product balances/revenues, before corporate expense. Definitions
remain with the owning stream; observing a source never posts that source again.
"""
import copy
import math
import uuid

KIND = 'linked_formula_opex'
COLLECTIONS = ('obs_exposures', 'lending_products', 'deposit_products')
SOURCES = {'catalog_quantity','reference_rate','deposit_interest','acquisition_share',
           'fee_stream_quantity','account_activity','customer_acquisition_auc',
           'fee_income','gain_on_sale','servicing_net','noninterest_income'}


def formulas(a):
    for collection in COLLECTIONS:
        for pi, p in enumerate(a.get(collection) or []):
            for si, s in enumerate(p.get('fee_streams') or []):
                if (s.get('cost') or {}).get('kind') == KIND:
                    yield collection, pi, si, s


def _check_sources(formula):
    for f in formula.get('factors') or []:
        if f.get('kind') == 'linked' and f.get('source') not in SOURCES:
            raise ValueError('Product formula cost source is not available before expense posting: '+str(f.get('source')))
    for term in formula.get('base_terms') or []:
        _check_sources(term)


def prepare(a, n, ppy, growth_context=None):
    from .opex_extensions import normalize_linked_component, resolve_linked_components
    from .income_modules import _validate_fee_stream_shape
    from collections import Counter
    ids=Counter(s.get('quantity_series_id') for key in COLLECTIONS for p in a.get(key) or [] for s in p.get('fee_streams') or [])
    component_ids={x.get('component_id') for cat in (a.get('nie_detail') or {}).get('categories') or [] for x in cat.get('linked_components') or [] if x.get('component_id')}
    rows=[]
    for collection, pi, si, s in formulas(a):
        _validate_fee_stream_shape(s)
        if not s.get('quantity_series_id'):
            raise ValueError('Product formula cost requires a stable stream ID')
        if ids[s['quantity_series_id']] != 1:
            raise ValueError('Product formula cost stream ID must be unique')
        c=normalize_linked_component((s['cost'].get('params') or {}).get('formula'))
        if c['driver'] != 'formula_driver':raise ValueError('Product cost requires a typed formula')
        if not c.get('component_id') or c['component_id'] in component_ids:
            raise ValueError('Product formula identity is missing or still used elsewhere; move the expense instead of copying it')
        component_ids.add(c['component_id'])
        _check_sources(c)
        owner={'series_id':s['quantity_series_id'], 'linked_components':[c]}
        compiled=resolve_linked_components(owner,n,ppy,context=growth_context,assumptions=a)[0]
        rows.append((collection,pi,si,compiled))
    return rows


def apply(rows, products, period, metrics, economics):
    from .opex_extensions import linked_component_period_result
    total=0.
    for collection, pi, si, formula in rows:
        p=products[collection][pi];s=p['fee_streams'][si];tm=s.get('timing') or {}
        active=int(tm.get('start_period') or 1)<=period and (tm.get('end_period') is None or period<=int(tm['end_period']))
        value=float(linked_component_period_result(formula,period-1,metrics)['expense']) if active else 0.
        if not math.isfinite(value):raise ValueError('Product formula cost must resolve to a finite amount')
        p['_fcost'][period]+=value;total+=value
        rec=economics.setdefault(s['quantity_series_id'], {'basis':'flat','cost_kind':KIND})
        vals=rec.setdefault('fee_product_cost',[])
        while len(vals)<period:vals.append(0.)
        vals[period-1]=value
    return total


def move_formula(cfg, collection, product_index, category_id, component_id):
    """Pure draft transfer; retains other category amounts and never writes a save."""
    if collection not in COLLECTIONS:raise ValueError('Select a product family')
    c=copy.deepcopy(cfg);a=c['assumptions']
    if type(product_index) is not int or product_index<0 or product_index>=len(a.get(collection) or []):
        raise ValueError('Selected product is missing')
    p=a[collection][product_index]
    hits=[x for x in (a.get('nie_detail') or {}).get('categories') or [] if x.get('series_id')==category_id]
    if len(hits)!=1:raise ValueError('Expense category is missing or ambiguous')
    cat=hits[0]
    matches=[(j,x) for j,x in enumerate(cat.get('linked_components') or []) if x.get('component_id')==component_id]
    if len(matches)!=1:raise ValueError('Expense formula is missing or ambiguous')
    j,formula=matches[0]
    if formula.get('driver')!='formula_driver':raise ValueError('Select a Formula component')
    if (cat.get('calculation') or {}).get('kind')=='cost_pool':raise ValueError('This category uses an exclusive cost pool')
    # Moving a category's expense would otherwise change observers silently.
    def referenced(node):
        if isinstance(node,dict):
            if node is cat:return False
            return any((k in {'series_id','ref','source_id'} and v==category_id) or referenced(v) for k,v in node.items())
        return isinstance(node,list) and any(referenced(v) for v in node)
    if referenced(a):raise ValueError('This expense category is referenced elsewhere. Moving its formula would change those consumers.')
    name=formula.get('name') or cat.get('name') or 'Product expense'
    if any(str(x.get('name') or '').strip().casefold()==str(name).strip().casefold()
           for x in p.get('fee_streams') or []):
        raise ValueError('A stream named "'+name+'" already exists in this product. Moving creates its own stream. Inspect the existing stream and remove it only if it is an unwanted blank formula, or rename it before moving. Nothing was moved.')
    policy=(a.get('nie_detail') or {}).get('gross_up_eligibility') or {}
    eligible=formula.get('gross_up_eligible',cat.get('gross_up_eligible',policy.get('categories',True)))
    sid='product-formula-'+uuid.uuid4().hex
    s={'name':name, 'basis':'flat',
       'quantity_series_id':sid,'driver':{'source':'constant','trajectory':'flat','params':{}},
       'rate':{'behavior':'flat','params':{'amount_per_period':0}},'timing':{'start_period':1},
       'cost':{'kind':KIND,'gross_up_eligible':eligible,'params':{'formula':copy.deepcopy(formula)}},
       'origin_expense':{'category_id':category_id,'category_name':cat.get('name'),'component_id':component_id}}
    p.setdefault('fee_streams',[]).append(s);cat['linked_components'].pop(j)
    return c


def verified_move(cfg, collection, product_index, category_id, component_id):
    from .engine_q_a import run_pf_a
    from .validate_q import validate_errors_v2
    source=copy.deepcopy(cfg)
    candidate=move_formula(source,collection,product_index,category_id,component_id)
    for c in (source,candidate):
        errs=validate_errors_v2(c)
        if errs:raise ValueError('; '.join(x['message'] for x in errs))
    old=run_pf_a(copy.deepcopy(source));new=run_pf_a(copy.deepcopy(candidate))
    def check(x,y,path='financials'):
        if isinstance(x,dict):
            if not isinstance(y,dict) or set(x)!=set(y):raise ValueError('Transfer changes financial statement structure: '+path)
            for k in x:
                if path=='is' and k in {'feeOpex','overhead','otherOpex'}:continue
                check(x[k],y[k],path+'.'+k)
        elif isinstance(x,list):
            if len(x)!=len(y):raise ValueError('Transfer changes financial statement horizon')
            for i,(v,w) in enumerate(zip(x,y)):check(v,w,path+'.'+str(i))
        elif isinstance(x,(int,float)) and not isinstance(x,bool):
            if not isinstance(y,(int,float)) or not math.isclose(x,y,rel_tol=1e-10,abs_tol=1e-6):raise ValueError('Transfer changes '+path+'; no change was applied')
        elif x!=y:raise ValueError('Transfer changes '+path)
    for section in ('is','bs'):
        check(old[section],new[section],section)
    for i in range(len(old['is']['pretax'])):
        check(sum(old['is'][k][i] for k in ('prodOpex','feeOpex','overhead')),
              sum(new['is'][k][i] for k in ('prodOpex','feeOpex','overhead')),'total expense')
    return {'config':candidate,'message':'Formula moved to the product stream. Financial statements reconcile; save when ready.'}
