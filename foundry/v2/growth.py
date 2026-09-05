"""Canonical business-growth trajectory resolver.

This module answers one question only: given a proportional business growth assumption,
what multiplier/value applies in each native engine period? It deliberately does NOT own
financial APR/yield conversion, regulatory quarter timing, or product balance mechanics.

The resolver is opt-in. Legacy callers can continue using their existing per-period fields.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import floor
from typing import Any, Mapping


_PERIOD_FREQ = {"year": 1, "quarter": 4, "month": 12}
_VALID_METHODS = {"smooth", "step"}
_VALID_ANCHORS = {"model_period", "model_year", "calendar_year", "fiscal_year", "hire_anniversary"}


@dataclass(frozen=True)
class GrowthContext:
    """Calendar context for calendar/fiscal anchors.

    `start_year/start_month` identify the first native model period's START month. For
    monthly cadence this is the literal opening month; for quarterly cadence it is the
    containing calendar quarter's start month.
    """

    start_year: int = 2026
    start_month: int = 1


def growth_context_from_cfg(cfg: Mapping[str, Any] | None, ppy: int) -> GrowthContext:
    """Build calendar context from Foundry's canonical engagement calendar."""
    if not cfg:
        return GrowthContext()
    from .timebase import model_period_year_month
    y, m = model_period_year_month(cfg, 1, int(ppy))
    return GrowthContext(int(y), int(m))


def _as_context(ctx: GrowthContext | Mapping[str, Any] | None) -> GrowthContext:
    if isinstance(ctx, GrowthContext):
        return ctx
    if isinstance(ctx, Mapping):
        return GrowthContext(int(ctx.get("start_year") or 2026), int(ctx.get("start_month") or 1))
    return GrowthContext()


def normalize_growth_spec(spec: Mapping[str, Any] | None, *, default_period: str = "model_period") -> dict:
    """Return a validated canonical spec; absent spec resolves to zero growth."""
    raw = dict(spec or {})
    rate = float(raw.get("rate") or 0.0)
    if rate <= -1.0:
        raise ValueError("growth_spec.rate must be greater than -1.0")
    period = str(raw.get("period") or default_period).lower()
    if period != "model_period" and period not in _PERIOD_FREQ:
        raise ValueError(f"unsupported growth period {period!r}")
    method = str(raw.get("method") or "smooth").lower()
    if method not in _VALID_METHODS:
        raise ValueError(f"unsupported growth method {method!r}")
    anchor = str(raw.get("anchor") or ("model_period" if period != "year" else "model_year")).lower()
    if anchor not in _VALID_ANCHORS:
        raise ValueError(f"unsupported growth anchor {anchor!r}")
    if method == "step" and anchor in {"model_year", "calendar_year", "fiscal_year", "hire_anniversary"} and period != "year":
        raise ValueError(f"{anchor} anchor requires period='year'")
    anchor_month = int(raw.get("anchor_month") or 1)
    if not 1 <= anchor_month <= 12:
        raise ValueError("growth_spec.anchor_month must be in 1..12")
    return {"rate": rate, "period": period, "method": method,
            "anchor": anchor, "anchor_month": anchor_month}


def validate_growth_spec_for_cadence(spec: Mapping[str, Any] | None, *, ppy: int = 4,
                                     context: GrowthContext | Mapping[str, Any] | None = None,
                                     default_period: str = "model_period") -> dict:
    """Validate a canonical growth spec against the computational cadence.

    Smooth growth can always be compounded across a coarser native cadence. Stepped
    growth cannot invent an intra-period event: a monthly step is therefore invalid in
    a quarterly model, and a fiscal-year boundary in a quarterly model must land on a
    native quarter boundary. This is the shared fail-closed contract used by both the
    resolver and config validation.
    """
    s = normalize_growth_spec(spec, default_period=default_period)
    ppy = int(ppy)
    if ppy not in (1, 4, 12):
        raise ValueError(f"unsupported cadence periods_per_year={ppy}")
    if s["method"] != "step":
        return s

    period = s["period"]
    if period != "model_period" and _PERIOD_FREQ[period] > ppy:
        raise ValueError(f"cannot represent stepped {period} growth inside {ppy}-period/year cadence")

    if s["anchor"] in {"calendar_year", "fiscal_year"} and ppy == 4:
        ctx = _as_context(context)
        boundary_month = 1 if s["anchor"] == "calendar_year" else s["anchor_month"]
        if (boundary_month - ctx.start_month) % 3:
            raise ValueError(
                f"{s['anchor']} boundary month {boundary_month} does not align to the quarterly model cadence")
    return s


def _period_start_year_month(period: int, ppy: int, ctx: GrowthContext) -> tuple[int, int]:
    """Calendar start month of a 1-based native period."""
    if period < 1:
        # Period 0 is the instant immediately before model period 1. Represent it by
        # backing up one native period so opening-stock trajectories can count calendar
        # boundary crossings without pretending period 0 is itself a modeled period.
        months_back = 1 if int(ppy) == 12 else 3
        idx = ctx.start_year * 12 + (ctx.start_month - 1) - months_back
        return idx // 12, idx % 12 + 1
    step_months = 12 // int(ppy)
    if int(ppy) not in (1, 4, 12):
        raise ValueError(f"unsupported cadence periods_per_year={ppy}")
    idx = ctx.start_year * 12 + (ctx.start_month - 1) + (period - 1) * step_months
    return idx // 12, idx % 12 + 1


def _cycle_index(year: int, month: int, anchor_month: int) -> int:
    """Index of the annual cycle containing (year, month), with cycle start anchor_month."""
    return year if month >= anchor_month else year - 1


def _step_count(spec: dict, current_period: int, start_period: int, ppy: int,
                ctx: GrowthContext) -> int:
    if current_period <= start_period:
        return 0
    period = spec["period"]
    anchor = spec["anchor"]

    if period == "model_period":
        return max(0, current_period - start_period)

    freq = _PERIOD_FREQ[period]
    if freq > int(ppy):
        raise ValueError(
            f"cannot represent stepped {period} growth inside {ppy}-period/year cadence")

    # Hire anniversary is explicitly relative to the role/cohort start.
    if anchor == "hire_anniversary":
        if period != "year":
            raise ValueError("hire_anniversary anchor requires period='year'")
        return max(0, (current_period - start_period) // int(ppy))

    # A model-year anchor follows global model-year boundaries, but the base value is
    # understood to be current as of start_period; therefore only boundaries AFTER the
    # start period count (a role hired in M17 first steps at M25, not retroactively at M13).
    if anchor == "model_year":
        if period != "year":
            raise ValueError("model_year anchor requires period='year'")
        cur_idx = (current_period - 1) // int(ppy)
        start_idx = (max(1, start_period) - 1) // int(ppy)
        return max(0, cur_idx - start_idx)

    if anchor in {"calendar_year", "fiscal_year"}:
        if period != "year":
            raise ValueError(f"{anchor} anchor requires period='year'")
        am = 1 if anchor == "calendar_year" else spec["anchor_month"]
        cy, cm = _period_start_year_month(current_period, int(ppy), ctx)
        sy, sm = _period_start_year_month(max(1, start_period), int(ppy), ctx)
        return max(0, _cycle_index(cy, cm, am) - _cycle_index(sy, sm, am))

    # model_period anchor with a named calendar period: boundaries are measured from
    # the assumption's start_period (e.g. quarter steps every 3 months in a monthly model).
    width = int(ppy) // freq
    if width <= 0 or int(ppy) % freq:
        raise ValueError(f"cannot align stepped {period} growth to cadence {ppy}")
    return max(0, (current_period - start_period) // width)


def growth_multiplier(spec: Mapping[str, Any] | None, *, current_period: int,
                      start_period: int = 1, ppy: int = 4,
                      context: GrowthContext | Mapping[str, Any] | None = None,
                      base_position: str = "period1") -> float:
    """Multiplier for a value whose base is current at `start_period`.

    `base_position='period1'` means the base is the value IN start_period (NIE categories,
    fee driver quantities, salaries). `base_position='opening'` means the base is an
    opening stock immediately before period 1 (managed notional day1): smooth growth earns
    one native period by P1 while annual/model-year step growth stays flat until the first
    annual boundary.
    """
    cp, sp, ppy = int(current_period), int(start_period), int(ppy)
    ctx = _as_context(context)
    s = validate_growth_spec_for_cadence(spec, ppy=ppy, context=ctx)
    if cp < sp:
        return 0.0

    if s["method"] == "smooth":
        elapsed = cp - sp
        if base_position == "opening":
            elapsed += 1
        if s["period"] == "model_period":
            native_exp = float(elapsed)
        else:
            source_freq = _PERIOD_FREQ[s["period"]]
            native_exp = float(elapsed) * source_freq / float(ppy)
        return (1.0 + s["rate"]) ** native_exp

    # Step growth counts discrete boundaries. Opening-stock semantics do not create a
    # step in P1; the first model-year step remains P(ppy+1).
    count = _step_count(s, cp, sp, ppy, ctx)
    return (1.0 + s["rate"]) ** count


def resolve_growth_series(base: float, spec: Mapping[str, Any] | None, n_periods: int,
                          ppy: int = 4, *, start_period: int = 1,
                          end_period: int | None = None,
                          context: GrowthContext | Mapping[str, Any] | None = None,
                          base_position: str = "period1") -> list[float]:
    """Materialize an absolute native-cadence series, zero outside the active window."""
    out = []
    n = int(n_periods)
    ep = int(end_period) if end_period not in (None, "") else None
    for p in range(1, n + 1):
        if p < int(start_period) or (ep is not None and p > ep):
            out.append(0.0)
            continue
        out.append(float(base or 0.0) * growth_multiplier(
            spec, current_period=p, start_period=int(start_period), ppy=int(ppy),
            context=context, base_position=base_position))
    return out
