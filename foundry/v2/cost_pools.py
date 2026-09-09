"""Shared cost-pool sources for fee products and other downstream consumers.

A cost pool is a *derived observational source*: it composes expense series owned by
Operating Expense / Workforce, but never owns or re-posts those expenses.  The pool
resolves to native engine-period dollar flows so downstream fee math must not annualize
or periodize the quantity again.

Canonical shape::

    assumptions.cost_pools = [
      {
        "series_id": "cost-pool-platform-services",
        "owner_module": "cost_pool",
        "name": "Platform Services Eligible Costs",
        "components": [
          {"kind": "operating_expense_category", "series_id": "opex-tech",
           "allocation_pct": 1.0},
          {"kind": "workforce_role_expense", "series_id": "wf-exp-platform-ops",
           "allocation_pct": 0.4},
        ],
      }
    ]

``allocation_pct`` answers the upstream eligibility/allocation question.  A fee
stream's ``recovery_pct`` is a distinct downstream pricing assumption and must not be
used to compose the pool.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

_VALID_COMPONENT_KINDS = {"operating_expense_category", "workforce_role_expense"}


def _pools(assumptions: Mapping[str, Any] | None) -> list[Mapping[str, Any]]:
    raw = (assumptions or {}).get("cost_pools") or []
    if isinstance(raw, Mapping):
        # Defensive compatibility for hand-authored/name-keyed drafts.  New UI writes a list
        # because the stable series_id, not a display-name dictionary key, is the identity.
        out = []
        for name, pool in raw.items():
            row = dict(pool or {})
            row.setdefault("name", str(name))
            out.append(row)
        return out
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        raise ValueError("assumptions.cost_pools must be a list")
    return [p or {} for p in raw]


def cost_pool_catalog(assumptions: Mapping[str, Any] | None) -> list[dict[str, str]]:
    """Return stable cost-pool identities for UI/validation/reference resolution."""
    out: list[dict[str, str]] = []
    for i, pool in enumerate(_pools(assumptions)):
        sid = str((pool or {}).get("series_id") or "").strip()
        name = str((pool or {}).get("name") or "").strip()
        if not sid:
            raise ValueError(f"cost_pools[{i}] requires stable series_id")
        if not name:
            raise ValueError(f"cost_pools[{i}] requires a name")
        owner = str((pool or {}).get("owner_module") or "cost_pool").strip()
        if owner != "cost_pool":
            raise ValueError(f"cost_pools[{i}].owner_module must be cost_pool")
        out.append({"series_id": sid, "name": name})
    ids = [x["series_id"] for x in out]
    if len(ids) != len(set(ids)):
        raise ValueError("cost-pool series_id values must be unique")
    return out


def resolve_cost_pool_ref(ref: str | None, assumptions: Mapping[str, Any] | None) -> Mapping[str, Any]:
    """Resolve a cost pool by stable series_id; unique display-name fallback is legacy-only."""
    ident = str(ref or "").strip()
    if not ident:
        raise ValueError("cost_pool driver requires driver.ref")
    pools = _pools(assumptions)
    by_id = [p for p in pools if str((p or {}).get("series_id") or "").strip() == ident]
    if len(by_id) == 1:
        return by_id[0]
    if len(by_id) > 1:
        raise ValueError(f"cost_pool ref {ident!r} is ambiguous")
    by_name = [p for p in pools if str((p or {}).get("name") or "").strip() == ident]
    if len(by_name) == 1:
        return by_name[0]
    raise ValueError(f"cost_pool ref {ident!r} resolved to {len(by_name)} matches; expected exactly one")


def cost_pool_series(pool: Mapping[str, Any] | None, assumptions: Mapping[str, Any] | None,
                     n_periods: int, ppy: int = 4, *, growth_context=None) -> list[float]:
    """Resolve one cost pool to native-period dollar *flows*.

    Every component is observational: resolving the source does not post an expense.
    The expense remains owned by the linked Operating Expense / Workforce series.
    """
    pool = pool or {}
    n, ppy = int(n_periods), int(ppy)
    comps = pool.get("components") or []
    if not isinstance(comps, list):
        raise ValueError("cost pool components must be a list")
    total = [0.0] * n
    seen_components: set[tuple[str, str]] = set()
    from .series import resolve_linked_series
    for i, comp in enumerate(comps):
        comp = comp or {}
        kind = str(comp.get("kind") or "").strip()
        if kind not in _VALID_COMPONENT_KINDS:
            raise ValueError(f"cost pool component {i} has unsupported kind {kind!r}")
        sid = str(comp.get("series_id") or "").strip()
        if not sid:
            raise ValueError(f"cost pool component {i} requires series_id")
        token = (kind, sid)
        if token in seen_components:
            raise ValueError(f"cost pool component {i} duplicates {kind}:{sid}")
        seen_components.add(token)
        raw_alloc = comp.get("allocation_pct")
        if raw_alloc is None:
            raw_alloc = comp.get("weight", 1.0)  # compatibility with early hand-authored drafts
        try:
            alloc = float(raw_alloc)
        except (TypeError, ValueError):
            raise ValueError(f"cost pool component {i} allocation_pct must be numeric")
        if alloc < 0.0 or alloc > 1.0:
            raise ValueError(f"cost pool component {i} allocation_pct must be between 0 and 1")
        arr = resolve_linked_series(
            assumptions or {}, {"kind": kind, "series_id": sid, "aggregation": "sum"},
            n, ppy, context=growth_context)
        if len(arr) != n:
            raise ValueError(f"cost pool component {i} resolved to {len(arr)} periods; expected {n}")
        for q in range(n):
            total[q] += float(arr[q] or 0.0) * alloc
    return total


def cost_pool_series_map(assumptions: Mapping[str, Any] | None, n_periods: int,
                         ppy: int = 4, *, growth_context=None) -> dict[str, list[float]]:
    """Resolve all pools once per run, keyed by stable ID plus unique legacy name aliases."""
    pools = _pools(assumptions)
    catalog = cost_pool_catalog(assumptions)
    out: dict[str, list[float]] = {}
    name_counts: dict[str, int] = {}
    for x in catalog:
        name_counts[x["name"]] = name_counts.get(x["name"], 0) + 1
    for pool in pools:
        sid = str((pool or {}).get("series_id") or "").strip()
        name = str((pool or {}).get("name") or "").strip()
        arr = cost_pool_series(pool, assumptions, n_periods, ppy, growth_context=growth_context)
        out[sid] = arr
        if name and name_counts.get(name) == 1:
            out[name] = arr  # compatibility only; new authoring stores the stable ID
    return out
