"""Shared, explicit flow-to-stock day conversion. Inputs are native-period flows."""
import math


def days_multiplier(multiplier, days, year_days, ppy):
    basis = float(year_days)
    if not math.isfinite(basis) or basis <= 0:
        raise ValueError('Days per year must be finite and positive')
    if len(multiplier) != len(days):
        raise ValueError('Days outstanding and multiplier horizons must match')
    if any(not math.isfinite(float(x)) or float(x) < 0 for x in days):
        raise ValueError('Days outstanding must be finite and non-negative')
    return [float(m) * float(d) / (basis / ppy) for m, d in zip(multiplier, days)]
