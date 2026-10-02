"""Opt-in deposit levels and shared retention pools. No spreadsheet formulas.

Operands use Enter/Link/Derived; identity is a stable series ID. Deposits remain
liabilities; amounts swept to other institutions are non-posting fee bases.
"""
from math import isfinite
from .series import normalize_series_spec, resolve_entered_series


def _check(values, label, share=False):
    out = [float(v) for v in values]
    if any(not isfinite(v) or v < 0 or (share and v > 1) for v in out):
        raise ValueError(label + (' must be finite shares in [0, 1]' if share else ' must be finite and nonnegative'))
    return out


def source_catalog(a):
    """Only upstream OBS quantities; deposit-owned drivers would create a cycle."""
    from .income_modules import _fee_stream_quantity_kinds
    out = []
    for p in a.get('obs_exposures') or []:
        streams = p.get('fee_streams') or []
        kinds = _fee_stream_quantity_kinds(streams)
        def upstream(i, seen=None):
            seen = set(seen or ())
            if i in seen:
                return False
            seen.add(i)
            driver = streams[i].get('driver') or {}
            source = driver.get('source', 'constant')
            if source == 'stream_ref':
                refs = [j for j, other in enumerate(streams) if other.get('name') == driver.get('ref')]
                return len(refs) == 1 and upstream(refs[0], seen)
            return source in {'constant', 'own_balance', 'managed_notional', 'customer_acquisition_count', 'cost_pool'}
        for i, st in enumerate(streams):
            sid = str(st.get('quantity_series_id') or '').strip()
            if not sid:
                continue
            drv = st.get('driver') or {}
            label = str(p.get('name') or 'Fee product') + ' · ' + str(st.get('name') or 'Stream')
            if kinds[i] == 'money' and st.get('basis') in {'transaction', 'balance'}:
                # bank aggregates / deposit stocks are never upstream operands.
                if upstream(i):
                    out.append(dict(series_id=sid, kind='fee_quantity', label=label, basis=st['basis'], stream=st))
            coef = (drv.get('params') or {}).get('coefficient') or {}
            if coef.get('kind') == 'pct' and coef.get('semantics') == 'share':
                out.append(dict(series_id=sid, kind='fee_share', label=label + ' · share schedule', stream=st))
    for p in a.get('lending_products') or []:
        if p.get('balance_mode') == 'funded_flow_level' and p.get('balance_series_id'):
            fd = p.get('funded_flow_driver') or {}
            # Sources owned by deposit members would point back into their consumer.
            if fd.get('source') == 'entered' or (fd.get('source') == 'fee_stream_quantity' and any(x['series_id'] == fd.get('series_id') and x['kind'] == 'fee_quantity' for x in out)):
                out.append(dict(series_id=p['balance_series_id'], kind='lending_funded_flow', label=str(p.get('name') or 'Lending') + ' · funded flow', basis='transaction', product=p))
    return out


def operand(spec, a, n, ppy, quantities=None, growth_context=None, share=False):
    """Levels and shares never acquire an APR conversion. Flows are typed."""
    s = normalize_series_spec(spec)
    if s['source'] == 'entered':
        return _check(resolve_entered_series(s, n, ppy, context=growth_context), 'Deposit operand', share)
    if s['source'] == 'link':
        lk = s['link']; kind, sid = lk['kind'], lk['series_id']
        matches = [x for x in source_catalog(a) if x['kind'] == kind and x['series_id'] == sid]
        if len(matches) != 1:
            raise ValueError(f'Deposit source {sid!r} is unavailable or ambiguous')
        if share != (kind == 'fee_share'):
            raise ValueError('Deposit links must use compatible monetary / share units')
        if share:
            from .income_modules import _fee_coefficient_value
            c = matches[0]['stream']['driver']['params']['coefficient']
            if c.get('trajectory') == 'explicit_schedule' and {'year':1,'quarter':4,'month':12}.get(c.get('period'),ppy) > ppy:
                raise ValueError('A finer-cadence migration share cannot be applied to aggregated activity; use the source cadence')
            vals = [_fee_coefficient_value(c, q, ppy, {'growth_context': growth_context}) for q in range(1, n + 1)]
        else:
            if matches[0]['basis'] != 'balance':
                raise ValueError('A transaction flow needs Activity × holding days, not a direct balance link')
            vals = (quantities or {}).get(sid) or []
        if len(vals) != n:
            raise ValueError(f'Deposit source {sid!r} has an incomplete horizon')
        return _check(vals, 'Deposit link', share)
    d = s['derived']
    if share or d.get('kind') != 'activity_held':
        raise ValueError('Deposits support only the activity_held derived equation')
    from .income_modules import _fee_entered_flow_value
    src = d.get('activity') or {}
    if src.get('source') == 'entered':
        if src.get('amount_spec') is not None:
            per = src.get('period', 'month')
            if per not in {'year', 'quarter', 'month'}:
                raise ValueError('Deposit activity period must be month, quarter or year')
            amounts = operand(src['amount_spec'], a, n, ppy, quantities, growth_context)
            flow = [v * {'year': 1, 'quarter': 4, 'month': 12}[per] / ppy for v in amounts]
        else:
            fp = src.get('flow_path') or {}
            if fp.get('unit_kind') != 'money_flow':
                raise ValueError('Deposit activity requires monetary flow units')
            flow = [_fee_entered_flow_value(fp, q, ppy, {'growth_context': growth_context}) for q in range(1, n + 1)]
    elif src.get('source') == 'link':
        sid = str((src.get('link') or {}).get('series_id') or '')
        kind = (src.get('link') or {}).get('kind', 'fee_quantity')
        hits = [x for x in source_catalog(a) if x['kind'] == kind and x['series_id'] == sid and x['basis'] == 'transaction']
        if len(hits) != 1:
            raise ValueError('Deposit activity link requires one available upstream monetary transaction Series')
        if kind == 'lending_funded_flow':
            from .loan_balance import resolve_linked_loan_balance
            resolved = resolve_linked_loan_balance(hits[0]['product'], a, {}, n, ppy, fee_stream_quantities=quantities, growth_context=growth_context)
            flow = resolved['funded_volume']
        else:
            flow = (quantities or {}).get(sid) or []
        if len(flow) != n:
            raise ValueError('Deposit activity source has an incomplete horizon')
    else:
        raise ValueError('Deposit activity must be entered or linked')
    days = operand(d.get('holding_days_spec'), a, n, ppy, quantities, growth_context)
    shares = operand(d.get('share_spec', {'value': 1}), a, n, ppy, quantities, growth_context, True)
    basis = float(d.get('day_count', 365))
    if not isfinite(basis) or basis <= 0:
        raise ValueError('Deposit day-count basis must be positive and finite')
    return _check([v * ppy * days[i] / basis * shares[i] for i, v in enumerate(_check(flow, 'Deposit activity'))], 'Derived deposit balance')


def prepare(a, n, ppy, quantities=None, growth_context=None):
    """Resolve independent sources once; bank-state capacity is applied per period."""
    products = a.get('deposit_products') or []
    pools = a.get('deposit_retention_pools') or []
    if sum(x.get('capacity_source') == 'beginning_equity_budget' for x in pools) > 1:
        raise ValueError('Only one pool may own the bank equity budget; use shared members or entered capacities for other pools')
    pool_quantity_ids = {st.get('quantity_series_id') for p in products if p.get('balance_mode') == 'pool' for st in p.get('fee_streams') or [] if st.get('quantity_series_id')}
    if any((p.get('funded_flow_driver') or {}).get('series_id') in pool_quantity_ids for p in a.get('lending_products') or []):
        raise ValueError('Lending cannot use fee quantities owned by a deposit sweep pool; link the upstream activity instead')
    ids = [str(x.get('id') or '') for x in pools]
    if any(not x for x in ids) or len(set(ids)) != len(ids):
        raise ValueError('Deposit pools require distinct stable IDs')
    if any(x.get('capacity_source') == 'beginning_equity_budget' for x in pools) and any(g.get('cap_source') == 'deposit_book_end' for g in a.get('loan_allocation_groups') or []):
        raise ValueError('Equity-budget deposit pools and current deposit-book lending caps form a dependency cycle; use an entered lending capacity')
    r = lambda s, share=False: operand(s, a, n, ppy, quantities, growth_context, share)
    direct = {}
    for i, p in enumerate(products):
        mode = p.get('balance_mode', 'rollforward')
        if mode not in {'rollforward', 'level', 'pool'}:
            raise ValueError('Unsupported deposit balance mode')
        if mode != 'rollforward' and (float(p.get('avg_maturity_m') or 0) != 0 or any(float(p.get(k) or 0) != 0 for k in ('growth_per_period', 'runoff_per_period', 'new_deposits_per_period', 'growth_q', 'runoff_q', 'new_deposits_q'))):
            raise ValueError('Deposit levels cannot also use growth, runoff, inflows or maturity; choose one balance method')
        if p.get('interest_balance_measure', 'period_average') not in {'period_average', 'period_end', 'period_begin'}:
            raise ValueError('Unsupported deposit interest balance measure')
        if mode != 'rollforward' and any((p.get('overrides') or {}).get(k) for k in ('growth_per_period','growth_q','runoff_per_period','runoff_q','new_deposits_per_period','new_deposits_q','avg_maturity_m')):
            raise ValueError('Deposit levels cannot also use balance roll-forward overrides')
        if mode == 'level':
            if not isinstance(p.get('ending_balance_spec'), dict):
                raise ValueError('Deposit level requires an explicit ending balance source')
            direct[i] = r(p.get('ending_balance_spec'))
        if mode == 'pool' and p.get('retention_pool_id') not in ids:
            raise ValueError('Deposit retention pool does not exist')
    prepared = []
    for pool in pools:
        members = [i for i, p in enumerate(products) if p.get('balance_mode') == 'pool' and p.get('retention_pool_id') == pool['id']]
        if not members:
            raise ValueError('Deposit retention pool must have a member')
        weights = {i: r(products[i].get('pool_share_spec', {'value': 1}), True) for i in members}
        if any(abs(sum(w[q] for w in weights.values()) - 1) > 1e-9 for q in range(n)):
            raise ValueError('Deposit pool category shares must sum to 100% in every period')
        if not isinstance(pool.get('balance_spec'), dict):
            raise ValueError('Deposit pool requires a balance source')
        available = r(pool.get('balance_spec'))
        adjustments = []
        for adj in pool.get('adjustments') or []:
            if adj.get('direction') not in {'add', 'deduct'}:
                raise ValueError('Deposit adjustment direction must be add or deduct')
            adjustments.append((adj['direction'], r(adj.get('balance_spec'))))
        net = [sum((1 if direction == 'add' else -1) * vals[q] for direction, vals in adjustments) for q in range(n)]
        shares = r(pool.get('retention_share_spec', {'value': 1}), True)
        fee = r(pool.get('sweep_fee_rate_spec', {'value': 0}))
        # Preserve r231a's period-end basis when the option is absent. New UI pools author average explicitly.
        fee_measure = str(pool.get('sweep_fee_balance_measure') or 'period_end')
        opening_swept = r({'value': pool.get('opening_swept_balance', 0)})[0]
        if fee_measure not in {'period_average', 'period_end'}:
            raise ValueError('Swept-balance fee balance measure must be period_average or period_end')
        cs = pool.get('capacity_source', 'none')
        if cs not in {'none', 'entered', 'beginning_equity_budget'}:
            raise ValueError('Unsupported deposit capacity source')
        if cs == 'entered' and not isinstance(pool.get('capacity_spec'), dict):
            raise ValueError('Entered capacity requires a capacity source')
        capacity = r(pool.get('capacity_spec')) if cs == 'entered' else None
        policy = pool.get('equity_budget') or {}
        budget = None
        if cs == 'beginning_equity_budget':
            budget = {key: r(policy.get(key, {'value': default}), key == 'target_leverage_spec') for key, default in [('target_leverage_spec', 0), ('capital_deduction_spec', 0), ('liquidity_buffer_spec', 0), ('operating_float_months_spec', 0), ('other_committed_assets_spec', 0)]}
            if any(v <= 0 for v in budget['target_leverage_spec']):
                raise ValueError('Equity-budget target leverage must be above zero')
        prepared.append(dict(config=pool, members=members, weights=weights, source=available, adjustments=net, share=shares, fee_rate=fee, capacity=capacity, budget=budget, fee_measure=fee_measure, opening_swept=opening_swept,
                             audit={key: [] for key in ('sourceBalance', 'balanceAdjustments', 'availableBalance', 'shareLimit', 'capacity', 'retainedBalance', 'sweptBalance', 'sweepFee', 'beginningSweptBalance', 'sweepFeeBasis', 'beginningCapital', 'committedAssets', 'bindingLimit')}))
    return direct, prepared


def allocate_period(pool, q, ppy, beginning_equity=0, beginning_credit=0, prior_opex=0):
    k = q - 1
    available = max(0., pool['source'][k] + pool['adjustments'][k])
    limit = available * pool['share'][k]
    capital = committed = 0.
    if pool['budget'] is not None:
        b = pool['budget']
        capital = max(0., beginning_equity - b['capital_deduction_spec'][k])
        committed = beginning_credit + b['liquidity_buffer_spec'][k] + b['other_committed_assets_spec'][k] + prior_opex * ppy / 12 * b['operating_float_months_spec'][k]
        cap = max(0., capital / b['target_leverage_spec'][k] - committed)
    else:
        cap = pool['capacity'][k] if pool['capacity'] is not None else available
    retained = min(available, limit, cap)
    swept = available - retained
    # Opening swept balance is independent of the first ending balance, just like retained deposits.
    prior = pool['audit']['sweptBalance'][-1] if pool['audit']['sweptBalance'] else pool.get('opening_swept', 0.)
    basis = (prior + swept) / 2.0 if pool.get('fee_measure') == 'period_average' else swept
    fee = basis * pool['fee_rate'][k] / ppy
    # 0=available / no sweep, 1=share, 2=capacity, 3=both (audit enum).
    binding = 0 if retained == available else (3 if abs(limit-cap) < 1e-9 else 1 if limit < cap else 2)
    vals = (pool['source'][k], pool['adjustments'][k], available, limit, cap, retained, swept, fee, prior, basis, capital, committed, binding)
    for key, val in zip(pool['audit'], vals):
        pool['audit'][key].append(val)
    return {i: (retained * pool['weights'][i][k], swept * pool['weights'][i][k], fee * pool['weights'][i][k]) for i in pool['members']}
