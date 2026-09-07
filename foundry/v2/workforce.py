"""Workforce/cohort authoring -> native-cadence compensation expense series."""
from __future__ import annotations

from typing import Any, Callable, Mapping

from .activation import rule_satisfied
from .growth import growth_multiplier


def workforce_role_count_series(role: Mapping[str, Any] | None, n_periods: int, ppy: int = 4,
                                 *, growth_context=None, include_activation_window: bool = True) -> list[float]:
    """Resolve one economically homogeneous workforce population's headcount path.

    ``count_spec`` is the new generic Foundry-Series contract (Flat / Growth / Explicit).
    Absence of ``count_spec`` preserves the historical scalar ``count`` exactly.  Metric-triggered
    activation is intentionally not resolved here; callers that need a static cross-module link
    must reject such roles to avoid circularity.
    """
    role = role or {}
    n, ppy = int(n_periods), int(ppy)
    base = float(role.get("count") if role.get("count") is not None else 1.0)
    spec = role.get("count_spec")
    if spec:
        from .series import normalize_series_spec, resolve_entered_series
        ns = normalize_series_spec(spec, default_value=base)
        if ns["source"] != "entered":
            raise ValueError("workforce count_spec must be entered; link workforce from consuming modules instead")
        if ns["trajectory"] == "growth":
            from .growth import resolve_growth_series
            hire = int(role.get("hire_period") or 1) if not role.get("activation") else 1
            arr = resolve_growth_series(float(ns["base"]), ns["growth_spec"], n, ppy,
                                        start_period=hire, context=growth_context)
        else:
            arr = resolve_entered_series(ns, n, ppy, context=growth_context, default_value=base)
    else:
        arr = [base] * n
    if not include_activation_window:
        return arr
    # Fixed start/end windows are deterministic and therefore safe for links.
    if role.get("activation"):
        return arr
    hire = int(role.get("hire_period") or 1)
    end = role.get("end_period")
    end = int(end) if end not in (None, "") else None
    return [float(v) if p >= hire and (end is None or p <= end) else 0.0
            for p, v in enumerate(arr, 1)]


def workforce_role_compensation_series(role: Mapping[str, Any] | None, n_periods: int,
                                        ppy: int = 4, *, growth_context=None,
                                        start_period: int = 1,
                                        default_growth_spec: Mapping[str, Any] | None = None) -> list[float]:
    """Resolve annual compensation per FTE as a Foundry Series.

    New authoring uses ``compensation_spec`` (Flat / Growth / Explicit).  The returned
    values are annual compensation levels, not payroll expense; payroll periodization
    happens once in :class:`WorkforceRuntime`.  With no ``compensation_spec`` this helper
    reproduces the historical ``annual_comp`` + salary-growth path, including its
    hire-anniversary start-period semantics.
    """
    role = role or {}
    n, ppy = int(n_periods), int(ppy)
    base = float(role.get("annual_comp") or role.get("base_salary_annual") or 0.0)
    cs = role.get("compensation_spec")
    if cs:
        from .series import normalize_series_spec, resolve_entered_series
        ns = normalize_series_spec(cs, default_value=base)
        if ns["source"] != "entered":
            raise ValueError(
                "workforce compensation_spec must be entered; Link/Derived require a "
                "compatible module-owned source and none is currently whitelisted")
        if ns["trajectory"] == "growth":
            from .growth import resolve_growth_series
            return resolve_growth_series(float(ns["base"]), ns["growth_spec"], n, ppy,
                                         start_period=int(start_period), context=growth_context)
        return resolve_entered_series(ns, n, ppy, context=growth_context, default_value=base)

    spec = dict(default_growth_spec or {
        "rate": 0.0, "period": "year", "method": "step", "anchor": "hire_anniversary"
    })
    spec.update(role.get("salary_growth_spec") or {})
    return [base * growth_multiplier(spec, current_period=q, start_period=int(start_period),
                                     ppy=ppy, context=growth_context, base_position="period1")
            for q in range(1, n + 1)]


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
            count_series = workforce_role_count_series(row, self.n, self.ppy,
                                                       growth_context=self.growth_context,
                                                       include_activation_window=False)
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
                comp_start = 1  # growth is re-anchored to the resolved hire in expense_for_period
            else:
                hire = int(row.get("hire_period") or 1)
                comp_start = hire
                if hire < 1: raise ValueError("workforce hire_period must be >= 1")
                if end is not None and end < hire:
                    raise ValueError("workforce end_period cannot precede hire_period")
            legacy_spec = dict(self.default_spec)
            legacy_spec.update(row.get("salary_growth_spec") or {})
            comp_ns = None
            comp_series = None
            if row.get("compensation_spec"):
                from .series import normalize_series_spec
                comp_ns = normalize_series_spec(row.get("compensation_spec"), default_value=annual)
                if comp_ns["source"] != "entered":
                    raise ValueError(
                        "workforce compensation_spec must be entered; Link/Derived require a "
                        "compatible module-owned source and none is currently whitelisted")
                if comp_ns["trajectory"] != "growth":
                    comp_series = workforce_role_compensation_series(
                        row, self.n, self.ppy, growth_context=self.growth_context,
                        start_period=comp_start, default_growth_spec=self.default_spec)
            self.rows.append({"raw": row, "count": count, "count_series": count_series,
                              "annual": annual, "end": end, "load": load,
                              "activation": activation, "hire": hire, "spec": legacy_spec,
                              "comp_ns": comp_ns, "comp_series": comp_series})

    def expense_for_period(self, period: int, metric_getter: Callable[[str, str | None, int], float | None] | None = None) -> float:
        q = int(period)
        total = 0.0
        for st in self.rows:
            count_now = float(st["count_series"][q - 1]) if q <= len(st["count_series"]) else 0.0
            if count_now <= 0:
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
            if st["comp_ns"] is not None:
                ns = st["comp_ns"]
                if ns["trajectory"] == "growth":
                    annual_now = float(ns["base"]) * growth_multiplier(
                        ns["growth_spec"], current_period=q, start_period=hire,
                        ppy=self.ppy, context=self.growth_context, base_position="period1")
                else:
                    annual_now = float(st["comp_series"][q - 1])
            else:
                # Exact legacy path: annual_comp multiplied by the inherited/row salary
                # growth spec, anchored at the resolved hire period.
                mult = growth_multiplier(st["spec"], current_period=q, start_period=hire,
                                         ppy=self.ppy, context=self.growth_context,
                                         base_position="period1")
                annual_now = st["annual"] * mult
            total += annual_now * count_now * (1.0 + st["load"]) / float(self.ppy)
        return total

    def count_for_period(self, period: int) -> list[float]:
        """Resolved active headcount by workforce row for one native period.

        Call after ``expense_for_period`` for that period when metric activation is in use,
        so newly satisfied activations are reflected consistently in both payroll and count.
        """
        q=int(period); out=[]
        for st in self.rows:
            hire=st["hire"]
            active=(hire is not None and q>=hire and (st["end"] is None or q<=st["end"]))
            out.append(float(st["count_series"][q-1]) if active and q<=len(st["count_series"]) else 0.0)
        return out

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
