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

from typing import Any, Callable, Mapping, Sequence

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


def managed_notional_source_catalog(assumptions: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    """Return canonical independent AUC/AUM sources for workforce activation.

    Customer Acquisition feeds are the canonical source when a fee product merely
    consumes that feed.  Product display names remain aliases for backward compatibility,
    but new authoring should store the feed's stable ``series_id`` in ``activation.source``.

    Standalone managed-notional products (not backed by a CAC feed) remain valid trigger
    sources.  They use an internal unique key so duplicate display names still fail closed.
    """
    a = assumptions or {}
    feeds = a.get("cac_feeds") or {}
    entries: dict[str, dict[str, Any]] = {}
    feed_key_by_name: dict[str, str] = {}

    def _add(key: str, label: str, alias: str | None = None, *, kind: str) -> None:
        if not key:
            return
        e = entries.setdefault(key, {"key": key, "label": label or key, "aliases": set(), "kind": kind})
        if label:
            e["label"] = label
        if alias:
            e["aliases"].add(alias)

    for name, raw in feeds.items():
        f = raw or {}
        nm = str(name or "").strip()
        sid = str(f.get("series_id") or "").strip()
        # Current UI creates stable feed IDs.  The name fallback preserves older configs
        # without silently inventing a new persistent identity during validation.
        key = sid or nm
        if not key:
            continue
        feed_key_by_name[nm] = key
        _add(key, nm or key, nm, kind="cac_feed")

    products = list(a.get("deposit_products") or []) + list(a.get("obs_exposures") or [])
    for idx, raw in enumerate(products):
        p = raw or {}
        if not (p.get("managed_notional") or p.get("managed_notional_source") or p.get("managed_notional_source_id")):
            continue
        nm = str(p.get("name") or "").strip()
        src_id = str(p.get("managed_notional_source_id") or "").strip()
        src_name = str(p.get("managed_notional_source") or "").strip()
        if src_id:
            key = src_id
            _add(key, (entries.get(key) or {}).get("label") or src_name or nm or key, nm, kind="cac_feed")
            if src_name:
                _add(key, (entries.get(key) or {}).get("label") or src_name, src_name, kind="cac_feed")
        elif src_name and src_name in feed_key_by_name:
            key = feed_key_by_name[src_name]
            _add(key, (entries.get(key) or {}).get("label") or src_name, nm, kind="cac_feed")
            _add(key, (entries.get(key) or {}).get("label") or src_name, src_name, kind="cac_feed")
        elif p.get("managed_notional"):
            # Standalone product AUC has no stable Series identity yet.  Keep it usable,
            # but give each product a distinct internal key so duplicate names remain
            # ambiguous when referenced through the legacy display-name alias.
            key = f"managed-product:{idx}:{nm}"
            _add(key, nm or f"Managed notional {idx + 1}", nm, kind="managed_product")

    out = []
    for e in entries.values():
        x = dict(e)
        x["aliases"] = sorted(x.get("aliases") or [])
        out.append(x)
    return out


def resolve_managed_notional_source(source: str, catalog: Sequence[Mapping[str, Any]]) -> str:
    """Resolve a stable source key, accepting legacy display-name aliases.

    Multiple fee products with the same display name are *not* ambiguous when they all
    consume the same underlying CAC feed: aliases collapse to that one stable Series key.
    If the same alias genuinely points at different AUC sources, fail closed.
    """
    src = str(source or "").strip()
    if not src:
        raise ValueError("activation.source is required for managed_notional_end")
    direct = [str(e.get("key") or "") for e in catalog if str(e.get("key") or "") == src]
    if len(set(direct)) == 1:
        return direct[0]
    keys = {
        str(e.get("key") or "")
        for e in catalog
        if src in {str(a) for a in (e.get("aliases") or [])}
    }
    keys.discard("")
    if len(keys) != 1:
        raise ValueError(f"activation.source must identify exactly one AUC/AUM source: {src}")
    return next(iter(keys))


def validate_activation_rule(rule: Mapping[str, Any] | None, *,
                             available_sources: list[str] | tuple[str, ...] | set[str] | None = None,
                             source_catalog: Sequence[Mapping[str, Any]] | None = None) -> dict[str, Any]:
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
        if source_catalog is not None:
            resolve_managed_notional_source(source, source_catalog)
        elif available_sources is not None:
            matches = [x for x in available_sources if x == source]
            if len(matches) != 1:
                raise ValueError(f"activation.source must identify exactly one AUC/AUM source: {source}")
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
