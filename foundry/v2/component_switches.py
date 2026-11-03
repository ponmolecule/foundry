"""Whole-horizon inclusion. Authored inputs are immutable; execution uses zero nodes.

scenario_enabled is deliberately distinct from existing module activation flags.
Identity survives exclusion so linked quantity consumers see zero, never a deleted source.
"""
import copy

PRODUCTS = ('lending_products', 'deposit_products', 'obs_exposures')
IDENTITY = ('inclusion_id', 'product_id', 'source_catalog_id', 'quantity_series_id',
            'series_id', 'compensation_series_id', 'expense_series_id', 'customer_count_series_id', 'derived_series_ids', 'activity_series_ids', 'name', 'role', 'call_report_line')


def inventory(cfg):
    a = cfg.get('assumptions') or {}; rows = []
    def add(node, kind, path, parent=None):
        if not isinstance(node, dict):
            raise ValueError('Component must be an object: ' + path)
        sid = str(node.get('inclusion_id') or node.get('product_id') or
                  node.get('quantity_series_id') or node.get('series_id') or path)
        row = dict(id=sid, name=node.get('name') or node.get('role') or path,
                   kind=kind, path=path, parent=parent, node=node)
        rows.append(row); return sid
    for key in PRODUCTS:
        for i, p in enumerate(a.get(key) or []):
            pid = add(p, key, f'{key}.{i}')
            for j, s in enumerate(p.get('fee_streams') or []):
                add(s, 'stream', f'{key}.{i}.fee_streams.{j}', pid)
    for key, feed in (a.get('cac_feeds') or {}).items():
        fid = add(feed, 'feed', 'cac_feeds.' + key)
        for i, ch in enumerate(feed.get('channels') or []):
            add(ch, 'channel', f'cac_feeds.{key}.channels.{i}', fid)
    for key, kind, vals in (
        ('nie_detail.workforce.roles', 'role', ((a.get('nie_detail') or {}).get('workforce') or {}).get('roles') or []),
        ('cost_pools', 'cost_pool', a.get('cost_pools') or []),
        ('nie_detail.categories', 'expense', (a.get('nie_detail') or {}).get('categories') or [])):
        for i, node in (vals.items() if isinstance(vals,dict) else enumerate(vals)): add(node, kind, f'{key}.{i}')
    return rows


def states(cfg):
    rows = inventory(cfg); ids = [r['id'] for r in rows]
    if len(ids) != len(set(ids)): raise ValueError('Component inclusion IDs must be unique')
    groups = (cfg.get('assumptions') or {}).get('component_groups') or []
    group_ids = [str(g.get('id') or '') for g in groups]
    if any(not x for x in group_ids) or len(group_ids) != len(set(group_ids)):
        raise ValueError('Component groups require unique IDs')
    if set(ids) & set(group_ids): raise ValueError('Group and component IDs must be distinct')
    nodes = {r['id']: r for r in rows}
    for g in groups:
        nodes[g['id']] = dict(id=g['id'], name=g.get('name') or g['id'], kind='group',
                              node=g, parent=None, path='component_groups.'+g['id'])
    dependencies = {sid: [] for sid in nodes}
    for sid, r in nodes.items():
        n = r['node']
        if 'scenario_enabled' in n and type(n['scenario_enabled']) is not bool:
            raise ValueError('scenario_enabled must be a boolean: ' + sid)
        for dep in (r.get('parent'), n.get('owner_component_id')):
            if dep:
                if dep not in nodes: raise ValueError('Unknown component owner: ' + str(dep))
                dependencies[sid].append(dep)
        if r['kind'] == 'group':
            for member in n.get('members') or []:
                if member not in nodes: raise ValueError('Unknown group member: ' + str(member))
                dependencies[member].append(sid)
    done = {}; visiting = set()
    def resolve(sid):
        if sid in done: return done[sid]
        if sid in visiting: raise ValueError('Component ownership/group cycle: ' + sid)
        visiting.add(sid)
        parents = [(d, resolve(d)) for d in dependencies[sid]]
        active = nodes[sid]['node'].get('scenario_enabled', True) and all(v for _, v in parents)
        nodes[sid]['effective'] = bool(active)
        nodes[sid]['blocked_by'] = [d for d, v in parents if not v]
        visiting.remove(sid); done[sid] = bool(active); return bool(active)
    for sid in nodes: resolve(sid)
    return list(nodes.values())


def _identity(node):
    return {k: copy.deepcopy(node[k]) for k in IDENTITY if k in node}


def _zero_stream(s):
    # A canonical zero quantity retains unit/basis and stable identity, without evaluating inputs.
    z = _identity(s)
    from .income_modules import fee_quantity_kind
    z['_scenario_quantity_kind'] = fee_quantity_kind(s)
    z.update(basis=s.get('basis') if s.get('basis') in {'balance','transaction','account','flat','event'} else 'flat',
             driver={'source':'constant','trajectory':'flat','params':{'value':0}},
             rate={'behavior':'flat','kind':'flat','value':0}, cost={'kind':'none'},
             _scenario_off=True)
    return z


def prepare(cfg):
    """Return the original object for all-On; private neutral execution copy otherwise."""
    if cfg.get('_component_switches_prepared'): return cfg
    rows = states(cfg)
    if all(r['effective'] for r in rows): return cfg
    out = copy.deepcopy(cfg); a = out['assumptions']; bypath = {r['path']:r for r in rows}
    # Only assumption-link resolution may read this immutable saved input registry.
    a['_saved_deposit_assumptions'] = copy.deepcopy(a.get('deposit_products') or [])
    for key in PRODUCTS:
        for i, p in enumerate(a.get(key) or []):
            state = bypath[f'{key}.{i}']; streams = p.get('fee_streams') or []
            if not state['effective']:
                z = _identity(p)
                z.update(opening_balance=0., notional=0., growth_per_period=0.,
                         runoff_per_period=0., new_deposits_per_period=0., originations_per_period=0.,
                         origination_q=0., rate_type='fixed', rate_paid_ann=0., yield_ann=0.,
                         charge_off_ann=0., provision_rate_ann=0., reserve_rate_pct_bal=0.,
                         measurement='amortized_cost', risk_weight=p.get('risk_weight',1.),
                         _scenario_off=True, fee_streams=[_zero_stream(s) for s in streams])
                if key=='deposit_products' and p.get('balance_mode')=='pool':
                    for field in ('balance_mode','retention_pool_id','pool_share_spec'):z[field]=copy.deepcopy(p.get(field))
                p.clear(); p.update(z)
            else:
                p['fee_streams'] = [s if bypath[f'{key}.{i}.fee_streams.{j}']['effective']
                                    else _zero_stream(s) for j,s in enumerate(streams)]
    for key, feed in (a.get('cac_feeds') or {}).items():
        if not bypath['cac_feeds.'+key]['effective']:
            for k in ('opening_customers','opening_auc','beginning_customers','beginning_auc'): feed[k] = 0.
            feed['driver_specs']={'attrition_rate':{'source':'entered','trajectory':'flat','value':0,'period':'month'}}
            if feed.get('population_composition'):
                for band in feed['population_composition'].get('bands') or []:band['opening']=0.
            feed['_scenario_off'] = True
        for i,ch in enumerate(feed.get('channels') or []):
            if not bypath[f'cac_feeds.{key}.channels.{i}']['effective']:
                z = _identity(ch); z.update(method='explicit', params={'new_customers_by_year':[0]},
                                            avg_auc_per_customer=0., _scenario_off=True)
                ch.clear(); ch.update(z)
    for r in rows:
        if r['kind'] not in {'role','cost_pool','expense'} or r['effective']: continue
        parts=r['path'].split('.'); target=a
        for k in parts[:-1]: target=target[int(k)] if isinstance(target,list) else target[k]
        last=int(parts[-1]) if isinstance(target,list) else parts[-1]
        old=target[last];z=_identity(old);z['_scenario_off']=True
        if r['kind']=='role': z.update(count=0.,annual_comp=0.)
        elif r['kind']=='cost_pool': z['components']=[]
        else:z.update(flow_spec={'source':'entered','trajectory':'flat','value':0,'period':'month'},amount=0.)
        target[last]=z
    out['_component_switches_prepared']=True
    return out


def disclosure(cfg):
    rows=states(cfg); excluded=[r for r in rows if not r['effective']]
    if not excluded:return None
    aliases={}
    for r in rows:
        for k in IDENTITY:
            if r['node'].get(k):
                if isinstance(r['node'][k],dict):
                    for value in r['node'][k].values():aliases[str(value)]=r
                else:aliases[str(r['node'][k])]=r
    warnings=[]
    def scan(obj, consumer, path=''):
        if isinstance(obj,dict):
            # This is an assumption link, not a modeled quantity dependency.
            if obj.get('source')=='deposit_customer_amount':return
            for k,v in obj.items():
                if k in {'owner_component_id','members','inclusion_id'}:continue
                if isinstance(v,str) and k in {'ref','series_id','source_id','managed_notional_source_id'}:
                    source=aliases.get(v)
                    if source and not source['effective'] and source['id']!=consumer['id']:
                        warnings.append(dict(consumer=consumer['name'],source=source['name'],
                                             source_id=source['id'],message='Enabled consumer receives zero from excluded source'))
                else:scan(v,consumer,path+'.'+k)
        elif isinstance(obj,list):
            for v in obj:scan(v,consumer,path)
    for r in rows:
        if r['effective']:scan({k:v for k,v in r['node'].items() if k not in {'fee_streams','channels'}},r)
    return dict(baseline='r458',semantics='Excluded over the entire forecast; never existed',
                excluded=[{k:r[k] for k in ('id','name','kind','blocked_by')} for r in excluded],
                warnings=list({(w['consumer'],w['source_id']):w for w in warnings}.values()),
                shared=[dict(id=r['id'],name=r['name'],kind=r['kind'],ownership='Shared / unowned; remains active')
                        for r in rows if r['kind'] in {'role','cost_pool','expense'} and r['effective']
                        and not r['node'].get('owner_component_id')])


def all_on(cfg):
    out=copy.deepcopy(cfg)
    for r in inventory(out):r['node'].pop('scenario_enabled',None)
    for g in (out.get('assumptions') or {}).get('component_groups') or []:g.pop('scenario_enabled',None)
    return out


def comparison(cfg, selected):
    """Exact dollar NI bridge, holding the base funding lines for stage one.

Stage one is selected operating pretax with All-On funding income/expense. Stage
 two restores selected funding. Stage three is the net-income residual, including
 tax and interactions. Every vector is from unrounded engine outputs.
"""
    from .engine_q_a import run_pf_a
    from .engine_q_b import run_pf_b
    engine = run_pf_b if cfg.get('parity_profile')=='pf_b' else run_pf_a
    try:
        base = engine(all_on(cfg), **({'_switch_capture_opening':True} if cfg.get('parity_profile')=='pf_b' else {}))
    except (ValueError,TypeError,KeyError,IndexError) as exc:
        return dict(available=False,reason='All-On comparison unavailable: excluded saved inputs are incomplete or invalid',detail=str(exc)[:300])
    cur = selected
    n = len(cur['is']['ni']); zero=[0.]*n
    def arr(r,k):return [float(v or 0.) for v in r['is'].get(k,zero)]
    def funding(r):
        vals=[arr(r,k) for k in (('intSweep','intCash','intBorrow') if cfg.get('parity_profile')=='pf_b' else ('secInt','cashInt','borrExp'))]
        return [x+y-z for x,y,z in zip(*vals)]
    bf,cf=funding(base),funding(cur)
    funding_delta=[y-x for x,y in zip(bf,cf)]
    pretax_delta=[y-x for x,y in zip(arr(base,'pretax'),arr(cur,'pretax'))]
    direct=[x-y for x,y in zip(pretax_delta,funding_delta)]
    total=[y-x for x,y in zip(arr(base,'ni'),arr(cur,'ni'))]
    residual=[t-d-f for t,d,f in zip(total,direct,funding_delta)]
    cb=cur.get('scenario_opening',{}) if cfg.get('parity_profile')=='pf_b' else {k:(v[0] if v else 0) for k,v in cur['bs'].items()}
    bb=base.get('scenario_opening',{}) if cfg.get('parity_profile')=='pf_b' else {k:(v[0] if v else 0) for k,v in base['bs'].items()}
    opening={k:float(cb.get(k,0))-float(bb.get(k,0)) for k in ('cash','borrow','sec','netLoans','deposits','equity')}
    return dict(units='dollars',order=['Direct removal at base plug','Funding / plug change',
                'Capital/tax and interaction residual'],direct_removal=direct,
                funding_plug_effect=funding_delta,capital_tax_interaction_residual=residual,
                total_net_income_change=total,opening_reconciliation=opening,
                opening_adjustment_label='Scenario opening adjustment',
                baseline='All components On; r458 economics')
