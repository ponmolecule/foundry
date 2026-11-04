"""Non-posting acquisition dollar flows, reusable by explicit product-cost links."""
import math

def catalog(a):
    from .account_activity import ensure_flow_ids
    ensure_flow_ids(a)
    from uuid import uuid5, NAMESPACE_URL
    out=[]
    for name,f in (a.get('cac_feeds') or {}).items():
        seed=f.get('customer_count_series_id') or f.get('series_id')
        if not seed:
            seed='cac-count-'+uuid5(NAMESPACE_URL,'foundry:feed:'+name).hex
            f['customer_count_series_id']=seed
        out.append(dict(series_id=str(seed)+'::spend',label='Customer acquisition › '+name+' › Total spend',feed=name))
        for i,ch in enumerate(f.get('channels') or []):
            ids=ch.setdefault('derived_series_ids',{})
            ids.setdefault('new_customers','cac-new-'+uuid5(NAMESPACE_URL,str(seed)+':'+str(i)+':'+str(ch.get('name') or '')).hex)
            channel_seed=ids['new_customers']
            if channel_seed:out.append(dict(series_id=str(channel_seed)+'::spend',label='Customer acquisition › '+name+' › '+str(ch.get('name') or 'Channel')+' › Spend',feed=name,channel=i))
    ids=[x['series_id'] for x in out]
    if len(ids)!=len(set(ids)):raise ValueError('Acquisition spend source IDs must be unique')
    return out

def resolve(a,n,ppy,growth_context=None):
    from .cac_feeder import cac_auc_rollforward
    requested={x.get('series_id') for key in ('obs_exposures','lending_products','deposit_products') for p in a.get(key) or [] for st in p.get('fee_streams') or [] for x in ((st.get('cost') or {}).get('params') or {}).get('linked_sources',[])}
    if not requested:return {}
    out={};cache={};width=12//ppy
    for x in catalog(a):
        if x['series_id'] not in requested:continue
        name=x['feed']
        if name not in cache:cache[name]=cac_auc_rollforward(a['cac_feeds'][name],n,ppy,assumptions=a,growth_context=growth_context)['monthly']
        rows=cache[name]
        vals=[float(r['total_spend'] if 'channel' not in x else r['channels'][x['channel']]['spend']) for r in rows]
        out[x['series_id']]=[sum(vals[i:i+width]) for i in range(0,n*width,width)]
    missing=requested-set(out)
    if missing:raise ValueError('Missing acquisition spend source: '+', '.join(sorted(missing)))
    return out

def validate_links(items):
    if not isinstance(items,list) or not items:raise ValueError('Linked product cost requires at least one spend source')
    seen=set()
    for x in items:
        sid=x.get('series_id')
        if not isinstance(sid,str) or not sid or sid in seen:raise ValueError('Linked spend sources must be present and unique')
        seen.add(sid)
        share=float(x.get('share',1))
        if not math.isfinite(share) or not 0<=share<=1:raise ValueError('Spend allocation must be between 0 and 100%')

def value(items,sources,q):
    validate_links(items)
    total=0.
    for x in items:
        sid=x['series_id']
        if sid not in sources:raise ValueError('Missing acquisition spend source: '+sid)
        total+=sources[sid][q-1]*float(x.get('share',1))
    return total

def validate(a):
    links=[]
    for key in ('obs_exposures','lending_products','deposit_products'):
        for p in a.get(key) or []:
            for st in p.get('fee_streams') or []:
                items=((st.get('cost') or {}).get('params') or {}).get('linked_sources')
                if items is not None:
                    validate_links(items);links.extend(items)
    if not links:return
    sources={x['series_id']:x for x in catalog(a)}
    for x in links:
        if x['series_id'] not in sources:raise ValueError('Missing acquisition spend source: '+x['series_id'])
    # A feed total includes its channels. Reject overlapping bases within a stream.
    for key in ('obs_exposures','lending_products','deposit_products'):
        for p in a.get(key) or []:
            for st in p.get('fee_streams') or []:
                rows=[sources[x['series_id']] for x in ((st.get('cost') or {}).get('params') or {}).get('linked_sources',[])]
                totals={x['feed'] for x in rows if 'channel' not in x}
                if any(x['feed'] in totals for x in rows if 'channel' in x):raise ValueError('Choose a feed total or its individual channels, not both in the same cost')
