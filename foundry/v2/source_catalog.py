"""Non-posting source metadata and typed consumer bindings.

Catalog discovery never runs the engine or changes a configuration/result. Existing
consumers keep their contracts; new consumers use explicit eligibility, not arbitrary
output-row references. Current-period financial statement residuals are not upstream
OpEx inputs. Equity-budget pools observe PRIOR equity/OpEx, so their current retained
stock can safely feed current OpEx without creating an algebraic cycle.
"""

def balance_catalog(a):
    out = []
    def add(sid, label, family, key, index=None, pool=None, unit='money_stock'):
        out.append(dict(series_id=sid, label=label, family=family, unit=unit,
                        temporal='stock', measures=['period_end','period_begin','period_average'],
                        consumers=['opex_formula'], driver='catalog_quantity',
                        key=key, index=index, pool=pool))
    add('bank.deposits', 'Deposits › Total on-book balance', 'Deposit', 'deposit_total')
    for fam, collection in [('Deposit','deposit_products'),('Lending','lending_products')]:
        used=set()
        for i,p in enumerate(a.get(collection) or []):
            sid=p.get('source_catalog_id')
            if not sid: continue  # Authoring assigns once; never invent position/name IDs.
            if sid in used: raise ValueError('Duplicate product source_catalog_id: '+str(sid))
            used.add(sid)
            add(f'{fam.lower()}.{sid}.balance', f'{fam} › {p.get("name") or fam} › On-book balance', fam, collection, i)
    ids=set()
    for p in a.get('deposit_retention_pools') or []:
        pid=str(p.get('id') or '')
        if not pid or pid in ids: raise ValueError('Deposit pool source IDs must be present and unique')
        ids.add(pid)
        for key,label in [('retainedBalance','Retained on-book balance'),('sweptBalance','Swept out (off-book)'),('availableBalance','Available program balance')]:
            add(f'deposit_pool.{pid}.{key}', f'Deposit pool › {p.get("name") or pid} › {label}', 'Deposit pool', key, pool=pid)
    for row in out:
        if row['key']=='availableBalance': row['measures']=['period_end']
    return out


def catalog(a):
    """Single discovery facade over typed publishers. Bindings are consumer-specific."""
    from .opex_extensions import fee_stream_quantity_catalog, customer_acquisition_auc_catalog, workforce_count_catalog
    from .deposit_balance import source_catalog as deposit_sources
    from .income_modules import _fee_stream_quantity_kinds
    from .fee_links import has_links, FeeLinkPlan
    rows=balance_catalog(a)
    for key,label in [('effr','EFFR'),('sofr','SOFR'),('prime','Prime')]:
        rows.append(dict(series_id=key,label=label+' reference rate (annual)',family='Rates',unit='rate',temporal='rate',measures=[],consumers=['opex_formula'],driver='reference_rate'))
    for p in a.get('deposit_products') or []:
        sid=p.get('source_catalog_id')
        if sid:rows.append(dict(series_id=sid,label='Deposit › '+str(p.get('name') or 'Deposit')+' › Interest expense',family='Deposit expense',unit='money_flow',temporal='flow',measures=[],consumers=['opex_formula'],driver='deposit_interest'))
    for x in acquisition_share_catalog(a):
        rows.append(dict(series_id=x['series_id'],label=x['label'],family='Customer acquisition',unit='share',temporal='share',measures=[],consumers=['opex_formula'],driver='acquisition_share'))
    from .settlement_balances import sources as settlement_sources
    for src in settlement_sources(a):
        for measure,label in [('reported_fee_income','Reported fee income'),('fee_product_cost','Direct stream cost'),('net_fee_income','Fee income less direct cost')]:
            rows.append(dict(series_id=src['series_id']+'.'+measure,stream_id=src['series_id'],measure=measure,label=src['label']+' › '+label,family='Fee income',unit='money_flow',temporal='flow',measures=[],consumers=['settlement_balance'],driver='fee_stream_economics'))
    if a.get('other_liabilities_mode','formula_level')=='formula_level':
        for comp in (a.get('other_liabilities_model') or {}).get('components') or []:
            if comp.get('kind')=='settlement':
                rows.append(dict(series_id='settlement.'+comp['component_id']+'.balance',component_id=comp['component_id'],label='Settlement liability › '+str(comp.get('name') or comp['component_id']),family='Liability',unit='money_stock',temporal='stock',measures=['period_end'],consumers=['cash_allocation'],driver='liability_component'))
    for src in ('fee_income','gain_on_sale','servicing_net','noninterest_income','net_fee_income'):
        rows.append(dict(series_id=src,label=src.replace('_',' ').title(),family='Income',unit='money_flow',temporal='flow',measures=[],consumers=['opex_formula'],driver=src))
    for meta in customer_acquisition_auc_catalog(a):
        rows.append(dict(meta,label='Customer acquisition › '+str(meta.get('feed') or meta.get('name') or meta['series_id']),family='Customer acquisition',unit='money_stock',temporal='stock',measures=['period_end','period_average'],consumers=['opex_formula','cost_pool_balance'],driver='customer_acquisition_auc'))
    for meta in workforce_count_catalog(a):
        rows.append(dict(meta,label='Workforce › '+str(meta.get('role') or meta.get('name') or meta['series_id']),family='Workforce',unit='count',temporal='level',measures=[],consumers=['opex_formula'],driver='workforce_count'))
    opex_ids={x['series_id'] for x in fee_stream_quantity_catalog(a)}
    # Discovery remains usable while the analyst repairs a broken fee link.
    # Dependency-sensitive deposit bindings are withheld until the graph is valid.
    try:
        deps={(x['series_id'],x['kind']):x for x in deposit_sources(a)}
        plan=FeeLinkPlan(a) if has_links(a) else None
    except ValueError:
        deps={};plan=None
    for fam,key in [('Fee Product','obs_exposures'),('Deposit','deposit_products'),('Lending','lending_products')]:
        for pi,p in enumerate(a.get(key) or []):
            streams=p.get('fee_streams') or []
            kinds=_fee_stream_quantity_kinds(streams)
            for si,st in enumerate(streams):
                sid=st.get('quantity_series_id');basis=st.get('basis')
                if not sid or basis not in {'transaction','balance','account'}:continue
                kind=plan.kinds[(pi,si)] if plan and key=='obs_exposures' else kinds.get(si,'native')
                unit=('money_stock' if basis=='balance' else 'money_flow') if kind=='money' else ('count' if basis=='account' or kind=='count' else 'native')
                consumers=[]
                if sid in opex_ids:consumers.append('opex_formula')
                if key=='obs_exposures':consumers.append('fee_quantity')
                if (sid,'fee_quantity') in deps:consumers.append('deposit_'+basis)
                if (sid,'fee_count') in deps:consumers.append('deposit_count')
                if unit=='money_flow' and basis=='transaction' and ((key=='obs_exposures' and (sid,'fee_quantity') in deps) or (key=='deposit_products' and p.get('balance_mode')!='pool' and (st.get('driver') or {}).get('source','constant')=='constant')):consumers.append('lending_funded_flow')
                rows.append(dict(series_id=sid,label=f'{fam} › {p.get("name") or fam} › {st.get("name") or "Stream"}',family=fam,unit=unit,temporal='stock' if basis=='balance' else 'flow' if basis=='transaction' else 'level',measures=[],consumers=consumers,driver='fee_stream_quantity',basis=basis,product_index=pi,stream_index=si,collection=key))
                if (sid,'fee_share') in deps:
                    rows.append(dict(series_id=sid,label=f'{p.get("name") or fam} › {st.get("name") or "Stream"} › Share schedule',family=fam,unit='share',temporal='coefficient',measures=[],consumers=['deposit_share'],driver='fee_share',basis='share'))
    for x in deps.values():
        if x['kind']=='lending_funded_flow':rows.append(dict(series_id=x['series_id'],label=x['label'],family='Lending',unit='money_flow',temporal='flow',measures=[],consumers=['deposit_transaction'],driver='lending_funded_flow',basis='transaction'))
    from .expense_sources import catalog as expense_catalog
    if ((a.get('nie_detail') or {}).get('categories') or []):
        for x in expense_catalog(a):
            rows.append(dict(x, family='Operating expenses', unit='money_flow', temporal='flow', measures=[], consumers=['other_liability_expense'], driver='operating_expense_flow'))
    from .cac_feeder import cac_customer_count_catalog
    from .cost_pools import cost_pool_catalog
    from .account_activity import catalog as activity_catalog
    for x in activity_catalog(a):
        rows.append(dict(x, family='Account activity', unit='count', measures=['period_end','period_average'] if x['temporal']=='level' else [], consumers=['fee_account_activity'] + (['opex_formula'] if x['temporal']=='flow' else []), driver='account_activity'))
    for name, feed in (a.get('cac_feeds') or {}).items():
        if feed.get('intra_period_path') == 'straight_line':
            rows.append(dict(series_id=str(feed.get('customer_count_series_id') or feed.get('series_id') or name)+'::gross_unavailable', label='Customer acquisition › '+name+' › Gross customer flows unavailable', family='Customer acquisition', unit='count', temporal='flow', measures=[], consumers=[], driver='unavailable', unavailable_reason='Straight-line stock interpolation supplies net movements, not gross acquisitions or attrition. Keep the existing stock path or explicitly author Monthly flows before using a per-new-customer input.'))
    for x in cac_customer_count_catalog(a):
        rows.append(dict(x,label='Customer acquisition › '+x['feed']+' › Customers',family='Customer acquisition',unit='count',temporal='level',measures=['period_end','period_average'],consumers=['fee_customer_count'],driver='customer_acquisition_count'))
    for x in cost_pool_catalog(a):
        rows.append(dict(x,label='Cost pool › '+x['name'],family='Cost pool',unit='money_flow',temporal='flow',measures=[],consumers=['fee_cost_pool'],driver='cost_pool'))
    for sid,label in [('bank.total_assets','Total assets'),('bank.equity','Equity'),('bank.cash','Cash'),('bank.net_income','Net income')]:
        rows.append(dict(series_id=sid,label='Bank › '+label,family='Financial statements',unit='money_flow' if sid.endswith('income') else 'money_stock',temporal='flow' if sid.endswith('income') else 'stock',measures=[],consumers=[],driver='downstream',unavailable_reason='Computed after operating expense; a current-period link here would be circular.'))
    return rows


def require_balance(a,sid,measure='period_end'):
    hits=[x for x in balance_catalog(a) if x['series_id']==sid]
    if len(hits)!=1:raise ValueError(f'Linked source {sid!r} is missing or ambiguous')
    if measure not in hits[0]['measures']:raise ValueError('Incompatible balance measure: '+str(measure))
    return hits[0]


def runtime_balances(a,dep,lend,pools,q):
    """One current observation, in native dollars, after pool allocation and before OpEx."""
    out={}
    for x in balance_catalog(a):
        if x['key']=='deposit_total':beg=sum(p['_bal'][q-1] for p in dep);end=sum(p['_bal'][q] for p in dep)
        elif x['pool']:
            pool=next(p for p in pools if p['config']['id']==x['pool']);arr=pool['audit'][x['key']];end=arr[q-1]
            if q>1:beg=arr[q-2]
            elif x['key']=='sweptBalance':beg=pool.get('opening_swept',0.)
            elif x['key']=='retainedBalance':beg=sum(dep[i]['_bal'][0] for i in pool['members'])
            else:beg=float(pool['config'].get('opening_available_balance') or 0.)
        else:
            p=(dep if x['key']=='deposit_products' else lend)[x['index']];beg=p['_bal'][q-1];end=p['_bal'][q]
            if x['key']=='lending_products' and p.get('_is_fv'):
                beg+=p['_fvadj'][q-1];end+=p['_fvadj'][q]
        out[x['series_id']]={'period_begin':beg,'period_end':end,'period_average':(beg+end)/2}
        if x['key']=='lending_products' and p.get('_repayment_profile'):
            width=12//int(a.get('periods_per_year',4));rows=p['_repayment_profile']['monthly'][(q-1)*width:q*width]
            out[x['series_id']]['_monthly']={k:[r[v] for r in rows] for k,v in [('period_begin','beginning'),('period_end','ending'),('period_average','average')]}
    return out


def result_balances(cfg,results,i,native=False):
    """Audit observations; product/pool public monetary outputs are in $000s."""
    a=cfg.get('assumptions') or {};out={};products=results.get('products') or [];scale=1 if native else 1000
    if cfg.get('parity_profile')=='pf_b':
        import copy
        products=copy.deepcopy(products)
        for fam,key in [('deposit','deposit_products'),('lending','lending_products')]:
            for prod,config in zip([p for p in products if p.get('family')==fam],a.get(key) or []):
                prod['bal']=[float(config.get('opening_balance') or 0.)/scale]+prod['bal']
    dep=[p for p in products if p.get('family')=='deposit'];lend=[p for p in products if p.get('family')=='lending']
    for x in balance_catalog(a):
        if x['key']=='deposit_total':beg=sum(p['bal'][i] for p in dep)*scale;end=sum(p['bal'][i+1] for p in dep)*scale
        elif x['pool']:
            arr=(results.get('deposit_retention_pools') or {})[x['pool']][x['key']];end=arr[i]*scale
            if i:beg=arr[i-1]*scale
            elif x['key']=='sweptBalance':beg=float(next(p for p in a['deposit_retention_pools'] if p['id']==x['pool']).get('opening_swept_balance') or 0.)
            elif x['key']=='retainedBalance':beg=sum(float(p.get('opening_balance') or 0.) for p in a.get('deposit_products') or [] if p.get('retention_pool_id')==x['pool'])
            else:beg=0.
        else:
            p=(dep if x['key']=='deposit_products' else lend)[x['index']];beg=p['bal'][i]*scale;end=p['bal'][i+1]*scale
        out[x['series_id']]={'period_begin':beg,'period_end':end,'period_average':(beg+end)/2}
        if x['key']=='lending_products':
            profiles=results.get('repayment_profiles') or []
            profile=next((r['profile'] for r in profiles if r['product_index']==x['index']),None)
            if profile:
                width=12//int(a.get('periods_per_year',4));rows=profile['monthly'][i*width:(i+1)*width]
                out[x['series_id']]['_monthly']={k:[r[v] for r in rows] for k,v in [('period_begin','beginning'),('period_end','ending'),('period_average','average')]}
    return out


def balance_link_creates_cycle(a, category, sid):
    """Follow authored upstream links; lagged pool budgets are not current dependencies."""
    from .opex_extensions import auc_link_creates_cycle
    target=category.get('series_id');seen=set()
    feeds=a.get('cac_feeds') or {}
    owners={}
    cost_pools={p.get('series_id'):p for p in a.get('cost_pools') or []}
    for key in ('obs_exposures','lending_products','deposit_products'):
        for p in a.get(key) or []:
            for st in p.get('fee_streams') or []:
                if st.get('quantity_series_id'):owners[st['quantity_series_id']]=(st,p)
    def strings(value):
        if isinstance(value,dict):
            for key,v in value.items():
                if key=='equity_budget':continue  # previous equity/expense by contract
                if key in {'series_id','ref','managed_notional_source_id'} and isinstance(v,str):yield v
                elif isinstance(v,(dict,list)):yield from strings(v)
        elif isinstance(value,list):
            for v in value:yield from strings(v)
    def visit(ref):
        if ref in seen:return False
        seen.add(ref)
        if target and ref==target:return True
        for feed in feeds.values():
            if ref in {feed.get('series_id'),feed.get('customer_count_series_id')}:
                return auc_link_creates_cycle(a,category,feed.get('series_id'))
        if ref in cost_pools:
            return any(visit(x) for x in strings(cost_pools[ref]))
        if ref in owners:
            st,p=owners[ref]
            if any(visit(x) for x in strings(st)):return True
            d=st.get('driver') or {}
            if d.get('source')=='stream_ref':
                other=next((s for s in p.get('fee_streams') or [] if s.get('name')==d.get('ref')),None)
                if other and any(visit(x) for x in strings(other)):return True
            return any(visit(x) for x in strings({k:v for k,v in p.items() if k!='fee_streams'}))
        return False
    descriptor=require_balance(a,sid)
    if descriptor['pool']:
        inputs=next(p for p in a.get('deposit_retention_pools') or [] if p['id']==descriptor['pool'])
        return any(visit(x) for x in strings(inputs))
    if descriptor['key']=='deposit_total':
        return any(balance_link_creates_cycle(a,category,x['series_id']) for x in balance_catalog(a) if x['key']=='deposit_products') or any(balance_link_creates_cycle(a,category,x['series_id']) for x in balance_catalog(a) if x['pool'] and x['key']=='retainedBalance')
    inputs=(a.get(descriptor['key']) or [])[descriptor['index']]
    if inputs.get('retention_pool_id'):
        return balance_link_creates_cycle(a,category,'deposit_pool.'+inputs['retention_pool_id']+'.retainedBalance')
    return any(visit(x) for x in strings(inputs))


def acquisition_share_catalog(a):
    from .account_activity import catalog as activity_catalog
    rows=activity_catalog(a);out=[]
    for row in rows:
        if row.get('field')!='new_customers' or 'channel' not in row:continue
        total=next((x for x in rows if x.get('feed')==row.get('feed') and x.get('field')=='new_customers' and 'channel' not in x),None)
        if total:
            for observation,label in [('current','Current-period gross acquisition share'),('cumulative','Cumulative gross acquisition share')]:
                out.append(dict(series_id=row['series_id']+'.share.'+observation,label=row['label'].rsplit(' › ',1)[0]+' › '+label,numerator=row['series_id'],denominator=total['series_id'],observation=observation))
    return out

def validate_formula_observation(a,category,f):
    source=f['source'];sid=f['series_id']
    if source=='reference_rate':
        if sid not in {'effr','sofr','prime'}:raise ValueError('Unknown reference rate source')
    elif source=='deposit_interest':
        if not any(p.get('source_catalog_id')==sid for p in a.get('deposit_products') or []):raise ValueError('Missing deposit interest source')
        if balance_link_creates_cycle(a,category,'deposit.'+sid+'.balance'):raise ValueError('Deposit interest observation would create an expense cycle')
    else:
        from .account_activity import expense_cycle
        row=next((x for x in acquisition_share_catalog(a) if x['series_id']==sid),None)
        if not row:raise ValueError('Gross acquisition share source unavailable')
        if expense_cycle(a,category,row['numerator']) or expense_cycle(a,category,row['denominator']):raise ValueError('Acquisition share would create an expense cycle')
        return {'_numerator':row['numerator'],'_denominator':row['denominator'],'_observation':row['observation']}
    return {}

def financial_observations(deposits,i,curves,*,profile_b=False,rate_fn=None,ppy=4):
    out={('reference_rate',key):fn(i+1) for key,fn in curves.items()}
    for p in deposits:
        sid=p.get('source_catalog_id')
        if sid:
            value=(p['_interest_expense'][i] if '_minimum_interest' in p else p['_avg'][i]*rate_fn(p)/ppy) if profile_b else p['_ie'][i+1]
            out[('deposit_interest',sid)]=float(value)
    return out

def result_financial_observations(cfg,results,i,native=False):
    from .engine_q_a import _build_rate_curve_set
    a=cfg['assumptions'];ppy=int(a.get('periods_per_year',4));curves=_build_rate_curve_set(a,cfg,ppy)
    out={('reference_rate',k):fn(i+1) for k,fn in curves.items()}
    for config,p in zip(a.get('deposit_products') or [],[p for p in results.get('products') or [] if p.get('family')=='deposit']):
        sid=config.get('source_catalog_id')
        if sid:out[('deposit_interest',sid)]=float(p['intExp'][i])*(1 if native else 1000)
    return out
