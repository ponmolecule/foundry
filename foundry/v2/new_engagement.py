"""Neutral funding defaults for newly supplied templates, never saved engagements."""
import copy
FUNDING_DEFAULT_KEYS = ('cash_target_pct_deposits','cash_yield','borrow_rate_ann','securities_yield')
def neutral_template(cfg):
    out = copy.deepcopy(cfg)
    a = out.setdefault('assumptions', {})
    for key in FUNDING_DEFAULT_KEYS:
        a[key] = 0.0
    if isinstance(a.get('nie_detail'), dict):
        a['nie_detail']['fdic_bp_ann'] = 0.0
    return out
