"""Fixed lending yield paths. Annualized rate levels, with period overrides applied last."""
from math import isfinite
from .series import normalize_series_spec, resolve_entered_series

def prepare_fixed_yields(products, n, ppy, context=None):
    for p in products:
        if p.get('rate_type')=='float' or p.get('yield_ann_spec') is None:
            continue
        s=normalize_series_spec(p['yield_ann_spec'])
        if s['source']!='entered':raise ValueError('Fixed lending yield must be an entered Flat/Growth/Explicit path')
        values=[float(v) for v in resolve_entered_series(s,n,ppy,context=context,default_value=0)]
        if any(not isfinite(v) or v<0 or v>.6 for v in values):
            raise ValueError('Fixed lending yield must resolve between 0% and 60%')
        p['_yield_ann_path']=values
