"""Shared cost-recovery pricing terms for revenue and expense consumers.

A cost pool resolves an eligible native-period dollar flow.  A downstream consumer then
applies a recovery share and a dimensionless markup level.  The same pricing mechanic can
therefore post either fee revenue or Operating Expense without changing the pool economics.
"""
from __future__ import annotations

from typing import Any, Mapping

_VALID_PERIODS = {"month", "quarter", "year"}
_VALID_TRAJECTORIES = {"flat", "growth", "explicit_schedule"}


def _schedule_value(schedule: Mapping[str, Any] | None, idx: int, default: float) -> float:
    cur = float(default or 0.0)
    points = []
    for k, v in (schedule or {}).items():
        try:
            points.append((int(k), float(v)))
        except (TypeError, ValueError):
            continue
    for k, v in sorted(points):
        if k > int(idx):
            break
        cur = v
    return cur


def _level_schedule_value(spec: Mapping[str, Any], q: int, ppy: int, default: float = 0.0) -> float:
    """Resolve explicit natural-period EOP markup levels to an engine-period average.

    This intentionally matches the Fee Product level-path contract: step/smooth schedules are
    first resolved on a conceptual monthly grid, then averaged into the presentation period.
    """
    s = dict(spec or {})
    period = str(s.get("period") or "").strip().lower()
    if period not in _VALID_PERIODS:
        raise ValueError(f"unsupported cost_recovery markup period: {s.get('period')!r}")
    resolution = str(s.get("resolution") or "step").strip().lower()
    if resolution not in {"step", "smooth"}:
        raise ValueError(f"unsupported cost_recovery markup resolution: {s.get('resolution')!r}")
    schedule = s.get("schedule") or {}
    if not isinstance(schedule, dict) or not schedule:
        raise ValueError("cost_recovery explicit markup requires at least one schedule value")

    ppy = int(ppy)
    if ppy not in (1, 4, 12):
        raise ValueError(f"unsupported cadence periods_per_year={ppy}")
    width_months = {"year": 12, "quarter": 3, "month": 1}[period]
    engine_width_months = 12 // ppy

    def _month_level(month_index: int) -> float:
        idx = (int(month_index) - 1) // width_months + 1
        cur = _schedule_value(schedule, idx, default)
        if idx <= 1:
            return cur
        prev = _schedule_value(schedule, idx - 1, default)
        pos = (int(month_index) - 1) % width_months + 1
        if resolution == "step":
            return cur if pos == width_months else prev
        frac = pos / float(width_months)
        return prev + (cur - prev) * frac

    first_month = (int(q) - 1) * engine_width_months + 1
    vals = [_month_level(first_month + j) for j in range(engine_width_months)]
    return sum(vals) / float(len(vals))


def validate_cost_recovery_terms(params: Mapping[str, Any] | None) -> dict:
    """Validate and normalize recovery + markup terms without changing their stored shape."""
    p = dict(params or {})
    try:
        recovery = float(p.get("recovery_pct") or 0.0)
    except (TypeError, ValueError):
        raise ValueError("cost_recovery requires numeric recovery_pct")
    if recovery < 0.0 or recovery > 1.0:
        raise ValueError("cost_recovery recovery_pct must be between 0 and 1")

    try:
        scalar_markup = float(p.get("markup_pct") or 0.0)
    except (TypeError, ValueError):
        raise ValueError("cost_recovery markup_pct must be numeric")
    if scalar_markup < -1.0:
        raise ValueError("cost_recovery markup_pct must be >= -1")

    mp = p.get("markup")
    if mp is not None:
        mp = dict(mp or {})
        traj = str(mp.get("trajectory") or "flat").strip().lower()
        if traj not in _VALID_TRAJECTORIES:
            raise ValueError(f"unsupported cost_recovery markup trajectory: {traj!r}")
        try:
            mval = float(mp.get("value") or 0.0)
        except (TypeError, ValueError):
            raise ValueError("cost_recovery markup value must be numeric")
        if mval < -1.0:
            raise ValueError("cost_recovery markup value must be >= -1")
        if traj == "growth" and not mp.get("growth_spec"):
            raise ValueError("cost_recovery markup growth trajectory requires growth_spec")
        if traj == "explicit_schedule":
            if str(mp.get("period") or "").strip().lower() not in _VALID_PERIODS:
                raise ValueError(f"unsupported cost_recovery markup period: {mp.get('period')!r}")
            if str(mp.get("resolution") or "step").strip().lower() not in {"step", "smooth"}:
                raise ValueError(f"unsupported cost_recovery markup resolution: {mp.get('resolution')!r}")
            sched = mp.get("schedule")
            if not isinstance(sched, dict) or not sched:
                raise ValueError("cost_recovery explicit markup requires at least one schedule value")
            try:
                vals = [float(v) for v in sched.values()]
            except (TypeError, ValueError):
                raise ValueError("cost_recovery markup schedule values must be numeric")
            if any(v < -1.0 for v in vals):
                raise ValueError("cost_recovery markup schedule values must be >= -1")
    return p


def cost_recovery_markup_value(params: Mapping[str, Any] | None, q: int, ppy: int,
                               *, growth_context=None) -> float:
    """Resolve the dimensionless markup level for one engine period."""
    p = validate_cost_recovery_terms(params)
    if p.get("markup") is None:
        return float(p.get("markup_pct") or 0.0)
    mp = dict(p.get("markup") or {})
    traj = str(mp.get("trajectory") or "flat").strip().lower()
    val = float(mp.get("value") or 0.0)
    if traj == "growth":
        from .growth import growth_multiplier
        val *= growth_multiplier(mp.get("growth_spec"), current_period=int(q), start_period=1,
                                 ppy=int(ppy), context=growth_context,
                                 base_position="period1")
    elif traj == "explicit_schedule":
        val = _level_schedule_value(mp, int(q), int(ppy), val)
    return float(val)


def cost_recovery_amount(cost_flow: float, recovery_pct: float, markup: float) -> float:
    """Apply recovery share and markup to one native-period eligible-cost flow."""
    recovery = float(recovery_pct or 0.0)
    markup = float(markup or 0.0)
    if recovery < 0.0 or recovery > 1.0:
        raise ValueError("cost_recovery recovery_pct must be between 0 and 1")
    if markup < -1.0:
        raise ValueError("cost_recovery markup must be >= -1")
    return float(cost_flow or 0.0) * recovery * (1.0 + markup)
