"""Workforce/cohort authoring -> native-cadence compensation expense series."""
from __future__ import annotations

from typing import Any, Mapping

from .growth import resolve_growth_series


def workforce_comp_series(workforce: Mapping[str, Any] | None, n_periods: int,
                          ppy: int = 4, *, growth_context=None) -> list[float]:
    """Return total payroll expense dollars per native engine period.

    A role row may represent one position or a cohort. Annual compensation is escalated
    independently per row, converted to native-period expense, then optionally payroll-loaded.
    Rows outside the current horizon are valid and simply contribute zero.
    """
    wf = workforce or {}
    roles = wf.get("roles") or []
    n, ppy = int(n_periods), int(ppy)
    out = [0.0] * n
    default_load = float(wf.get("default_payroll_load_rate") or 0.0)
    default_spec = wf.get("default_salary_growth_spec") or {
        "rate": 0.0, "period": "year", "method": "step", "anchor": "hire_anniversary"
    }
    for row in roles:
        if not row:
            continue
        count = float(row.get("count") if row.get("count") is not None else 1.0)
        if count <= 0:
            continue
        annual = float(row.get("annual_comp") or row.get("base_salary_annual") or 0.0)
        hire = int(row.get("hire_period") or 1)
        end = row.get("end_period")
        end = int(end) if end not in (None, "") else None
        if hire < 1:
            raise ValueError("workforce hire_period must be >= 1")
        if end is not None and end < hire:
            raise ValueError("workforce end_period cannot precede hire_period")
        load = float(row.get("payroll_load_rate") if row.get("payroll_load_rate") is not None else default_load)
        if load < 0:
            raise ValueError("workforce payroll_load_rate must be >= 0")
        # Row specs are sparse overrides by design: a 48-role paste usually varies only
        # the escalation RATE while sharing period/method/anchor defaults.
        spec = dict(default_spec)
        spec.update(row.get("salary_growth_spec") or {})
        annual_path = resolve_growth_series(
            annual, spec, n, ppy, start_period=hire, end_period=end,
            context=growth_context, base_position="period1")
        for i, ann in enumerate(annual_path):
            out[i] += ann * count * (1.0 + load) / float(ppy)
    return out
