"""Opt-in reserve liability for undrawn lending commitments (not funded ALLL)."""
from math import isfinite
from .series import resolve_entered_series


def prepare(product, n, ppy, growth_context=None):
    if ppy not in (4,12) or not isinstance(n,int) or n<1: raise ValueError('Unused commitment reserve requires monthly or quarterly cadence')
    spec = product.get('unused_commitment_reserve')
    if spec is None:
        return None
    if not isinstance(spec, dict):
        raise ValueError('Unused commitment reserve must be an object')
    if product.get('measurement') == 'fair_value':
        raise ValueError('Unused commitment reserve requires amortized-cost lending')
    if product.get('mortgage_banking') or product.get('originate_to_sell'):
        raise ValueError('Unused commitment reserve does not support originate-to-sell lending')
    def share(key, positive=False):
        s = spec.get(key)
        if not isinstance(s, dict) or s.get('source', 'entered') != 'entered' or s.get('unit', 'share') != 'share':
            raise ValueError('Unused commitment '+key+' requires an entered share Series')
        months=n*12//ppy
        vs = [float(v) for v in resolve_entered_series(s, months, 12, context=growth_context)]
        if len(vs) != months or any(not isfinite(v) or v > 1 or v < 0 or (positive and v == 0) for v in vs):
            raise ValueError('Unused commitment '+key+' must be '+('(0, 100%]' if positive else '[0, 100%]'))
        return vs if ppy==12 else vs[2::3]
    opening = spec.get('opening_reserve', 0)
    if isinstance(opening, bool) or not isinstance(opening, (int, float)) or not isfinite(opening) or opening < 0:
        raise ValueError('Unused commitment opening reserve must be finite and nonnegative')
    return {'utilization': share('utilization_spec', True),
            'loss_rate': share('lifetime_loss_rate_spec'), 'opening': float(opening)}


def resolve(product, n, ppy, growth_context=None):
    p = prepare(product, n, ppy, growth_context)
    if p is None:
        return None
    multiplier = float(product.get('_unused_reserve_mult', 1))
    if not isfinite(multiplier) or multiplier < 0: raise ValueError('Unused commitment reserve multiplier must be finite and nonnegative')
    balances = product['_bal'][1:]
    total, unused, reserve, provision = [], [], [], []
    prior = p['opening']
    for balance, utilization, rate in zip(balances, p['utilization'], p['loss_rate']):
        commitment = balance / utilization
        undrawn = commitment - balance
        target = undrawn * rate * multiplier
        if not all(isfinite(v) and v >= 0 for v in (commitment, undrawn, target)):
            raise ValueError('Unused commitment calculation must be finite and nonnegative')
        total.append(commitment); unused.append(undrawn); reserve.append(target)
        provision.append(target-prior); prior = target
    return {'totalCommitment': total, 'unusedCommitment': unused,
            'unusedCommitmentReserve': [p['opening']]+reserve,
            'unusedCommitmentProvision': provision}
