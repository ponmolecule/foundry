"""Opt-in monthly channel allocations, active bands and an associated population.

Acquisition equation links remain pre-allocation inputs. Rounded allocations feed
actual wins and the customer roll-forward; both quantities remain auditable.
"""
import math


def number(x,label):
    try:v=float(x)
    except (ValueError,TypeError):raise ValueError(label+' must be a finite nonnegative number')
    if not math.isfinite(v) or v<0:raise ValueError(label+' must be a finite nonnegative number')
    return v


def validate(feed):
    c=feed.get('population_composition')
    if c is None:return None
    if not isinstance(c,dict) or not isinstance(c.get('bands'),list) or not c.get('bands'):raise ValueError('Population composition requires at least one band')
    if feed.get('intra_period_path')=='straight_line':raise ValueError('Population composition requires Monthly flows, not interpolated customer stocks')
    if c.get('rounding','none') not in {'none','up'}:raise ValueError('Band rounding must be None or Round up')
    ids=[];series=[]
    for b in c['bands']:
        if not isinstance(b,dict) or not str(b.get('id') or '').strip() or not str(b.get('name') or '').strip():raise ValueError('Composition bands require stable IDs and names')
        ids.append(b['id']);series.append(b.get('series_id'))
        number(b.get('opening',0),'Band opening count');number(b.get('units_per_customer',1),'Units per customer')
    series.append(c.get('population_series_id'))
    if len(set(ids))!=len(ids) or any(not isinstance(x,str) or not x.strip() for x in series) or len(set(series))!=len(series) or feed.get('customer_count_series_id') in series:raise ValueError('Composition band and population Series IDs must be present and unique')
    opening=sum(float(b.get('opening',0)) for b in c['bands'])
    if not math.isclose(opening,float(feed.get('beginning_customers') or 0),rel_tol=1e-10,abs_tol=1e-8):raise ValueError('Band opening counts must sum to feed opening customers')
    for ch in feed.get('channels') or []:
        sid=(ch.get('derived_series_ids') or {}).get('new_customers')
        shares=(c.get('channel_shares') or {}).get(sid)
        if not sid or not isinstance(shares,dict) or set(shares)!=set(ids):raise ValueError('Every acquisition channel requires a share for every band')
        values=[number(shares[i],'Band share') for i in ids]
        if any(v>1 for v in values) or not math.isclose(sum(values),1,rel_tol=0,abs_tol=1e-8):raise ValueError('Band shares must total 100% for each channel')
    return c


def allocate(feed,channel_monthly):
    c=validate(feed)
    if c is None:return
    for ch,rows in zip(feed.get('channels') or [],channel_monthly):
        shares=c['channel_shares'][ch['derived_series_ids']['new_customers']]
        for r in rows:
            raw=number(r['new_customers'],'Acquisition equation output');allocated={}
            for b in c['bands']:
                value=raw*float(shares[b['id']])
                if c.get('rounding')=='up' and value>0:
                    nearest=round(value)
                    value=float(nearest if abs(value-nearest)<=2*math.ulp(value) else math.ceil(value))
                allocated[b['id']]=value
            r['equation_new_customers']=raw;r['equation_new_auc']=r['new_auc']
            r['band_additions']=allocated;r['new_customers']=sum(allocated.values()) if c.get('rounding')=='up' else raw
            r['rounding_increment']=r['new_customers']-raw
            r['new_auc']=r['new_customers']*r['avg_auc_per_customer']
            r['cac']=r['spend']/r['new_customers'] if r['new_customers']>0 else None


def count_paths(opening,ends,n,ppy):
    from .balance_measures import monthly_balance_measure_series
    width=12//ppy
    end=list(ends);avg=monthly_balance_measure_series(opening,end,'period_average')
    year=[end[min((i//12+1)*12,len(end))-1] for i in range(len(end))]
    return dict(opening=opening,customer_end_by_month=end,customer_average_by_month=avg,customer_annual_count_by_month=year,
        customer_level_by_period=[sum(end[i*width:(i+1)*width])/width for i in range(n)],
        customer_end_by_period=[end[min((i+1)*width,len(end))-1] for i in range(n)],
        customer_average_by_period=[sum(avg[i*width:(i+1)*width])/width for i in range(n)],
        customer_annual_count_by_period=[year[min(i*width,len(year)-1)] for i in range(n)])


def rollforward(feed,monthly,n,ppy,attr_width):
    c=validate(feed)
    if c is None:return None
    bands={b['id']:dict(name=b['name'],series_id=b['series_id'],units_per_customer=float(b.get('units_per_customer',1)),opening=float(b.get('opening',0)),monthly=[]) for b in c['bands']}
    previous={i:b['opening'] for i,b in bands.items()};source_open=previous.copy()
    for mi,row in enumerate(monthly):
        if mi%attr_width==0:source_open=previous.copy()
        base=sum(source_open.values());loss=float(row['cust_lost']);factor=loss/base if base else 0
        if not base and loss:raise ValueError('Composition attrition has no opening population')
        for ident,b in bands.items():
            adds=sum(ch['band_additions'][ident] for ch in row['channels']);lost=source_open[ident]*factor;end=previous[ident]+adds-lost
            if not math.isfinite(end) or end < -1e-8:raise ValueError('Composition band population must remain finite and nonnegative')
            b['monthly'].append(dict(beginning=previous[ident],additions=adds,lost=lost,ending=end));previous[ident]=end
        if not math.isclose(sum(previous.values()),row['end_cust'],rel_tol=1e-10,abs_tol=1e-7):raise ValueError('Population bands do not reconcile to the feed')
        row['equation_new_cust']=sum(ch['equation_new_customers'] for ch in row['channels'])
        row['rounding_increment']=row['new_cust']-row['equation_new_cust']
    for b in bands.values():b.update(count_paths(b['opening'],[r['ending'] for r in b['monthly']],n,ppy))
    opening=number(sum(b['opening']*b['units_per_customer'] for b in bands.values()),'Associated opening population')
    population=count_paths(opening,[number(sum(b['customer_end_by_month'][m]*b['units_per_customer'] for b in bands.values()),'Associated population') for m in range(len(monthly))],n,ppy)
    population.update(name=c.get('population_name') or 'Associated population',series_id=c['population_series_id'])
    return dict(rounding=c.get('rounding','none'),bands=bands,population=population)


def selected_counts(result,meta):
    if meta.get('band_id'):return result['population_composition']['bands'][meta['band_id']]
    if meta.get('population'):return result['population_composition']['population']
    return result
