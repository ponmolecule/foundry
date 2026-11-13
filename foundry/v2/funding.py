"""Explicit funding policy and non-posting liquidity diagnostics (dollars)."""

POLICIES = ('show_shortfall', 'automatic_borrowing', 'contingency_facility')


def facility(assumptions):
    """r503: a committed contingency facility (dollars). Draws fund shortfalls only from ``available_from`` (model
    period) and only up to ``capacity``; any remainder stays unfunded. Drawn balances are priced at ``rate_ann``."""
    f = assumptions.get('contingency_facility') or {}
    cap = float(f.get('capacity') or 0.0)
    frm = int(f.get('available_from') or 1)
    rate = float(f.get('rate_ann') if f.get('rate_ann') is not None else assumptions.get('borrow_rate_ann', 0.0))
    if cap < 0 or frm < 1:
        raise ValueError('contingency_facility needs a non-negative capacity and an availability period from 1')
    return cap, frm, rate


def facility_limit(assumptions, period):
    cap, frm, _ = facility(assumptions)
    return cap if period >= frm else 0.0


def funding_policy(assumptions):
    policy = assumptions.get('funding_shortfall_policy', 'show_shortfall')
    if policy not in POLICIES:
        raise ValueError('funding_shortfall_policy must be show_shortfall, automatic_borrowing or contingency_facility')
    return policy


def funding_diagnostics(policy, cash, required, automatic, scheduled, periods_per_year):
    """Negative cash is an unfunded position, never an implicit overdraft facility.

    Requirements may also be breached while cash is positive.  Keep that distinct
    from the amount needed to get cash back to zero.  Nothing here changes equity,
    investments, authored borrowing or any accounting balance.
    """
    shortfall = [max(0., float(r) - float(c)) for c, r in zip(cash, required)]
    unfunded = [max(0., -float(c)) for c in cash]
    first = next((i for i, v in enumerate(shortfall) if v > .005), None)
    return dict(policy=policy, units="dollars", periods_per_year=periods_per_year,
                includes_opening=True, cash_position=list(cash),
                required_cash=list(required), cash_shortfall=shortfall,
                unfunded_cash=unfunded, automatic_borrowing=list(automatic),
                scheduled_borrowing=list(scheduled), first_shortfall_period=first,
                feasible=first is None, max_cash_shortfall=max(shortfall, default=0.))
