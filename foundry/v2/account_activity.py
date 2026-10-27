"""Opt-in customer flows and subscriber adoption; canonical monthly count semantics.

This module owns population equations, never income or expense posting. Stable IDs
are authored, not inferred from labels. Reconciling additions are not gross openings.
"""
import math

FLOW_FIELDS = ('new_customers', 'lost_customers')
ADOPTION_FIELDS = ('count', 'additions', 'cancellations', 'exits')

def _number(value, label):
    v = float(value)
    if not math.isfinite(v) or v < 0:
        raise ValueError(label + ' must be finite and nonnegative')
    return v

def _path(spec, months, context=None, probability=False):
    from .series import resolve_entered_series
    if not isinstance(spec, dict):
        raise ValueError('Activity paths require an explicit entered path')
    values = resolve_entered_series(spec, months, 12, context=context)
    period = spec.get('period') or spec.get('cadence')
    if period not in {'month', 'quarter', 'year'}:
        raise ValueError('Adoption probabilities require Month / Quarter / Year period')
    width = {'month':1, 'quarter':3, 'year':12}[period]
    result = []
    for x in values:
        v = _number(x, 'Adoption share / probability')
        if v > 1: raise ValueError('Adoption share / probability must be between 0 and 1')
        result.append(1 - (1-v)**(1/width) if probability else v)
    return result

def flow_eligible(feed):
    return (feed.get('intra_period_path') or 'monthly_flows') == 'monthly_flows'


def ensure_flow_ids(a):
    """Assign missing publication metadata only; existing authored IDs always win.

    Deterministic IDs let API-only legacy models discover and consume flows before
    a browser save. Authoring persists these IDs, so rename/reorder keeps identity.
    """
    from uuid import uuid5, NAMESPACE_URL
    for name, feed in (a.get('cac_feeds') or {}).items():
        if not flow_eligible(feed):
            continue
        seed = feed.get('customer_count_series_id') or feed.get('series_id')
        if not seed:
            seed = 'cac-count-' + uuid5(NAMESPACE_URL, 'foundry:feed:' + name).hex
            feed['customer_count_series_id'] = seed
        ids = feed.setdefault('activity_series_ids', {})
        for field in FLOW_FIELDS:
            ids.setdefault(field, str(seed) + '::' + field)
        for ci, ch in enumerate(feed.get('channels') or []):
            derived = ch.setdefault('derived_series_ids', {})
            if not derived.get('new_customers'):
                derived['new_customers'] = 'cac-new-' + uuid5(NAMESPACE_URL, str(seed) + ':' + str(ci) + ':' + str(ch.get('name') or '')).hex
            ids = ch.setdefault('activity_series_ids', {})
            for field in FLOW_FIELDS:
                ids.setdefault(field, str(derived['new_customers']) + '::' + field)


def catalog(a):
    ensure_flow_ids(a)
    out = []
    for name, feed in (a.get('cac_feeds') or {}).items():
        if not flow_eligible(feed):
            continue
        ids = feed.get('activity_series_ids') or {}
        for field in FLOW_FIELDS:
            if ids.get(field):
                out.append(dict(series_id=ids[field], label=f'Customer acquisition › {name} › '+field.replace('_',' ').title(), temporal='flow', feed=name, field=field))
        for ci,ch in enumerate(feed.get('channels') or []):
            for field in FLOW_FIELDS:
                sid=(ch.get('activity_series_ids') or {}).get(field)
                if sid:out.append(dict(series_id=sid,label=f'Customer acquisition › {name} › {ch.get("name") or "Channel"} › '+field.replace('_',' ').title(),temporal='flow',feed=name,field=field,channel=ci))
    for item in a.get('account_adoption') or []:
        ids=item.get('series_ids') or {}
        mode=item.get('mode')
        for field in ADOPTION_FIELDS:
            if ids.get(field):
                word={'count':'Active subscribers','exits':'Customer attrition exits','additions':'Gross openings' if mode=='gross_flows' else 'Reconciling additions','cancellations':'Subscriber closures' if mode=='gross_flows' else 'Reconciling cancellations'}[field]
                out.append(dict(series_id=ids[field],label=f'Account adoption › {item.get("name") or "Subscribers"} › {word}',temporal='level' if field=='count' else 'flow',adoption=item.get('id'),field=field))
    ids=[x['series_id'] for x in out]
    if any(not isinstance(x,str) or not x.strip() for x in ids) or len(ids)!=len(set(ids)):
        raise ValueError('Account activity Series IDs must be nonblank and unique')
    reserved={x.get('customer_count_series_id') for x in (a.get('cac_feeds') or {}).values()} | {x.get('series_id') for x in (a.get('cac_feeds') or {}).values()}
    reserved|={s.get('quantity_series_id') for k in ('obs_exposures','lending_products','deposit_products') for p in a.get(k) or [] for s in p.get('fee_streams') or []}
    if set(ids)&reserved:raise ValueError('Account activity Series ID collides with another publisher')
    return out

def resolve(a, n, ppy, growth_context=None):
    from .cac_feeder import cac_auc_rollforward
    ensure_flow_ids(a)
    if ppy not in (4,12):raise ValueError('Account activity supports monthly and quarterly models')
    months=n*(12//ppy); result={};feeds={};audits={}
    def publish(sid, vals, temporal, opening=0):
        if not sid:return
        width=12//ppy
        native=[sum(vals[i:i+width]) if temporal=='flow' else vals[i+width-1] for i in range(0,months,width)]
        average=[sum(vals[i:i+width])/width for i in range(0,months,width)]
        result[sid]=dict(canonical_values=vals,values=native,average_values=average,temporal=temporal,opening=opening)
    for name,f in (a.get('cac_feeds') or {}).items():
        if not f.get('activity_series_ids') and not any(c.get('activity_series_ids') for c in f.get('channels') or []) and not any(x.get('customer_source_id')==f.get('customer_count_series_id') for x in a.get('account_adoption') or []):continue
        # Straight-line interpolation has *implied* monthly losses, not gross attrition.
        # Reject it for this opt-in publisher instead of relabelling implied negatives.
        if not flow_eligible(f):
            if any(x.get('customer_source_id') == f.get('customer_count_series_id') for x in a.get('account_adoption') or []):
                raise ValueError('Account activity requires CAC monthly_flows; straight-line implied losses are not gross attrition')
            continue
        r=cac_auc_rollforward(f,n,ppy,assumptions=a,growth_context=growth_context); rows=r['monthly'][:months];feeds[f.get('customer_count_series_id')]=(f,rows)
        ids=f.get('activity_series_ids') or {}
        for field,key in [('new_customers','new_cust'),('lost_customers','cust_lost')]:publish(ids.get(field),[float(x[key]) for x in rows],'flow')
        chs=f.get('channels') or [];stocks=[_number(c.get('opening_customers',0),'Channel opening customers') for c in chs]
        if sum(stocks)>float(f.get('beginning_customers') or 0)+1e-8:raise ValueError('Channel opening customers exceed feed opening customers')
        losses=[[] for c in chs]
        for row in rows:
            beg=float(row['beg_cust']);lost=float(row['cust_lost'])
            if lost<0 or lost>beg+1e-8:raise ValueError('Customer losses must not exceed beginning customers for account activity')
            for ci,c in enumerate(chs):
                loss=stocks[ci]*lost/beg if beg else 0.;losses[ci].append(loss);stocks[ci]+=row['channels'][ci]['new_customers']-loss
        for ci,c in enumerate(chs):
            ids=c.get('activity_series_ids') or {}
            publish(ids.get('new_customers'),[float(x['channels'][ci]['new_customers']) for x in rows],'flow')
            publish(ids.get('lost_customers'),losses[ci],'flow')
    seen=set()
    for item in a.get('account_adoption') or []:
        ident=item.get('id')
        if not ident or ident in seen:raise ValueError('Account adoption IDs must be present and unique')
        seen.add(ident)
        source=item.get('customer_source_id')
        if not isinstance(source,str) or not source.strip():raise ValueError('Account adoption requires a stable customer source ID')
        if source not in feeds:raise ValueError('Account adoption requires an existing CAC customer-count source')
        f,rows=feeds[source];mode=item.get('mode')
        if mode not in {'target_share','gross_flows'}:raise ValueError('Account adoption mode must be target_share or gross_flows')
        if item.get('exit_assumption')!='proportional_customer_attrition':raise ValueError('Select proportional customer attrition explicitly')
        if 'opening_subscribers' not in item:raise ValueError('Account adoption requires explicit opening subscribers')
        stock=_number(item['opening_subscribers'],'Opening subscribers');opening=stock
        if stock>float(f.get('beginning_customers') or 0)+1e-8:raise ValueError('Opening subscribers exceed opening customers')
        incompatible=('new_customer_adoption','existing_customer_adoption','closure_probability') if mode=='target_share' else ('target_share',)
        if any(item.get(k) is not None for k in incompatible):raise ValueError('Choose only one account adoption method; remove inactive method inputs')
        if mode=='target_share':targets=_path(item.get('target_share'),months,growth_context)
        else:
            new=_path(item.get('new_customer_adoption'),months,growth_context,True)
            existing=_path(item.get('existing_customer_adoption'),months,growth_context,True)
            closure=_path(item.get('closure_probability'),months,growth_context,True)
        vals={k:[] for k in ADOPTION_FIELDS};detail=[]
        for i,row in enumerate(rows):
            beg=float(row['beg_cust']);end=float(row['end_cust']);lost=float(row['cust_lost']);adds=float(row['new_cust'])
            if lost<0 or lost>beg+1e-8 or end<0:raise ValueError('Inconsistent CAC losses for adoption')
            exits=stock*lost/beg if beg else 0.;survivors=stock-exits
            if mode=='target_share':
                target=targets[i]*end;delta=target-survivors;op=max(delta,0);cl=max(-delta,0);eligible=None
            else:
                eligible=beg-lost-survivors
                if eligible<-1e-8:raise ValueError('Subscriber population exceeds eligible surviving customers')
                cl=survivors*closure[i];op=adds*new[i]+eligible*existing[i];target=survivors-cl+op
            if target<0 or target>end+1e-8:raise ValueError('Adoption produces an impossible subscriber count')
            share=target/end if end else 0.
            detail.append(dict(month=i+1,beginning=stock,customer_exits=exits,additions=op,cancellations=cl,ending=target,adoption_share=share,eligible_existing_nonholders=eligible))
            for k,v in [('count',target),('additions',op),('cancellations',cl),('exits',exits)]:vals[k].append(v)
            stock=target
        ids=item.get('series_ids') or {}
        if set(ids)!=set(ADOPTION_FIELDS):raise ValueError('Account adoption requires stable IDs for count, additions, cancellations and exits')
        for k,v in vals.items():publish(ids[k],v,'level' if k=='count' else 'flow',opening if k=='count' else 0)
        audits[ident]=dict(name=item.get('name') or 'Subscribers',mode=mode,exit_assumption=item['exit_assumption'],same_month_reopening=False,monthly=detail)
    catalog(a)
    return result,audits

def needs_monthly(stream, definitions, seen=None):
    seen=set(seen or ());ident=id(stream)
    if ident in seen:return False
    seen.add(ident);d=stream.get('driver') or {}
    if d.get('source')=='account_activity' or (stream.get('cost') or {}).get('kind')=='per_account' or (d.get('params') or {}).get('share_spec') is not None:return True
    if d.get('source') in {'stream_ref','fee_stream_quantity'}:
        parent=definitions.get(str(d.get('ref') or ''))
        return bool(parent and needs_monthly(parent,definitions,seen))
    return False

def monthly_fee(stream,q,ctx,ppy,evaluator,*,force=False):
    """Replay only opt-in chains monthly, preserving SUM(quantity_m * price_m)."""
    import copy
    definitions=dict(ctx.get('linked_stream_defs') or {});definitions.update(ctx.get('stream_defs') or {})
    if not force and not needs_monthly(stream,definitions):return None
    width=12//ppy;lo=(q-1)*width;hi=q*width;cache={};visiting=set()
    def eval_month(st,mi):
        key=(id(st),mi)
        if key in cache:return cache[key]
        if key in visiting:raise ValueError('Account activity fee dependency cycle')
        visiting.add(key);s=copy.deepcopy(st);d=s.get('driver') or {};src=d.get('source','constant');params=d.get('params') or {}
        c=dict(ctx);c['_account_monthly']=True;c['capture_stream_qty']={};c['capture_stream_economics']={};c['stream_qty']={};c['linked_stream_qty']={};c['periods_per_year']=12
        for source,keyname in [('stream_ref','stream_qty'),('fee_stream_quantity','linked_stream_qty')]:
            if src==source:
                ref=str(d.get('ref') or '');parent=definitions.get(ref)
                if source=='stream_ref':
                    owner=(ctx.get('activity_stream_owners') or {}).get(st.get('quantity_series_id'))
                    if owner is not None:parent=next((x for x in owner if x.get('name')==ref),None)
                if parent is None:raise ValueError('Monthly activity source is missing: '+ref)
                _,_,qty,_=eval_month(parent,mi)
                c[keyname][ref]=qty if source=='stream_ref' else [0.]*mi+[qty]
        if src=='account_activity':
            sid=d.get('ref');meta=(ctx.get('account_activity') or {}).get(sid)
            if meta is None:raise ValueError('Account activity source is unavailable: '+str(sid))
            vals=meta['canonical_values']
            if st.get('basis')=='account' and d.get('measure')=='period_average':
                vals=[((meta['opening'] if j==0 else vals[j-1])+v)/2 for j,v in enumerate(vals)]
            c['account_activity']={sid:dict(meta,values=vals)}
        elif src=='customer_acquisition_count':
            meta=(ctx.get('cac_monthly_counts') or {}).get(d.get('ref'))
            if meta is None:raise ValueError('Canonical monthly customer count unavailable')
            c['customer_acquisition_count']={d['ref']:{k:v[mi] for k,v in meta.items()}}
        elif src=='constant':
            if params.get('schedule') or params.get('level_schedule',{}).get('period')=='model_period':raise ValueError('Monthly account-cost chains require natural-period schedules, not legacy model-period schedules')
        elif src in {'own_balance','distributed_balance','product_funded_flow'} and ctx.get('_profile_monthly_operands') is not None:
            c[src] = ctx['_profile_monthly_operands'][src][mi]
            if src == 'own_balance' and 'own_balance_begin' in ctx['_profile_monthly_operands']:
                c['own_balance_begin'] = ctx['_profile_monthly_operands']['own_balance_begin'][mi]
            if src == 'own_balance' and 'own_balance_end' in ctx['_profile_monthly_operands']:
                c['own_balance_end'] = ctx['_profile_monthly_operands']['own_balance_end'][mi]
        elif src not in {'stream_ref','fee_stream_quantity'}:raise ValueError('This source has no canonical monthly path for this calculation')
        tm=s.get('timing') or {};s['timing']=dict(tm,start_period=(int(tm.get('start_period') or 1)-1)*width+1)
        if tm.get('end_period') is not None:s['timing']['end_period']=int(tm['end_period'])*width
        if tm.get('ramp_in_periods'):raise ValueError('Monthly account activity chains require an explicit adoption path rather than a revenue ramp')
        coef=params.get('coefficient') or {}
        if coef.get('kind')=='pct' and not coef.get('semantics'):
            from .income_modules import fee_quantity_kind
            def source_kind(node,seen=None):
                seen=set(seen or ());token=id(node)
                if token in seen:raise ValueError('Account activity quantity cycle')
                seen.add(token);nd=node.get('driver') or {};dep='native'
                if nd.get('source')=='fee_stream_quantity':parent=definitions.get(nd.get('ref'))
                elif nd.get('source')=='stream_ref':
                    siblings=(ctx.get('activity_stream_owners') or {}).get(node.get('quantity_series_id')) or list(definitions.values())
                    parent=next((x for x in siblings if x.get('name')==nd.get('ref')),None)
                else:parent=None
                if parent:dep=source_kind(parent,seen)
                return fee_quantity_kind(node,dep)
            if src in {'customer_acquisition_count','account_activity'}:kind='count'
            elif src in {'stream_ref','fee_stream_quantity'}:kind=source_kind(parent)
            else:kind='native'
            s['driver']['params']['coefficient']['semantics']='share' if kind=='count' else 'flow'
        inc,cost=evaluator(s,mi+1,c,12);sid=s.get('quantity_series_id');rec=c['capture_stream_economics'].get(sid,{})
        qty=c['stream_qty'].get(s.get('name'),0.)
        if not sid:
            # Diagnostic identity belongs only to this local replay, never persisted.
            s['quantity_series_id']='__activity_replay__';c['capture_stream_economics']={};inc,cost=evaluator(s,mi+1,c,12);rec=c['capture_stream_economics'].get('__activity_replay__',{})
        if 'quantity' in rec:qty=rec['quantity'][mi] or 0.
        result=(inc,cost,qty,{k:v[mi] for k,v in rec.items() if isinstance(v,list) and len(v)>mi})
        cache[key]=result;visiting.remove(key);return result
    rows=[eval_month(stream,mi) for mi in range(lo,hi)];inc=sum(x[0] for x in rows);cost=sum(x[1] for x in rows)
    level=stream.get('basis') in {'account','balance'};qty=sum(x[2] for x in rows)/(width if level else 1)
    name=stream.get('name');ctx.setdefault('stream_qty',{})[name]=qty
    sid=stream.get('quantity_series_id')
    if sid:
        arr=ctx.setdefault('capture_stream_qty',{}).setdefault(sid,[])
        while len(arr)<q:arr.append(0.)
        arr[q-1]=qty
        cap=ctx.get('capture_stream_economics')
        if isinstance(cap,dict):
            rec=cap.setdefault(sid,dict(basis=stream.get('basis'),cost_kind=(stream.get('cost') or {}).get('kind','none')))
            if stream.get('basis')=='transaction':rec['pricing_basis']=((stream.get('rate') or {}).get('params') or {}).get('pricing_basis','per_unit')
            monetary={'gross_fee_revenue','contra_revenue','reported_fee_income','fee_product_cost'}
            for field in set().union(*(x[3] for x in rows)):
                vs=[x[3].get(field,0. if field in monetary or field=='quantity' else None) for x in rows];v=None if any(x is None for x in vs) else sum(vs)/(1 if field in monetary else width)
                if field=='quantity':v=qty
                if field in {'pricing_factor','effective_cost_factor'} and qty:
                    numer=sum(x[2]*(x[3].get(field) or 0.) for x in rows)
                    v=numer/qty
                    if field=='pricing_factor' and stream.get('basis')=='balance':
                        # Balance prices are annual rates, unlike Account's $/engine-period price.
                        v=numer/(qty*width)
                    if field=='effective_cost_factor':
                        kind=(stream.get('cost') or {}).get('kind')
                        if kind in {'pct_of_revenue','pct_of_revenue_opex'}:
                            gross=sum(x[3].get('gross_fee_revenue',0.) or 0. for x in rows)
                            v=(sum((x[3].get('gross_fee_revenue',0.) or 0.)*(x[3].get(field) or 0.) for x in rows)/gross if gross else sum(x[3].get(field,0.) or 0. for x in rows)/width)
                        elif kind=='periodic_amount_opex':v=cost
                arr=rec.setdefault(field,[])
                while len(arr)<q:arr.append(None)
                arr[q-1]=v
    return inc,cost

def upstream_feed(a, sid):
    """Stable activity ID -> owning CAC feed, used by expense cycle checks."""
    row=next((x for x in catalog(a) if x['series_id']==sid),None)
    if not row:return None
    if row.get('feed'):return row['feed']
    source=next((x.get('customer_source_id') for x in a.get('account_adoption') or [] if x.get('id')==row.get('adoption')),None)
    return next((name for name,f in (a.get('cac_feeds') or {}).items() if f.get('customer_count_series_id')==source),None)

def expense_cycle(a, category, sid):
    from .opex_extensions import auc_link_creates_cycle
    owner=upstream_feed(a,sid)
    if owner:return bool(auc_link_creates_cycle(a,category,a['cac_feeds'][owner].get('series_id')))
    products=[p for k in ('obs_exposures','deposit_products','lending_products') for p in a.get(k) or []]
    external={s.get('quantity_series_id'):(s,p) for p in products for s in p.get('fee_streams') or [] if s.get('quantity_series_id')}
    seen=set()
    def visit(pair):
        if not pair:return False
        node,product=pair
        if id(node) in seen:return False # The fee planner rejects stream cycles separately.
        seen.add(id(node));driver=node.get('driver') or {}
        if driver.get('source')=='account_activity':
            feed=upstream_feed(a,driver.get('ref'))
            return bool(feed and auc_link_creates_cycle(a,category,a['cac_feeds'][feed].get('series_id')))
        if driver.get('source')=='fee_stream_quantity':return visit(external.get(driver.get('ref')))
        if driver.get('source')=='stream_ref':
            parent=next((s for s in product.get('fee_streams') or [] if s.get('name')==driver.get('ref')),None)
            return visit((parent,product)) if parent else False
        return False
    return visit(external.get(sid))

def validate_fee_paths(a,n,ppy,growth_context=None):
    """Fail before projection when an opt-in chain lacks canonical monthly operands."""
    from .income_modules import _validate_fee_stream_shape
    products=[p for k in ('obs_exposures','deposit_products','lending_products') for p in a.get(k) or []]
    external={s.get('quantity_series_id'):s for p in products for s in p.get('fee_streams') or [] if s.get('quantity_series_id')}
    owners={s.get('quantity_series_id'):p.get('fee_streams') or [] for p in products for s in p.get('fee_streams') or []}
    activity={x['series_id']:x for x in catalog(a)}
    for p in products:
        defs=dict(external);defs.update({s.get('name'):s for s in p.get('fee_streams') or []})
        for st in p.get('fee_streams') or []:
            if not needs_monthly(st,defs):continue
            seen=set()
            def visit(node):
                if id(node) in seen:raise ValueError('Account activity fee dependency cycle')
                seen.add(id(node));_validate_fee_stream_shape(node)
                d=node.get('driver') or {};src=d.get('source','constant');params=d.get('params') or {}
                if src=='account_activity':
                    meta=activity.get(d.get('ref'))
                    if meta is None:raise ValueError('Account activity source is missing')
                    if (node.get('basis')=='account')!=(meta['temporal']=='level'):raise ValueError('Account activity level / flow basis mismatch')
                elif src in {'stream_ref','fee_stream_quantity'}:
                    parent=external.get(d.get('ref')) if src=='fee_stream_quantity' else next((x for x in owners.get(node.get('quantity_series_id'),p.get('fee_streams') or []) if x.get('name')==d.get('ref')),None)
                    if parent is None:raise ValueError('Monthly activity upstream stream is missing')
                    visit(parent)
                elif src not in {'constant','customer_acquisition_count'}:
                    raise ValueError('Account activity / per-account costs require a canonical monthly count source')
                if params.get('share_spec') is not None:_path(params['share_spec'],n*(12//ppy),growth_context)
                if params.get('schedule'):raise ValueError('Account activity chains require natural-period schedules, not legacy model-period schedules')
                if (node.get('timing') or {}).get('ramp_in_periods'):raise ValueError('Use an adoption path rather than a revenue ramp on account activity chains')
                def periods(value):
                    if isinstance(value,dict):
                        if value.get('period')=='model_period' or value.get('cadence')=='model_period':raise ValueError('Account activity chains require explicit Month / Quarter / Year units')
                        for child in value.values():periods(child)
                    elif isinstance(value,list):
                        for child in value:periods(child)
                periods(params);periods((node.get('rate') or {}).get('params') or {});periods((node.get('cost') or {}).get('params') or {})
                seen.remove(id(node))
            visit(st)
