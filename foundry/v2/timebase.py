"""Canonical calendar/cadence conversion helpers for Foundry v2.

The engine may compute monthly or quarterly, but contractual/regulatory timing is
expressed in calendar units. These helpers are the ONLY place where calendar
quarters/months are translated to engine-period indices/counts.
"""
from __future__ import annotations

from datetime import date
import calendar
import re


def periods_per_quarter(ppy: int) -> int:
    if ppy not in (4, 12):
        raise ValueError(f"unsupported cadence periods_per_year={ppy}")
    return ppy // 4


def quarter_start_period(quarter: int, ppy: int) -> int:
    """1-based engine period corresponding to the START of 1-based model quarter."""
    q = int(quarter)
    if q < 1:
        raise ValueError("quarter must be >= 1")
    return (q - 1) * periods_per_quarter(ppy) + 1


def quarters_to_periods(quarters: int | float, ppy: int) -> int:
    """Calendar-quarter duration -> engine-period duration."""
    q = float(quarters)
    if q < 0:
        raise ValueError("quarters must be >= 0")
    return int(round(q * periods_per_quarter(ppy)))


def months_to_periods(months: int | float, ppy: int) -> int:
    """Calendar-month duration -> engine-period duration.

    Quarterly cadence necessarily represents month durations at quarter resolution;
    monthly cadence is exact. Round to the nearest engine period, preserving legacy
    quarterly behavior (e.g. 24 months -> 8 quarters).
    """
    m = float(months)
    if m < 0:
        raise ValueError("months must be >= 0")
    return int(round(m * ppy / 12.0))


def period_to_model_quarter(period: int, ppy: int) -> int:
    """1-based engine period -> 1-based model quarter containing it."""
    p = int(period)
    if p < 1:
        raise ValueError("period must be >= 1")
    return (p - 1) // periods_per_quarter(ppy) + 1


def parse_opening_quarter(cfg, default_year: int = 2026, default_quarter: int = 1):
    """Return (year, quarter) for the engagement's target opening.

    Canonical source is charter_profile.target_opening; top-level target_opening is
    accepted as a backward-compatible alias. Supports 'YYYY-Qn', ISO dates, and dicts
    containing year/quarter. Returns a deterministic nominal fallback when absent.
    """
    raw = (cfg.get("charter_profile") or {}).get("target_opening")
    if raw in (None, ""):
        raw = cfg.get("target_opening")
    if isinstance(raw, dict):
        try:
            y, q = int(raw.get("year")), int(raw.get("quarter"))
            if 1 <= q <= 4:
                return y, q
        except Exception:
            pass
    if isinstance(raw, str):
        s = raw.strip()
        m = re.search(r"(\d{4})\s*[-/]?\s*Q([1-4])", s, re.I)
        if m:
            return int(m.group(1)), int(m.group(2))
        try:
            d = date.fromisoformat(s[:10])
            return d.year, (d.month - 1) // 3 + 1
        except Exception:
            pass
    return int(default_year), int(default_quarter)


def model_period_calendar_quarter(cfg, period: int, ppy: int):
    """Return (year, quarter) containing a 1-based engine period."""
    y0, q0 = parse_opening_quarter(cfg)
    mq = period_to_model_quarter(period, ppy)
    off = (q0 - 1) + (mq - 1)
    return y0 + off // 4, off % 4 + 1


def parse_opening_year_month(cfg, default_year: int = 2026, default_month: int = 1):
    """Return the actual opening (year, month) when available.

    ISO dates retain their literal month (e.g. 2027-05-15 -> May 2027). A YYYY-Qn
    value represents the start month of that quarter. This distinction matters only
    for monthly cadence; quarterly cadence still ends the first modeled period at the
    opening calendar quarter-end.
    """
    raw = (cfg.get("charter_profile") or {}).get("target_opening")
    if raw in (None, ""):
        raw = cfg.get("target_opening")
    if isinstance(raw, dict):
        try:
            y = int(raw.get("year"))
            if raw.get("month") is not None:
                m = int(raw.get("month"))
                if 1 <= m <= 12:
                    return y, m
            q = int(raw.get("quarter"))
            if 1 <= q <= 4:
                return y, (q - 1) * 3 + 1
        except Exception:
            pass
    if isinstance(raw, str):
        s = raw.strip()
        m = re.search(r"(\d{4})\s*[-/]?\s*Q([1-4])", s, re.I)
        if m:
            return int(m.group(1)), (int(m.group(2)) - 1) * 3 + 1
        try:
            d = date.fromisoformat(s[:10])
            return d.year, d.month
        except Exception:
            pass
    return int(default_year), int(default_month)


def model_period_year_month(cfg, period: int, ppy: int):
    """Return (year, month) for a 1-based engine period.

    Monthly cadence preserves the engagement's actual opening month when an ISO date
    is supplied. Quarterly cadence maps each period to the first month of its opening
    calendar quarter; model_period_end_date then advances to that quarter's end.
    """
    if int(ppy) == 12:
        y0, start_month = parse_opening_year_month(cfg)
    else:
        y0, q0 = parse_opening_quarter(cfg)
        start_month = (q0 - 1) * 3 + 1
    if ppy == 12:
        off = period - 1
    elif ppy == 4:
        off = (period - 1) * 3
    else:
        raise ValueError(f"unsupported cadence periods_per_year={ppy}")
    idx = (y0 * 12 + start_month - 1) + off
    return idx // 12, idx % 12 + 1



def model_period_end_date(cfg, period: int, ppy: int) -> date:
    """Calendar end date represented by a 1-based engine period.

    Monthly cadence uses month-end. Quarterly cadence uses calendar quarter-end. The
    engagement opening quarter anchors model period 1; an exact opening-day convention can
    be added later without changing downstream curve/regulatory consumers.
    """
    y, m0 = model_period_year_month(cfg, period, ppy)
    if int(ppy) == 4:
        m = m0 + 2
        if m > 12:
            y += (m - 1) // 12
            m = (m - 1) % 12 + 1
    else:
        m = m0
    return date(y, m, calendar.monthrange(y, m)[1])


def period_label(period: int | None, ppy: int) -> str:
    """Human label for a 1-based engine period."""
    if period in (None, 0):
        return "—"
    prefix = "M" if int(ppy) == 12 else "Q"
    return f"{prefix}{int(period)}"


def horizon_label(n_periods: int, ppy: int) -> str:
    """Human-readable computational horizon without pretending periods are quarters."""
    n = int(n_periods)
    if int(ppy) == 12:
        return f"{n} month{'' if n == 1 else 's'}"
    return f"{n} quarter{'' if n == 1 else 's'}"


def cadence_noun(ppy: int, plural: bool = False) -> str:
    w = "month" if int(ppy) == 12 else "quarter"
    return w + ("s" if plural else "")

def quarterly_value_to_period(stem: str, value, ppy: int):
    """Convert a LEGACY numeric *_q value into an equivalent engine-period value.

    Rates representing proportional growth/runoff/decay are compounded; dollar flows
    are allocated evenly across the engine periods inside a quarter. Structural keys
    ending in `_q` can hold lists/dicts, so non-numeric values are intentionally left
    unchanged. At quarterly cadence this is exactly the identity.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return value
    v = float(value)
    ppq = periods_per_quarter(ppy)
    if ppq == 1:
        return v
    if stem in {"growth", "orig_growth", "overhead_growth"}:
        if v <= -1.0:
            return -1.0
        return (1.0 + v) ** (1.0 / ppq) - 1.0
    if stem in {"runoff", "fv_decay", "msr_decay"}:
        if v >= 1.0:
            return 1.0
        return 1.0 - (1.0 - v) ** (1.0 / ppq)
    if stem in {"purchases", "new_deposits", "originations", "opex_fixed", "overhead"}:
        return v / ppq
    return v


def submission_quarters(cfg, default: int = 12) -> int:
    """Regulator-facing business-plan horizon in CALENDAR quarters.

    Foundry's computational horizon may be monthly/quarterly and may extend beyond
    three years.  Regulator-facing business-plan exhibits, however, commonly use a
    Q1-Q12 submission window.  Keep that convention explicit and overridable rather
    than inferring it from ``n_periods`` or baking ``12`` into general model logic.
    """
    cp = cfg.get("charter_profile") or {}
    raw = cp.get("submission_quarters", cfg.get("submission_quarters", default))
    try:
        q = int(raw)
    except Exception:
        q = int(default)
    return max(1, q)


def submission_end_period(cfg, ppy: int, n_periods: int | None = None) -> int:
    """1-based engine period at the end of the regulator-facing submission window.

    If the computational horizon is shorter than the requested submission window,
    return the actual terminal engine period.
    """
    if n_periods is None:
        n_periods = int((cfg.get("assumptions") or {}).get("n_periods") or 12)
    return min(int(n_periods), submission_quarters(cfg) * periods_per_quarter(int(ppy)))


def submission_period_label(cfg, ppy: int, n_periods: int | None = None) -> str:
    """Human label for the submission-window endpoint (normally Q12)."""
    endp = submission_end_period(cfg, ppy, n_periods)
    q = period_to_model_quarter(endp, ppy)
    return f"Q{q}"
