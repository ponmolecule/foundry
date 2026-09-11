"""Canonical natural-period resolver for recurring Configuration flow assumptions.

This module is deliberately narrow.  It exists for recurring dollar flows whose authored
amount has its own Month / Quarter / Year unit (currently Operating Expense in Configuration).
It does *not* own product balance growth/runoff, APR/yield semantics, workforce levels, or
one-time events.

Core invariant:
    economically equivalent inputs such as 360/year, 90/quarter, and 30/month resolve to
    identical modeled dollars.  Computational cadence implements the assumption; it never
    defines the assumption's economic unit.

Smooth/step growth is resolved on a conceptual monthly grid and then summed into the engine
cadence.  This makes annual flow economics invariant between monthly and quarterly engines and
also avoids sampling a smooth curve differently merely because the engine runs at a different
cadence.
"""
from __future__ import annotations

from typing import Any, Mapping

from .growth import growth_multiplier, validate_growth_spec_for_cadence


_PERIOD_FREQ = {"year": 1, "quarter": 4, "month": 12}
_VALID_TRAJECTORIES = {"flat", "growth", "explicit"}
_VALID_BASE_POSITIONS = {"period1", "prior_period"}


def normalize_period(period: Any) -> str:
    p = str(period or "").strip().lower()
    if p not in _PERIOD_FREQ:
        raise ValueError(f"unsupported recurring-flow period {period!r}; expected month/quarter/year")
    return p


def monthly_equivalent(value: float, period: str) -> float:
    """Convert one natural-period recurring amount to an equivalent monthly amount."""
    p = normalize_period(period)
    return float(value or 0.0) * _PERIOD_FREQ[p] / 12.0


def _months_per_engine_period(ppy: int) -> int:
    ppy = int(ppy)
    if ppy not in (4, 12):
        raise ValueError(f"unsupported cadence periods_per_year={ppy}")
    return 12 // ppy


def _aggregate_months(months: list[float], n_periods: int, ppy: int) -> list[float]:
    width = _months_per_engine_period(ppy)
    out = []
    for i in range(int(n_periods)):
        lo = i * width
        out.append(float(sum(months[lo:lo + width])))
    return out


def _explicit_months(values: list[Any], period: str, n_months: int) -> list[float]:
    """Expand natural-period flow totals to months, preserving legacy zero-after-schedule behavior."""
    p = normalize_period(period)
    months_per_source = 12 // _PERIOD_FREQ[p]
    out: list[float] = []
    for raw in list(values or []):
        val = float(raw or 0.0) / float(months_per_source)
        out.extend([val] * months_per_source)
        if len(out) >= int(n_months):
            break
    if len(out) < int(n_months):
        out.extend([0.0] * (int(n_months) - len(out)))
    return out[:int(n_months)]


def validate_periodic_flow_spec(spec: Mapping[str, Any] | None, *, ppy: int = 4,
                                context=None) -> dict:
    """Validate and normalize the opt-in recurring-flow contract."""
    raw = dict(spec or {})
    traj = str(raw.get("trajectory") or "flat").strip().lower()
    if traj not in _VALID_TRAJECTORIES:
        raise ValueError(f"unsupported recurring-flow trajectory {traj!r}")
    period = normalize_period(raw.get("period"))
    base_position = str(raw.get("base_position") or "period1").strip().lower()
    if base_position not in _VALID_BASE_POSITIONS:
        raise ValueError("recurring-flow base_position must be period1 or prior_period")
    out = {"trajectory": traj, "period": period, "base_position": base_position}
    if traj == "explicit":
        if base_position != "period1":
            raise ValueError("recurring-flow base_position=prior_period requires trajectory=growth")
        vals = raw.get("values")
        if vals is None:
            vals = raw.get("schedule")
        if not isinstance(vals, (list, tuple)):
            raise ValueError("explicit recurring-flow values must be a list")
        out["values"] = [float(v or 0.0) for v in vals]
    else:
        out["value"] = float(raw.get("value") or 0.0)
        if traj == "growth":
            gs = raw.get("growth_spec")
            if not gs:
                raise ValueError("growth recurring-flow trajectory requires growth_spec")
            # Validate against the conceptual monthly grid, not the engine cadence.  A monthly
            # step can be represented inside a quarterly flow because the monthly values are
            # summed into the quarter rather than sampled at quarter-end.
            out["growth_spec"] = validate_growth_spec_for_cadence(
                gs, ppy=12, context=context)
        elif base_position != "period1":
            raise ValueError("recurring-flow base_position=prior_period requires trajectory=growth")
    return out


def resolve_periodic_flow(spec: Mapping[str, Any] | None, n_periods: int, ppy: int = 4,
                          *, context=None) -> list[float]:
    """Resolve a natural-period recurring dollar flow to engine-period dollar totals.

    Flat/Growth values are normalized to monthly recurring amounts.  Growth is applied on the
    conceptual monthly grid; engine periods then sum those monthly flows.  Explicit schedules
    are natural-period *totals*: an annual value is distributed evenly through its model year,
    a quarterly value through its model quarter, and monthly values are used directly.
    """
    s = validate_periodic_flow_spec(spec, ppy=ppy, context=context)
    n = int(n_periods)
    ppy = int(ppy)
    width = _months_per_engine_period(ppy)
    n_months = n * width

    if s["trajectory"] == "explicit":
        months = _explicit_months(s["values"], s["period"], n_months)
        return _aggregate_months(months, n, ppy)

    base_month = monthly_equivalent(s["value"], s["period"])
    if s["trajectory"] == "flat":
        months = [base_month] * n_months
    else:
        gs = s["growth_spec"]
        # Some source models author the base amount for the immediately preceding natural
        # growth period (for example, a current-year annual service cost whose first forecast
        # year is escalated once).  Preserve the authored amount and its timing explicitly
        # instead of forcing users to pre-escalate it by hand.  Default behavior remains the
        # historical contract: the base is already the value in model period 1.
        if s.get("base_position") == "prior_period":
            base_month *= (1.0 + float(gs.get("rate") or 0.0))
        months = [base_month * growth_multiplier(
            gs, current_period=m, start_period=1, ppy=12,
            context=context, base_position="period1") for m in range(1, n_months + 1)]
    return _aggregate_months(months, n, ppy)
