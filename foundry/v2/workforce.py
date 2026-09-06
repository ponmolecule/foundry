"""Workforce/cohort authoring -> native-cadence compensation expense series."""
from __future__ import annotations

from typing import Any, Callable, Mapping

from .activation import rule_satisfied
from .growth import growth_multiplier


class WorkforceRuntime:
    """Stateful workforce resolver used by the engine period-by-period.

    Fixed-period and metric-triggered roles share the same compensation trajectory once
    active.  Activation is sticky: the first period whose rule is satisfied becomes the
    resolved hire period and the role remains active thereafter unless ``end_period`` ends it.
    """
    def __init__(self, workforce: Mapping[str, Any] | None, n_periods: int,
                 ppy: int = 4, *, growth_context=None):
        self.wf = workforce or {}
        self.n = int(n_periods)
        self.ppy = int(ppy)
        self.growth_context = growth_context
        self.default_load = float(self.wf.get("default_payroll_load_rate") or 0.0)
        self.default_spec = self.wf.get("default_salary_growth_spec") or {
            "rate": 0.0, "period": "year", "method": "step", "anchor": "hire_anniversary"
        }
        self.rows: list[dict[str, Any]] = []
        for raw in self.wf.get("roles") or []:
            if not raw:
                continue
            row = dict(raw)
            count = float(row.get("count") if row.get("count") is not None else 1.0)
            annual = float(row.get("annual_comp") or row.get("base_salary_annual") or 0.0)
            end = row.get("end_period")
            end = int(end) if end not in (None, "") else None
            load = float(row.get("payroll_load_rate") if row.get("payroll_load_rate") is not None else self.default_load)
            if count < 0: raise ValueError("workforce count must be >= 0")
            if annual < 0: raise ValueError("workforce annual_comp must be >= 0")
            if load < 0: raise ValueError("workforce payroll_load_rate must be >= 0")
            activation = row.get("activation") or None
            if activation:
                hire = None
            else:
                hire = int(row.get("hire_period") or 1)
                if hire < 1: raise ValueError("workforce hire_period must be >= 1")
                if end is not None and end < hire:
                    raise ValueError("workforce end_period cannot precede hire_period")
            spec = dict(self.default_spec)
            spec.update(row.get("salary_growth_spec") or {})
            self.rows.append({"raw": row, "count": count, "annual": annual, "end": end,
                              "load": load, "activation": activation, "hire": hire, "spec": spec})

    def expense_for_period(self, period: int, metric_getter: Callable[[str, str | None, int], float | None] | None = None) -> float:
        q = int(period)
        total = 0.0
        for st in self.rows:
            if st["count"] <= 0:
                continue
            if st["hire"] is None:
                if metric_getter is None:
                    continue
                if rule_satisfied(st["activation"], current_period=q, ppy=self.ppy,
                                  metric_getter=metric_getter):
                    st["hire"] = q
            hire = st["hire"]
            if hire is None or q < hire:
                continue
            if st["end"] is not None and q > st["end"]:
                continue
            mult = growth_multiplier(st["spec"], current_period=q, start_period=hire,
                                     ppy=self.ppy, context=self.growth_context,
                                     base_position="period1")
            total += st["annual"] * mult * st["count"] * (1.0 + st["load"]) / float(self.ppy)
        return total

    def resolved_hires(self) -> list[int | None]:
        return [st["hire"] for st in self.rows]


def workforce_comp_series(workforce: Mapping[str, Any] | None, n_periods: int,
                          ppy: int = 4, *, growth_context=None,
                          metric_series: Mapping[tuple[str, str | None], list[float]] | None = None) -> list[float]:
    """Return total payroll expense dollars per native engine period.

    ``metric_series`` is optional and only needed for metric-triggered roles.  Keys are
    ``(metric, source)`` tuples and values are zero-based native-period series.  Fixed-role
    behavior remains identical to the prior implementation.
    """
    runtime = WorkforceRuntime(workforce, n_periods, ppy, growth_context=growth_context)
    series = metric_series or {}

    def getter(metric: str, source: str | None, period: int):
        arr = series.get((metric, source))
        if arr is None:
            arr = series.get((metric, None))
        if arr is None or period < 1 or period > len(arr):
            return None
        return arr[period - 1]

    return [runtime.expense_for_period(q, getter if series else None)
            for q in range(1, int(n_periods) + 1)]
