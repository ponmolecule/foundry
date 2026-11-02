"""Monthly per-customer amounts from a selected acquisition population, shared by loans and deposits."""
import math

def population_amount(driver, spec, a, months, growth_context=None):
    from .cac_feeder import cac_auc_rollforward
    from .shared_assumptions import SharedAssumptions, DIMENSIONLESS
    from .balance_measures import monthly_balance_measure_series
    d = driver
    if d.get('source', 'customer_acquisition_count') != 'customer_acquisition_count':
        raise ValueError('Active population weights require the whole Customer Acquisition feed count')
    hits = [f for f in (a.get('cac_feeds') or {}).values()
            if f.get('customer_count_series_id') == d.get('series_id')]
    if len(hits) != 1 or not hits[0].get('population_composition'):
        raise ValueError('Active population weights require a feed with population composition; select its total customer count')
    feed = hits[0]
    rows = spec.get('components') or []
    ids = [r.get('id') for r in rows]
    if not ids or any(not x for x in ids) or len(ids) != len(set(ids)):
        raise ValueError('Population-weighted components require unique stable IDs')
    if spec.get('unit', 'money_per_unit') != 'money_per_unit':
        raise ValueError('Population-weighted amount unit must be money_per_unit')
    band_ids = {b['id'] for b in feed['population_composition']['bands']}
    mapped = [r.get('population_band_id') for r in rows]
    if len(mapped) != len(band_ids) or set(mapped) != band_ids:
        raise ValueError('Active population weights require every acquisition band exactly once')
    measure = d.get('measure', 'period_end')
    if measure not in {'period_end', 'period_average'}:
        raise ValueError('Unsupported active population count measure')
    roll = cac_auc_rollforward(feed, months, 12, assumptions=a, growth_context=growth_context)
    bands = roll['population_composition']['bands']
    counts = {bid: (list(bands[bid]['customer_end_by_month']) if measure == 'period_end' else
              monthly_balance_measure_series(bands[bid]['opening'], bands[bid]['customer_end_by_month'], 'period_average'))
              for bid in band_ids}
    totals = [sum(v[m] for v in counts.values()) for m in range(months)]
    result = [0.] * months
    detail = []
    for row in rows:
        bid = row['population_band_id']
        amount = SharedAssumptions(a, months, 12, growth_context).evaluate(row.get('amount_spec') or {}, 'money_per_unit')
        weight = [counts[bid][m] / totals[m] if totals[m] else 0. for m in range(months)]
        weighted = [v * w for v, w in zip(amount, weight)]
        result = [x + y for x, y in zip(result, weighted)]
        detail.append(dict(component_id=row.get('id'), name=row.get('name') or bands[bid]['name'],
                           unit='money_per_unit', amount=amount, weight=weight, weighted_amount=weighted,
                           weight_source='active_population', population_band_id=bid, count=counts[bid]))
    for factor in spec.get('factors') or []:
        unit = factor.get('unit', 'scalar')
        if unit not in DIMENSIONLESS:
            raise ValueError('Assumption factors must be dimensionless')
        values = SharedAssumptions(a, months, 12, growth_context).evaluate(factor, unit)
        result = [x * y for x, y in zip(result, values)]
        detail.append(dict(name=factor.get('name') or 'Factor', unit=unit, values=values))
    detail.append(dict(name='Resolved amount per customer', unit='money_per_unit', values=list(result)))
    if any(not math.isfinite(v) or v < 0 for v in result):
        raise ValueError('Population-weighted amount must be finite and nonnegative')
    return result, detail

