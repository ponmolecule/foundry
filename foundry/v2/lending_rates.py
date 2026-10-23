"""Fixed lending yield paths. Annualized rate levels, with period overrides applied last."""
from math import isfinite
from .series import normalize_series_spec, resolve_entered_series

def prepare_fixed_yields(products, n, ppy, context=None):
    for p in products:
        if p.get('rate_type')=='float' or p.get('yield_ann_spec') is None:
            continue
        s=normalize_series_spec(p['yield_ann_spec'])
        if s.get('trajectory')=='explicit' and not s.get('values'):
            raise ValueError('Fixed lending yield schedule has no values')
        if s['source']!='entered':raise ValueError('Fixed lending yield must be an entered Flat/Growth/Explicit path')
        values=[float(v) for v in resolve_entered_series(s,n,ppy,context=context,default_value=0)]
        if any(not isfinite(v) or v<0 or v>.6 for v in values):
            raise ValueError('Fixed lending yield must resolve between 0% and 60%')
        p['_yield_ann_path']=values


def prepare_fixed_deposit_rates(products, n, ppy, context=None):
    """Resolve deposit annual rate levels with the existing entered-Series mechanics."""
    for p in products:
        if p.get('rate_type') == 'float' or p.get('rate_paid_ann_spec') is None:
            continue
        spec = normalize_series_spec(p['rate_paid_ann_spec'])
        if spec['source'] != 'entered':
            raise ValueError('Fixed deposit rate must be an entered Flat/Growth/Explicit path')
        if spec.get('trajectory') == 'explicit' and not spec.get('values'):
            raise ValueError('Fixed deposit rate schedule has no values')
        values = [float(v) for v in resolve_entered_series(spec, n, ppy, context=context, default_value=0)]
        if any(not isfinite(v) or v < 0 or v > .30 for v in values):
            raise ValueError('Fixed deposit rate must resolve between 0% and 30%')
        p['_rate_paid_ann_path'] = values
