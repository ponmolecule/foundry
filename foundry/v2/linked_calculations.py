"""Read-only expense expressions over typed upstream observations.

No eval, arbitrary row references, expense feedback, or product-specific equations.
Arithmetic is explicitly grouped. Zero division and negative outputs are authored policies.
"""
from copy import deepcopy
from math import isfinite
from .series import resolve_entered_series

OPS = {'add', 'subtract', 'multiply', 'divide', 'if_positive'}
SOURCES = {'entered', 'balance', 'reference_rate', 'deposit_interest', 'activity'}

def normalize(raw, depth=0):
    if depth > 12 or not isinstance(raw, dict):
        raise ValueError('Linked calculation requires an expression (maximum depth 12)')
    s = deepcopy(raw); op = s.get('op', 'entered')
    if op in OPS:
        args = s.get('args') or []
        if len(args) != (3 if op == 'if_positive' else 2):
            raise ValueError('Calculation '+op+' has an invalid operand count')
        s['args'] = [normalize(x, depth+1) for x in args]
        if op == 'divide' and s.get('zero_policy','error') not in {'error','zero'}:
            raise ValueError('Choose zero division policy: error or zero')
    elif op not in SOURCES:
        raise ValueError('Unsupported calculation operand: '+str(op))
    return s

def source_options(a):
    from .source_catalog import balance_catalog
    from .account_activity import catalog
    rows = [dict(op='balance',series_id=x['series_id'],label=x['label'],unit='money',measures=x['measures']) for x in balance_catalog(a)]
    rows += [dict(op='reference_rate',series_id=k,label=l+' reference rate',unit='scalar') for k,l in [('effr','EFFR'),('sofr','SOFR'),('prime','Prime')]]
    for p in a.get('deposit_products') or []:
        sid = p.get('source_catalog_id')
        if sid: rows.append(dict(op='deposit_interest',series_id=sid,label='Deposit › '+str(p.get('name') or 'Deposit')+' › Interest expense',unit='money'))
    rows += [dict(op='activity',series_id=x['series_id'],label=x['label'],unit='count') for x in catalog(a) if x['temporal']=='flow' and 'feed' in x]
    return rows

def compile_expression(raw, a, n, ppy, context=None, category=None):
    from .source_catalog import require_balance, balance_link_creates_cycle
    from .account_activity import expense_cycle
    category = category or {}
    node = normalize(raw)
    options = {(x['op'], x['series_id']):x for x in source_options(a)}
    budget=[0]
    def compile_node(s):
        budget[0]+=1
        if budget[0]>128: raise ValueError('Calculation exceeds 128 operands')
        op=s.get('op','entered')
        if op in OPS:
            args=[compile_node(x) for x in s['args']];units=[x['resolved_unit'] for x in args]
            if op in {'add','subtract'}:
                if units[0]!=units[1]:raise ValueError('Addition/subtraction requires matching units')
                unit=units[0]
            elif op=='multiply':
                if 'scalar' not in units:raise ValueError('Multiply a monetary/count amount by a dimensionless factor')
                unit=units[1] if units[0]=='scalar' else units[0]
            elif op=='divide':
                if units[1]!='scalar' and units[0]!=units[1]:raise ValueError('Division requires matching units or a dimensionless denominator')
                unit='scalar' if units[0]==units[1] else units[0]
            else:
                if units[1]!=units[2]:raise ValueError('Conditional branches must use matching units')
                unit=units[1]
            return {**s,'args':args,'resolved_unit':unit}
        if op=='entered':
            unit=s.get('unit','scalar')
            if unit not in {'money','count','scalar'}:raise ValueError('Invalid entered calculation unit')
            spec=s.get('spec') or {'source':'entered','trajectory':'flat','value':0}
            if spec.get('source','entered')!='entered':raise ValueError('Calculation assumption must be entered')
            vals=resolve_entered_series(spec,n,ppy,context=context)
            if s.get('per','none') not in {'none','month','quarter','year'}:raise ValueError('Invalid calculation natural period')
            per=s.get('per','none');scale={'none':ppy,'month':12,'quarter':4,'year':1}[per]/ppy
            vals=[float(x)*scale for x in vals]
            if any(not isfinite(x) for x in vals):raise ValueError('Calculation values must be finite')
            return {**s,'values':vals,'resolved_unit':unit}
        sid=str(s.get('series_id') or '')
        meta=options.get((op,sid))
        if not meta:raise ValueError('Calculation source missing or unavailable: '+sid)
        if op=='balance':
            measure=s.get('measure','period_end');require_balance(a,sid,measure)
            if balance_link_creates_cycle(a,category,sid):raise ValueError('Calculation balance would create an expense cycle')
        if op=='activity':
            if s.get('observation','current') not in {'current','cumulative'}:raise ValueError('Invalid flow observation')
            if expense_cycle(a,category,sid):raise ValueError('Calculation activity would create an expense cycle')
        if op=='deposit_interest':
            p=next(x for x in a.get('deposit_products') or [] if x.get('source_catalog_id')==sid)
            if balance_link_creates_cycle(a, category, 'deposit.'+sid+'.balance'):
                raise ValueError('Calculation deposit interest would create an expense cycle')
            # An equity-budget retention pool depends on prior overhead only; no current expense feedback.
            if p.get('balance_mode')=='pool':
                g=next((x for x in a.get('deposit_retention_pools') or [] if x.get('id')==p.get('retention_pool_id')),None)
                if not g:raise ValueError('Deposit interest source has a missing retention pool')
        return {**s,'resolved_unit':meta['unit']}
    result=compile_node(node)
    if result['resolved_unit']!='money':raise ValueError('Expense calculation must resolve a monetary amount')
    return result

def evaluate(node, i, metrics, trace=None, path='result'):
    op=node.get('op','entered')
    if op in OPS:
        args=node['args'];v=evaluate(args[0],i,metrics,trace,path+'.1')
        if op=='if_positive':
            result=evaluate(args[1 if v>0 else 2],i,metrics,trace,path+('.2' if v>0 else '.3'))
        else:
            w=evaluate(args[1],i,metrics,trace,path+'.2')
            if op=='add':result=v+w
            elif op=='subtract':result=v-w
            elif op=='multiply':result=v*w
            elif w==0:
                if node.get('zero_policy','error')!='zero':raise ValueError('Linked calculation cannot divide by zero')
                result=0.
            else:result=v/w
    elif op=='entered':result=node['values'][i]
    elif op=='balance':
        obs=(metrics.get('catalog_balances') or {}).get(node['series_id'])
        if obs is None:raise ValueError('Calculation balance unavailable: '+node['series_id'])
        result=obs[node.get('measure','period_end')]
    elif op=='activity':
        obs=(metrics.get('account_activity') or {}).get(node['series_id'])
        if obs is None or obs['temporal']!='flow':raise ValueError('Calculation requires an available gross count flow')
        vals=obs['values'];result=sum(vals[:i+1]) if node.get('observation','current')=='cumulative' else vals[i]
    else:
        key=(op,node['series_id']);sources=metrics.get('linked_calculation_sources') or {}
        if key not in sources:raise ValueError('Calculation observation unavailable: '+str(key))
        result=sources[key]
    result=float(result)
    if not isfinite(result):raise ValueError('Calculation produced a non-finite value')
    if trace is not None:trace.append({'path':path,'label':node.get('name') or op,'unit':node['resolved_unit'],'value':result})
    return result

def runtime_sources(a, i, ppy, context, deposits, *, curves, profile_b=False, rate_fn=None):
    # No state is accumulated here: solver retries must overwrite the same observation.
    out={('reference_rate',k):curve(i+1) for k,curve in curves.items()}
    for p in deposits:
        sid=p.get('source_catalog_id')
        if not sid:continue
        value=(p['_interest_expense'][i] if '_minimum_interest' in p else p['_avg'][i]*rate_fn(p)/ppy) if profile_b else p['_ie'][i+1]
        out[('deposit_interest',sid)]=float(value)
    return out

def result_sources(cfg, results, i, *, native=False):
    # Curves come from the same resolver as the engines (including engagement schedules).
    a=cfg['assumptions'];ppy=int(a.get('periods_per_year',4))
    from .engine_q_a import _build_rate_curve_set
    curves=_build_rate_curve_set(a,cfg,ppy)
    out={('reference_rate',k):v(i+1) for k,v in curves.items()}
    products=[p for p in results.get('products',[]) if p.get('family')=='deposit']
    for p,r in zip(a.get('deposit_products') or [],products):
        sid=p.get('source_catalog_id')
        if sid:out[('deposit_interest',sid)]=float(r['intExp'][i])*(1 if native else 1000)
    return out
