"""Named non-earning Other Assets using the existing source × multiplier grammar.

An entered level or a linked pre-expense flow/count/stock produces an asset stock.
Optional days outstanding converts a period flow using an explicit annual day basis.
The bank funding plug allocates that stock; no income is recognized a second time.
Flat configurations retain their exact historical result contract.
"""
from typing import Mapping
import math
from .other_liabilities import (_resolve_entered, _driver_metadata,
                               other_liability_period, other_liability_audit_payload)

_FLOW_SOURCES = {'fees': 'Bank · Total fee income'}


def other_asset_mode(a):
    a=a or {}
    return a.get('other_assets_mode') or ('formula_level' if isinstance(a.get('other_assets_model'),Mapping) else 'flat')


def prepare_other_assets(a,n_periods,ppy,*,growth_context=None):
    from .series import normalize_series_spec,resolve_series_spec
    a=a or {}
    mode=other_asset_mode(a)
    if mode=='flat':return None
    if mode!='formula_level':raise ValueError('Other Assets mode must be flat or formula_level')
    m=a.get('other_assets_model')
    if not isinstance(m,Mapping):raise ValueError('Other Assets Formula / level requires a model')
    n,ppy=int(n_periods),int(ppy)
    def entered(spec,default=0):
        vals=_resolve_entered(spec,n,ppy,growth_context=growth_context,default_value=default)
        if not all(math.isfinite(x) for x in vals):raise ValueError('Other Assets inputs must be finite')
        return vals
    opening=float(m.get('opening_balance',a.get('other_assets',0)))
    if not math.isfinite(opening) or opening<0:raise ValueError('Other Assets opening balance must be finite and non-negative')
    base=entered(m.get('base_spec'))
    if any(x<0 for x in base):raise ValueError('Other Assets base must be non-negative')
    rows=[];ids=set();tids=set()
    for c in m.get('components') or []:
        if not isinstance(c,Mapping):raise ValueError('Other Assets component must be an object')
        cid=str(c.get('component_id') or '').strip()
        if not cid or cid in ids:raise ValueError('Other Assets component IDs must be present and unique')
        ids.add(cid)
        if not isinstance(c.get('terms'),list):raise ValueError('Other Assets component requires terms')
        terms=[]
        for t in c['terms']:
            if not isinstance(t,Mapping):raise ValueError('Other Assets term must be an object')
            tid=str(t.get('term_id') or '').strip()
            if not tid or tid in tids:raise ValueError('Other Assets term IDs must be present and unique')
            tids.add(tid);ns=normalize_series_spec(t.get('driver_spec'),default_value=0)
            driver=None
            if ns['source']=='entered':
                kind,sid,name,unit='entered',tid,'Entered asset level','$'
                driver=entered(ns)
            elif ns['source']=='link':
                link=ns.get('link') or {};kind=str(link.get('kind') or '');sid=str(link.get('series_id') or '')
                if kind=='bank_income_flow':
                    if sid not in _FLOW_SOURCES:raise ValueError('Other Assets income source is unavailable or self-dependent')
                    name,unit=_FLOW_SOURCES[sid],'$'
                elif kind in {'workforce_role_count','fixed_asset_level'}:
                    name,unit=_driver_metadata(a,kind,sid)
                    if kind=='fixed_asset_level':driver=list(resolve_series_spec(ns,a,n,ppy,context=growth_context))
                else:raise ValueError('Other Assets linked source is unsupported')
            else:raise ValueError('Other Assets derives balances through named source × multiplier terms; arbitrary formulas are unavailable')
            authored=entered(t.get('multiplier_spec'),1)
            mult=list(authored);days=None;year_days=None
            if t.get('days_spec') is not None:
                if kind!='bank_income_flow':raise ValueError('Days outstanding requires a monetary income flow')
                days=entered(t['days_spec']);year_days=float(t.get('year_days',360))
                if not math.isfinite(year_days) or year_days<=0 or any(x<0 for x in days):raise ValueError('Days outstanding must be non-negative and annual day basis positive')
                mult=[authored[i]*days[i]/(year_days/ppy) for i in range(n)]
            terms.append({'term_id':tid,'driver_kind':kind,'series_id':sid,'driver_name':name,
                          'driver_unit':unit,'driver':driver,'multiplier':mult,
                          'days':days,'year_days':year_days,'authored_multiplier':authored})
        rows.append({'component_id':cid,'name':str(c.get('name') or 'Asset component'),'terms':terms})
    return {'opening_balance':opening,'base':base,'components':rows}


def other_asset_period(prepared,i,*,income_flows=None,**kwargs):
    # Resolve deterministic flow operands now, before the funding / interest solver.
    p={**prepared,'components':[]}
    for c in prepared['components']:
        terms=[]
        for t in c['terms']:
            if t['driver_kind']=='bank_income_flow':
                sid=t['series_id']
                if sid not in (income_flows or {}):raise ValueError('Other Assets income source is unavailable')
                terms.append({**t,'driver':[float(income_flows[sid])]*len(prepared['base'])})
            else:terms.append(t)
        p['components'].append({**c,'terms':terms})
    out=other_liability_period(p,i,**kwargs)
    if not math.isfinite(out['total']):raise ValueError('Other Assets resolved balance must be finite')
    return out


def other_asset_audit_payload(prepared,total,period_rows):
    out=other_liability_audit_payload(prepared,total,period_rows)
    for pc,c in zip(prepared['components'],out['components']):
        for pt,t in zip(pc['terms'],c['terms']):
            if pt.get('days') is not None:
                t.update(days=list(pt['days']),year_days=pt['year_days'],authored_multiplier=list(pt['authored_multiplier']))
    return out
