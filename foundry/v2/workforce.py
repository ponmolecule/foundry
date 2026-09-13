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


def workforce_role_expense_series(role: Mapping[str, Any] | None, n_periods: int,
                                   ppy: int = 4, *, growth_context=None,
                                   default_payroll_load_rate: float = 0.0,
                                   default_salary_growth_spec: Mapping[str, Any] | None = None) -> list[float]:
    """Resolve one role/population's native-period payroll expense flow.

    This is the observational cross-module seam used by cost pools.  It intentionally
    composes Count × annual compensation × payroll load and periodizes once, exactly as
    the Workforce runtime does.  Metric-triggered roles fail closed here because a fee
    sourced from payroll can itself affect financial metrics used to activate Workforce;
    that feedback loop needs an explicit dependency design before it can be supported.
    """
    row = dict(role or {})
    if row.get("activation"):
        raise ValueError(
            "cost pools cannot link to a metric-triggered workforce role expense; "
            "use a fixed/entered activation window or break the circular dependency")
    wf = {
        "mode": "roles",
        "default_payroll_load_rate": float(default_payroll_load_rate or 0.0),
        "default_salary_growth_spec": dict(default_salary_growth_spec or {
            "rate": 0.0, "period": "year", "method": "step", "anchor": "hire_anniversary"
        }),
        "roles": [row],
    }
    return workforce_comp_series(wf, int(n_periods), int(ppy), growth_context=growth_context)


WORKFORCE_ADDITIVE_DRIVER = "piecewise_linked"
WORKFORCE_INCOME_FLOW_SOURCE = "income_statement_flow"
WORKFORCE_INCOME_FLOW_METRICS = {
    "fee_income",
    "gain_on_sale",
    "servicing_net",
    "noninterest_income",
    "net_interest_income",
    "total_operating_revenue",
}


def normalize_workforce_additive_component(component: Mapping[str, Any] | None, ppy: int = 12) -> dict:
    """Normalize one additive compensation component.

    Workforce uses the same literal base + marginal-rate band grammar as Advanced Opex,
    but owns its own posting destination.  The component name is never computational.
    Income-statement terms are model-year flows through the event period; the same band
    primitive may also observe the stock/balance sources already supported by Opex.
    """
    c = dict(component or {})
    drv = str(c.get("driver") or "").strip().lower()
    if drv != WORKFORCE_ADDITIVE_DRIVER:
        raise ValueError("workforce additive component must use the tiered/banded driver")
    from .opex_extensions import (
        _normalize_piecewise_bands, _normalize_piecewise_timing, _normalize_observation_lag,
        _normalize_piecewise_terms, _lag_to_engine_periods, timing_interval,
    )
    raw_terms = list(c.get("terms") or [])
    if not raw_terms:
        raise ValueError("workforce tiered/banded component requires at least one driver term")
    terms = []
    for i, raw in enumerate(raw_terms):
        t = dict(raw or {})
        src = str(t.get("source") or "").strip().lower()
        if src == WORKFORCE_INCOME_FLOW_SOURCE:
            metric = str(t.get("metric") or "").strip().lower()
            if metric not in WORKFORCE_INCOME_FLOW_METRICS:
                raise ValueError(
                    f"workforce additive term {i + 1} has unsupported income-statement metric {metric!r}")
            aggregation = str(t.get("aggregation") or "model_year_to_date").strip().lower()
            if aggregation != "model_year_to_date":
                raise ValueError("workforce income-statement flow aggregation must be model_year_to_date")
            try:
                weight = float(t.get("weight") if t.get("weight") is not None else 1.0)
            except (TypeError, ValueError) as e:
                raise ValueError(f"workforce additive term {i + 1} weight must be numeric") from e
            terms.append({"source": src, "metric": metric, "aggregation": aggregation, "weight": weight})
        else:
            # Reuse the Opex typed observation grammar for balance/stock terms.  This is
            # intentionally a shared economic primitive rather than a second Workforce dialect.
            terms.append(_normalize_piecewise_terms([t])[0])
    timing = _normalize_piecewise_timing(c.get("timing"))
    lag = _normalize_observation_lag(c.get("observation_lag"))
    timing_interval(timing["mode"], int(ppy))
    _lag_to_engine_periods(lag, int(ppy))
    if any(t["source"] == "bank_total_assets" for t in terms) and lag["value"] == 0:
        raise ValueError("workforce Total Assets term requires a positive observation lag to avoid circularity")
    return {
        "driver": drv,
        "component_id": str(c.get("component_id") or "").strip(),
        "name": str(c.get("name") or "Tiered / banded compensation component"),
        "terms": terms,
        "bands": _normalize_piecewise_bands(c.get("bands")),
        "timing": timing,
        "observation_lag": lag,
    }


def resolve_workforce_additive_components(workforce: Mapping[str, Any] | None, ppy: int = 12) -> list[dict]:
    """Return normalized additive compensation components; absence is exactly inert."""
    return [normalize_workforce_additive_component(c, ppy)
            for c in ((workforce or {}).get("additive_components") or []) if c]


def _income_flow_term_value(term: Mapping[str, Any], observation_ordinal: int,
                            metrics: Mapping[str, Any]) -> float:
    """Resolve a model-year income-statement flow through a 1-based observation period."""
    obs = int(observation_ordinal)
    if obs <= 0:
        raise ValueError("workforce income-statement flow observation precedes the first modeled period")
    ppy = int(metrics.get("periods_per_year") or 12)
    histories = metrics.get("income_statement_flow_history") or {}
    metric = str(term.get("metric") or "")
    arr = histories.get(metric)
    if arr is None:
        raise ValueError(f"workforce income-statement flow metric {metric!r} is unavailable in this engine run")
    values = list(arr)
    if obs > len(values):
        raise ValueError(f"workforce income-statement flow observation period {obs} is unavailable")
    year_start = ((obs - 1) // ppy) * ppy
    return sum(float(v or 0.0) for v in values[year_start:obs])


def workforce_additive_component_amount(component: Mapping[str, Any], period_index: int,
                                         metrics: Mapping[str, Any]) -> float:
    """Evaluate one additive compensation component for a zero-based engine period."""
    from .opex_extensions import (
        _piecewise_event_due, _lag_to_engine_periods, _piecewise_term_value,
        apply_piecewise_schedule, _normalize_observation_lag,
    )
    c = component
    i = int(period_index)
    ppy = int(metrics.get("periods_per_year") or 12)
    if not _piecewise_event_due(c, i, ppy):
        return 0.0
    lag_periods = _lag_to_engine_periods(_normalize_observation_lag(c.get("observation_lag")), ppy)
    obs = (i + 1) - lag_periods
    total = 0.0
    for term in c.get("terms") or []:
        if str(term.get("source") or "") == WORKFORCE_INCOME_FLOW_SOURCE:
            val = _income_flow_term_value(term, obs, metrics)
        else:
            val = _piecewise_term_value(term, obs, metrics)
        total += float(term.get("weight") if term.get("weight") is not None else 1.0) * float(val or 0.0)
    return apply_piecewise_schedule(total, c.get("bands"))


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
        self.additive_components = resolve_workforce_additive_components(self.wf, self.ppy)
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
