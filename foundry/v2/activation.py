"""Generic, deterministic activation rules for workforce roles.

Activation is deliberately separate from growth.  It answers *when* a modeled role
becomes active; the growth resolver answers how compensation evolves after activation.

Rules are intentionally constrained rather than becoming a spreadsheet-formula language.
The engine supports a small registry of approved modeled metrics and four comparators.
Independent observables (currently EOP managed notional / AUC / AUM) may trigger in the
same period because their full path is resolved before NIE.  Endogenous financial metrics
must use completed history and therefore activate in the next period, avoiding circularity.
"""
from __future__ import annotations

from typing import Any, Callable, Mapping

MetricGetter = Callable[[str, str | None, int], float | None]

COMPARATORS = {">=", ">", "<=", "<"}
REFERENCES = {"fixed", "prior_period", "prior_year"}
TIMINGS = {"same_period", "next_period"}

# Registry is intentionally small and extensible.  "independent" means the metric can be
# known for the current period before workforce/NIE is calculated.  "endogenous" means
# workforce expense can affect the metric, so only completed-period observations are safe.
METRICS: dict[str, dict[str, Any]] = {
    "managed_notional_end": {
        "label": "EOP AUC / AUM",
        "dependency": "independent",
        "source_required": True,
        "unit": "currency",
    },
    "efficiency_ratio": {
        "label": "Efficiency ratio",
        "dependency": "endogenous",
        "source_required": False,
        "unit": "ratio",
    },
    "net_income": {
        "label": "Net income",
        "dependency": "endogenous",
        "source_required": False,
        "unit": "currency",
    },
}


def metric_meta(metric: str) -> Mapping[str, Any]:
    if metric not in METRICS:
        raise ValueError(f"unsupported activation metric: {metric}")
    return METRICS[metric]


def _compare(lhs: float, op: str, rhs: float) -> bool:
    if op == ">=": return lhs >= rhs
    if op == ">": return lhs > rhs
    if op == "<=": return lhs <= rhs
    if op == "<": return lhs < rhs
    raise ValueError(f"unsupported activation comparator: {op}")


def normalize_rule(rule: Mapping[str, Any] | None) -> dict[str, Any]:
    r = dict(rule or {})
    if not r:
        return {}
    r.setdefault("type", "metric")
    if r.get("type") != "metric":
        raise ValueError("activation.type must be 'metric'")
    metric = str(r.get("metric") or "")
    meta = metric_meta(metric)
    r["metric"] = metric
    r.setdefault("operator", ">=")
    r.setdefault("reference", "fixed")
    # Safe default is derived from dependency.  AUC/AUM may trigger in the same period;
    # endogenous metrics use the last completed period and activate one period later.
    r.setdefault("timing", "same_period" if meta["dependency"] == "independent" else "next_period")
    r.setdefault("multiplier", 1.0)
    return r


def validate_activation_rule(rule: Mapping[str, Any] | None, *,
                             available_sources: list[str] | tuple[str, ...] | set[str] | None = None) -> dict[str, Any]:
    r = normalize_rule(rule)
    if not r:
        return r
    meta = metric_meta(r["metric"])
    op = r.get("operator")
    ref = r.get("reference")
    timing = r.get("timing")
    if op not in COMPARATORS:
        raise ValueError("activation.operator must be one of >=, >, <=, <")
    if ref not in REFERENCES:
        raise ValueError("activation.reference must be fixed, prior_period, or prior_year")
    if timing not in TIMINGS:
        raise ValueError("activation.timing must be same_period or next_period")
    if meta["dependency"] == "endogenous" and timing != "next_period":
        raise ValueError(f"{r['metric']} is workforce-dependent and must activate next_period from completed history")
    source = r.get("source")
    if meta.get("source_required"):
        if not isinstance(source, str) or not source.strip():
            raise ValueError(f"activation.source is required for {r['metric']}")
        if available_sources is not None:
            matches = [x for x in available_sources if x == source]
            if len(matches) != 1:
                raise ValueError(f"activation.source must name exactly one managed-notional product: {source}")
    if ref == "fixed":
        if not isinstance(r.get("value"), (int, float)) or isinstance(r.get("value"), bool):
            raise ValueError("activation.value must be numeric when reference=fixed")
    else:
        m = r.get("multiplier", 1.0)
        if not isinstance(m, (int, float)) or isinstance(m, bool) or m < 0:
            raise ValueError("activation.multiplier must be a non-negative number")
    return r


def rule_satisfied(rule: Mapping[str, Any], *, current_period: int, ppy: int,
                   metric_getter: MetricGetter) -> bool:
    """Return whether ``rule`` activates a role in ``current_period``.

    ``metric_getter(metric, source, period)`` uses 1-based model periods.  For
    ``same_period`` rules the current independent metric is observed.  For
    ``next_period`` rules the immediately preceding completed period is observed.
    Prior-period/prior-year references are relative to that observation period.
    Missing history simply means "not yet triggered".
    """
    r = normalize_rule(rule)
    if not r:
        return False
    obs = int(current_period) if r["timing"] == "same_period" else int(current_period) - 1
    if obs < 1:
        return False
    lhs = metric_getter(r["metric"], r.get("source"), obs)
    if lhs is None:
        return False
    ref = r.get("reference", "fixed")
    if ref == "fixed":
        rhs = float(r.get("value") or 0.0)
    else:
        back = 1 if ref == "prior_period" else int(ppy)
        rp = obs - back
        if rp < 1:
            return False
        prior = metric_getter(r["metric"], r.get("source"), rp)
        if prior is None:
            return False
        rhs = float(prior) * float(r.get("multiplier", 1.0) or 0.0)
    return _compare(float(lhs), str(r.get("operator") or ">="), rhs)
