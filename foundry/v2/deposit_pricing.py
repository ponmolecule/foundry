"""Optional monetary minimum for deposit interest expense, separate from rate floors."""
from math import isfinite
from .series import normalize_series_spec, resolve_entered_series


def minimum_interest_path(product, n, ppy, growth_context=None):
    raw = product.get('minimum_interest_expense')
    if raw is None:
        return None
    if not isinstance(raw, dict) or not isinstance(raw.get('amount_spec'), dict):
        raise ValueError('minimum interest expense requires an amount Series')
    period = raw.get('period')
    if period not in {'month', 'quarter', 'year'}:
        raise ValueError('minimum interest expense requires Month, Quarter or Year amount period')
    s = normalize_series_spec(raw['amount_spec'])
    if s['source'] != 'entered':
        raise ValueError('minimum interest expense must use an entered amount Series')
    values = resolve_entered_series(s, n, ppy, context=growth_context)
    if len(values) != n or any(not isfinite(float(v)) or float(v) < 0 for v in values):
        raise ValueError('minimum interest expense amounts must be finite and nonnegative with complete coverage')
    return [float(v) * {'month':12, 'quarter':4, 'year':1}[period] / ppy for v in values]


def apply_minimum(calculated, minimum, index):
    return calculated if minimum is None else max(calculated, minimum[index])
