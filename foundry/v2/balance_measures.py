"""Canonical balance-measure helpers.

A balance owner publishes period-end observations.  Consumers choose the economically
appropriate measure explicitly instead of reinterpreting the stock ad hoc:

* ``period_end``     — the stock at the end of each canonical month;
* ``period_average`` — (prior month-end + current month-end) / 2 for each canonical month.

When a native model period spans several canonical months, a period-average balance is the
arithmetic mean of the monthly period-average exposures.  This makes an annual-rate flow
calculated as ``native_average * annual_rate / periods_per_year`` exactly equivalent to
summing the underlying monthly accruals when the rate is constant within the native period.
"""
from __future__ import annotations

from typing import Iterable

BALANCE_MEASURES = {"period_end", "period_average"}


def normalize_balance_measure(value, *, default: str = "period_end") -> str:
    measure = str(value or default).strip().lower()
    if measure not in BALANCE_MEASURES:
        raise ValueError("balance measure must be period_end or period_average")
    return measure


def monthly_balance_measure_series(beginning_balance: float, monthly_end: Iterable[float],
                                   measure: str) -> list[float]:
    """Resolve a canonical monthly balance measure from monthly period-end observations."""
    measure = normalize_balance_measure(measure)
    out: list[float] = []
    prev = float(beginning_balance or 0.0)
    for raw in monthly_end:
        eop = float(raw or 0.0)
        out.append(eop if measure == "period_end" else (prev + eop) / 2.0)
        prev = eop
    return out


def native_balance_measure_series(beginning_balance: float, monthly_end: Iterable[float],
                                  n_periods: int, ppy: int, measure: str) -> list[float]:
    """Aggregate a canonical monthly stock path to one balance measure per model period.

    ``period_end`` samples the last month in each native period. ``period_average`` averages
    the constituent monthly period-average exposures.  No intra-period path is manufactured
    from native endpoints.
    """
    ppy = int(ppy)
    n_periods = int(n_periods)
    if ppy not in (1, 4, 12) or 12 % ppy:
        raise ValueError(f"unsupported cadence periods_per_year={ppy} for balance measure")
    width = 12 // ppy
    monthly_end = [float(x or 0.0) for x in monthly_end]
    expected = n_periods * width
    if len(monthly_end) < expected:
        raise ValueError(f"canonical monthly balance path has {len(monthly_end)} months; expected at least {expected}")
    monthly_end = monthly_end[:expected]
    measure = normalize_balance_measure(measure)
    if measure == "period_end":
        return [monthly_end[(i + 1) * width - 1] for i in range(n_periods)]
    monthly_avg = monthly_balance_measure_series(beginning_balance, monthly_end, "period_average")
    return [sum(monthly_avg[i * width:(i + 1) * width]) / float(width)
            for i in range(n_periods)]
