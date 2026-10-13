"""Non-posting revenue observations -> weighted settlement liability stocks."""
import math
from copy import deepcopy

class SettlementInputError(ValueError):
    """An authored settlement cannot produce a valid liability stock."""

MEASURES={'reported_fee_income','fee_product_cost','net_fee_income'}

def sources(a):
    rows=[]
    for collection in ('obs_exposures',):
        for p in a.get(collection) or []:
            for s in p.get('fee_streams') or []:
                sid=s.get('quantity_series_id')
                if not sid or (s.get('rate') or {}).get('behavior')=='durbin_capped':continue
                rows.append({'series_id':sid,'label':(p.get('name') or 'Product')+' › '+(s.get('name') or 'Stream'),'timing':deepcopy(s.get('timing') or {})})
    from collections import Counter
    counts=Counter(r['series_id'] for r in rows)
    return [r for r in rows if counts[r['series_id']]==1]

def prepare(raw,a,ppy):
    c=deepcopy(raw);spec=c.get('settlement') or {}
    if spec.get('period')!={12:'month',4:'quarter',1:'year'}.get(int(ppy)):
        raise SettlementInputError('Settlement holding period must match model cadence; reauthor weights explicitly before changing cadence')
    weights=spec.get('weights');history=spec.get('opening_history',[]);sign=spec.get('sign',1)
    def finite(x):return isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x)
    if not isinstance(weights,list) or not weights or len(weights)>120 or any(not finite(x) or x<0 for x in weights):raise SettlementInputError('Settlement weights must be finite nonnegative period weights')
    if sign not in (-1,1) or isinstance(sign,bool):raise SettlementInputError('Settlement sign must be +1 or -1')
    if not isinstance(history,list) or len(history)<len(weights)-1 or any(not finite(x) for x in history):raise SettlementInputError('Settlement opening revenue history is required for every lag (most recent first)')
    opening=c.get('opening_balance',0)
    if not finite(opening) or opening<0:raise SettlementInputError('Settlement opening liability must be finite and nonnegative')
    selected=spec.get('sources') or [];meta={x['series_id']:x for x in sources(a)};known=set(meta);pairs=[]
    if not selected:raise SettlementInputError('Choose at least one settlement revenue source')
    for src in selected:
        pair=(src.get('series_id'),src.get('measure','reported_fee_income'))
        if pair[0] not in known:raise SettlementInputError('Missing settlement revenue source: '+str(pair[0]))
        if pair[1] not in MEASURES:raise SettlementInputError('Unsupported settlement revenue measure')
        if pair in pairs:raise SettlementInputError('Duplicate settlement revenue selection')
        if any(p[0]==pair[0] and (p[1]=='net_fee_income' or pair[1]=='net_fee_income') for p in pairs):raise SettlementInputError('Do not select net income and its constituent income/cost for the same settlement source')
        pairs.append(pair)
    return {'component_id':c['component_id'],'name':c.get('name') or 'Settlement liability','settlement':spec,'opening_balance':float(opening),'terms':[],'source_timings':{sid:meta[sid]['timing'] for sid,_ in pairs}}

def bind(row,economics,n):
    s=row['settlement'];flow=[0.]*n
    for src in s['sources']:
        rec=economics.get(src['series_id']) or {}
        timing=row.get('source_timings',{}).get(src['series_id'],{})
        start=int(timing.get('start_period') or 1);end=timing.get('end_period')
        measure=src.get('measure','reported_fee_income');fields=['reported_fee_income','fee_product_cost'] if measure=='net_fee_income' else [measure]
        for field in fields:
            vals=rec.get(field) or []
            resolved=[]
            for i in range(n):
                if i+1<start or (end is not None and i+1>int(end)):resolved.append(0.);continue
                if i>=len(vals) or vals[i] is None or not math.isfinite(vals[i]):raise SettlementInputError('Incomplete active settlement revenue source')
                resolved.append(vals[i])
            vals=resolved
            factor=-1 if measure=='net_fee_income' and field=='fee_product_cost' else 1
            flow=[x+factor*y for x,y in zip(flow,vals)]
    history=s.get('opening_history') or [];parts=[]
    for lag,w in enumerate(s['weights']):
        vals=[flow[i-lag] if i>=lag else history[lag-i-1] for i in range(n)]
        parts.append({'term_id':row['component_id']+'.lag'+str(lag),'driver_kind':'settlement_revenue','series_id':row['component_id']+'.eligible_revenue','driver_name':'Eligible revenue · lag '+str(lag),'driver_unit':'$','driver':vals,'multiplier':[s.get('sign',1)*w]*n,'lag':lag})
    totals=[sum(t['driver'][i]*t['multiplier'][i] for t in parts) for i in range(n)]
    for i,amount in enumerate(totals):
        if not math.isfinite(amount) or amount<0:
            period=s.get('period','period')
            raise SettlementInputError(f"Settlement '{row['name']}' produces a negative or nonfinite liability in {period} {i+1}. Check Source sign and opening revenue history. Use Reverse sign (−1) when the selected revenue is negative and represents an amount owed. No balance was clipped or sign changed automatically.")
    row['terms']=parts;row['eligible_revenue']=flow;row['resolved_balance']=totals
