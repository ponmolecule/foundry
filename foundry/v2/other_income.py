"""Opt-in entity-level income flows; no product, asset or investment is manufactured."""
import math
from .series import resolve_entered_series

PERIODS = {'month': 12, 'quarter': 4, 'year': 1, 'model_period': None}

def validate(a):
    model = a.get('other_income_model')
    if model is None: return
    if not isinstance(model, dict): raise ValueError('Other income must be an object')
    lines = model.get('lines', [])
    if not isinstance(lines, list): raise ValueError('Other income lines must be a list')
    ids = set()
    for line in lines:
        if not isinstance(line, dict): raise ValueError('Each Other income line must be an object')
        if line.get('classification', 'other') not in {'other','dividend'}: raise ValueError('Unsupported Other income classification')
        sid = line.get('id')
        if not isinstance(sid, str) or not sid or sid in ids: raise ValueError('Other income requires unique stable line IDs')
        ids.add(sid)
        source = line.get('source', 'entered')
        if source not in {'entered', 'linked_quantity'}: raise ValueError('Unsupported Other income source')
        if source == 'entered':
            spec = line.get('amount_spec') or {}
            if not isinstance(spec, dict): raise ValueError('Other income amount must be a Series object')
            if spec.get('source', 'entered') != 'entered': raise ValueError('Other income amount must be entered; use Linked quantity for a source link')
            if spec.get('period', 'model_period') not in PERIODS: raise ValueError('Unsupported Other income amount period')
        else:
            from .source_catalog import catalog
            meta = {x['series_id']: x for x in catalog(a)}.get(line.get('source_series_id'))
            if not meta or meta.get('driver') != 'fee_stream_quantity' or meta.get('unit') != 'money_flow' or meta.get('collection') != 'obs_exposures':
                raise ValueError('Other income link requires an existing monetary-flow fee quantity')
            factor = line.get('multiplier', 0)
            if isinstance(factor, bool) or not isinstance(factor, (int, float)) or not math.isfinite(factor): raise ValueError('Other income multiplier must be finite')


def prepare(a, quantities, n, ppy, context=None):
    validate(a)
    model = a.get('other_income_model') or {}
    rows = []
    for line in model.get('lines') or []:
        if line.get('source', 'entered') == 'linked_quantity':
            sid = line['source_series_id']
            if sid not in quantities or len(quantities[sid]) != n: raise ValueError('Other income linked quantity is unavailable: '+sid)
            amounts = [float(x) * line.get('multiplier', 0) for x in quantities[sid]]
        else:
            spec = dict(line.get('amount_spec') or {})
            native = {12:'month',4:'quarter'}[ppy]
            if spec.get('cadence', 'model_period') == 'model_period': spec['cadence'] = native
            gs = dict(spec.get('growth_spec') or {})
            if gs.get('period') == 'model_period':
                gs['period'] = native
                spec['growth_spec'] = gs
            # Resolve monthly first, then SUM flows for quarterly models; never sample monthly flows.
            freq = PERIODS[spec.get('period', 'model_period')] or ppy
            monthly = resolve_entered_series(spec, n * 12 // ppy, 12, context=context)
            monthly = [x * freq / 12 for x in monthly]
            width = 12 // ppy
            amounts = [sum(monthly[i:i+width]) for i in range(0, len(monthly), width)]
        if any(not math.isfinite(x) for x in amounts): raise ValueError('Other income amounts must be finite')
        rows.append({'id': line['id'], 'name': line.get('name') or 'Other income',
                     'classification': line.get('classification') or 'other',
                     'source': line.get('source', 'entered'), 'amount': amounts})
    return rows
