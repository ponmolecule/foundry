"""Shared eligible-cost pools for cost-recovery revenue or expense consumers.

A cost pool is a *non-posting calculation source*.  It can combine three economic shapes:

* linked modeled costs already owned/posted by Operating Expense or Workforce;
* entered recurring cost-base assumptions used only for pricing; and
* balance-derived cost components (currently canonical managed-notional/AUC balances)
  multiplied by a natural-period rate.

Every component resolves to a native engine-period dollar *flow*.  The downstream consumer
therefore applies recovery and markup directly; it must not annualize or periodize the pool again.

Canonical examples::

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
          {"kind": "assumption_cost_base", "series_id": "cost-base-fixed",
           "name": "Fixed service cost base", "allocation_pct": 1.0,
           "flow_spec": {"trajectory": "growth", "value": 1200000, "period": "year",
                         "growth_spec": {"rate": 0.03, "period": "year",
                                         "method": "step", "anchor": "model_year"}}},
          {"kind": "balance_derived_cost", "series_id": "cost-base-auc-variable",
           "name": "Variable managed-notional cost", "allocation_pct": 1.0,
           "source_kind": "managed_notional", "source_series_id": "cac-auc-primary",
           "measure": "period_average", "rate_period": "year",
           "rate_spec": {"source": "entered", "trajectory": "flat", "value": 0.012}},
        ],
      }
    ]

``allocation_pct`` answers the upstream eligibility/allocation question.  A downstream
consumer's ``recovery_pct`` is a separate pricing assumption. Entered and balance-derived
components are non-posting: they construct an eligible cost base. A Fee Product consumer may
post revenue; an Operating Expense consumer may post the final recovered/marked-up charge once.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

_LINKED_COMPONENT_KINDS = {"operating_expense_category", "workforce_role_expense"}
_VALID_COMPONENT_KINDS = _LINKED_COMPONENT_KINDS | {"assumption_cost_base", "balance_derived_cost"}
_RATE_PERIOD_MONTHS = {"month": 1, "quarter": 3, "year": 12}
_BALANCE_SOURCE_KINDS = {"managed_notional"}


def _pools(assumptions: Mapping[str, Any] | None) -> list[Mapping[str, Any]]:
    raw = (assumptions or {}).get("cost_pools") or []
    if isinstance(raw, Mapping):
        # Defensive compatibility for hand-authored/name-keyed drafts. New UI writes a list
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


def cost_pool_component_series_ids(assumptions: Mapping[str, Any] | None) -> list[str]:
    """Stable identities owned by new non-posting cost-pool components.

    Legacy linked components use ``series_id`` for the *upstream* source and are therefore
    excluded here. New authored/derived components own their own series identity.
    """
    out: list[str] = []
    for pi, pool in enumerate(_pools(assumptions)):
        for ci, raw in enumerate((pool or {}).get("components") or []):
            comp = raw or {}
            if str(comp.get("kind") or "") not in {"assumption_cost_base", "balance_derived_cost"}:
                continue
            sid = str(comp.get("series_id") or "").strip()
            if not sid:
                raise ValueError(f"cost_pools[{pi}].components[{ci}] requires stable series_id")
            out.append(sid)
    if len(out) != len(set(out)):
        raise ValueError("cost-pool component series_id values must be unique")
    return out


def cost_pool_balance_source_catalog(assumptions: Mapping[str, Any] | None) -> list[dict[str, str]]:
    """Canonical balance sources with sufficient monthly detail for cost accruals.

    r63 made Customer Acquisition AUC a canonical monthly balance Series even when the model
    presents quarterly.  Those Series can therefore support exact monthly period-end or
    period-average cost accruals. Other balance families should join this registry only after
    they publish an equally explicit canonical monthly path; we do not interpolate unknown
    intra-quarter economics merely to make a source selectable.
    """
    out: list[dict[str, str]] = []
    for name, raw in ((assumptions or {}).get("cac_feeds") or {}).items():
        feed = raw or {}
        sid = str(feed.get("series_id") or "").strip()
        if not sid:
            continue
        count_sid = str(feed.get("customer_count_series_id") or "").strip()
        if count_sid and count_sid == sid:
            raise ValueError(
                f"CAC feed {name!r} uses the same series_id for AUC and customer count; "
                "balance semantics require distinct stable Series IDs")
        out.append({
            "source_kind": "managed_notional",
            "series_id": sid,
            "name": str(name or sid),
            "feed": str(name or sid),
            "owner_module": "customer_acquisition",
            "semantic_type": "auc_end",
            "measure_semantic": "canonical_monthly_balance",
        })
    ids = [x["series_id"] for x in out]
    if len(ids) != len(set(ids)):
        raise ValueError("cost-pool managed-notional source series_id values must be unique")
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


def _iter_fee_streams(assumptions: Mapping[str, Any] | None):
    a = assumptions or {}
    for key in ("lending_products", "deposit_products", "obs_exposures"):
        for product in a.get(key) or []:
            for stream in (product or {}).get("fee_streams") or []:
                yield stream or {}


def _pool_downstream_fee_streams(pool: Mapping[str, Any], assumptions: Mapping[str, Any] | None) -> list[Mapping[str, Any]]:
    """Fee streams whose native quantity is this pool.

    Stable pool ID is authoritative. Unique-name matching is retained only for legacy drafts,
    mirroring ``resolve_cost_pool_ref``.
    """
    pid = str((pool or {}).get("series_id") or "").strip()
    pname = str((pool or {}).get("name") or "").strip()
    out: list[Mapping[str, Any]] = []
    for st in _iter_fee_streams(assumptions):
        drv = (st or {}).get("driver") or {}
        if str(drv.get("source") or "").strip().lower() != "cost_pool":
            continue
        ref = str(drv.get("ref") or "").strip()
        if (pid and ref == pid) or (not pid and pname and ref == pname):
            out.append(st)
    return out


def _pool_downstream_opex_categories(pool: Mapping[str, Any], assumptions: Mapping[str, Any] | None) -> list[Mapping[str, Any]]:
    """Operating Expense categories whose active calculation consumes this pool."""
    pid = str((pool or {}).get("series_id") or "").strip()
    pname = str((pool or {}).get("name") or "").strip()
    cats = (((assumptions or {}).get("nie_detail") or {}).get("categories") or [])
    out: list[Mapping[str, Any]] = []
    for cat0 in cats:
        cat = cat0 or {}
        calc = dict(cat.get("calculation") or {})
        if str(calc.get("kind") or "entered").strip().lower() != "cost_pool":
            continue
        ref = str(calc.get("ref") or "").strip()
        if (pid and ref == pid) or (not pid and pname and ref == pname):
            out.append(cat)
    return out


def _category_by_link(assumptions: Mapping[str, Any] | None, sid: str = "", name: str = "") -> Mapping[str, Any] | None:
    cats = (((assumptions or {}).get("nie_detail") or {}).get("categories") or [])
    sid = str(sid or "").strip(); name = str(name or "").strip()
    if sid:
        hits = [c or {} for c in cats if str((c or {}).get("series_id") or "").strip() == sid]
    else:
        hits = [c or {} for c in cats if name and str((c or {}).get("name") or "").strip() == name]
    return hits[0] if len(hits) == 1 else None


def _auc_upstream_opex_categories(assumptions: Mapping[str, Any] | None, auc_series_id: str) -> list[Mapping[str, Any]]:
    """Operating Expense categories that feed acquisition economics for one AUC Series."""
    a = assumptions or {}
    target = None
    for _name, raw in (a.get("cac_feeds") or {}).items():
        feed = raw or {}
        if str(feed.get("series_id") or "").strip() == str(auc_series_id or "").strip():
            target = feed; break
    if target is None:
        return []
    out: list[Mapping[str, Any]] = []
    seen: set[int] = set()

    # Follow only operands that actually affect the AUC roll-forward. Driver_specs may also
    # contain spend/audit operands that are unused by a channel's selected acquisition equation;
    # those must not manufacture a false cycle.
    relevant: list[tuple[Mapping[str, Any], set[str]]] = [
        (target, {"attrition_rate", "attrition_avg_ticket"}),
    ]
    method_keys = {
        "pool_conversion": {"pool", "conversion_rate", "avg_auc_per_customer"},
        "spend_cac": {"spend", "cac", "avg_auc_per_customer"},
        "fte_productivity": {"ftes", "per_fte", "avg_auc_per_customer"},
        "explicit": {"new_customers", "avg_auc_per_customer"},
    }
    for ch0 in target.get("channels") or []:
        ch = ch0 or {}
        relevant.append((ch, method_keys.get(str(ch.get("method") or ""), set())))

    for owner, keys in relevant:
        specs = (owner or {}).get("driver_specs") or {}
        for key in keys:
            sp = specs.get(key) or {}
            if str(sp.get("source") or "").strip().lower() != "link":
                continue
            link = sp.get("link") or {}
            if str(link.get("kind") or "").strip() != "operating_expense_category":
                continue
            cat = _category_by_link(a, str(link.get("series_id") or ""), str(link.get("name") or ""))
            if cat is not None and id(cat) not in seen:
                seen.add(id(cat)); out.append(cat)
    return out


def _opex_depends_on_downstream_fee(category: Mapping[str, Any], downstream: Sequence[Mapping[str, Any]]) -> bool:
    """Whether an Opex category observes fee output/quantity produced from this same pool."""
    if not downstream:
        return False
    quantity_ids = {str((st or {}).get("quantity_series_id") or "").strip()
                    for st in downstream if str((st or {}).get("quantity_series_id") or "").strip()}
    for raw in (category or {}).get("linked_components") or []:
        comp = raw or {}
        drv = str(comp.get("driver") or "").strip().lower()
        # These aggregates include every fee stream, including the downstream cost-recovery fee.
        if drv in {"fee_income", "noninterest_income"}:
            return True
        if drv == "fee_stream_quantity":
            sid = str(comp.get("series_id") or "").strip()
            if sid and sid in quantity_ids:
                return True
    return False


def _validate_no_dependency_cycle(pool: Mapping[str, Any], assumptions: Mapping[str, Any] | None) -> None:
    """Fail closed only when this pool participates in an actual observable dependency loop.

    Valid: CAC -> AUC -> eligible cost pool -> fee revenue.
    Invalid examples:
      Opex -> pool -> fee revenue -> same Opex
      Opex -> CAC -> AUC -> pool -> fee revenue -> same Opex
    """
    a = assumptions or {}
    downstream_fees = _pool_downstream_fee_streams(pool, a)
    downstream_opex = _pool_downstream_opex_categories(pool, a)
    if not downstream_fees and not downstream_opex:
        return

    candidate_categories: list[Mapping[str, Any]] = []
    for comp in (pool or {}).get("components") or []:
        c = comp or {}
        kind = str(c.get("kind") or "").strip()
        if kind == "operating_expense_category":
            cat = _category_by_link(a, str(c.get("series_id") or ""), str(c.get("name") or ""))
            if cat is not None:
                candidate_categories.append(cat)
        elif kind == "balance_derived_cost" and str(c.get("source_kind") or "managed_notional").strip().lower() == "managed_notional":
            candidate_categories.extend(_auc_upstream_opex_categories(a, str(c.get("source_series_id") or "")))

    seen: set[int] = set()
    for cat in candidate_categories:
        if id(cat) in seen:
            continue
        seen.add(id(cat))
        if any(cat is x for x in downstream_opex):
            raise ValueError(
                "cost pool would create a circular dependency through its downstream Operating Expense category")
        if _opex_depends_on_downstream_fee(cat, downstream_fees):
            raise ValueError(
                "cost pool would create a circular dependency through fee revenue/quantity and Operating Expense")


def _allocation(comp: Mapping[str, Any], i: int) -> float:
    raw_alloc = comp.get("allocation_pct")
    if raw_alloc is None:
        raw_alloc = comp.get("weight", 1.0)  # compatibility with early hand-authored drafts
    try:
        alloc = float(raw_alloc)
    except (TypeError, ValueError):
        raise ValueError(f"cost pool component {i} allocation_pct must be numeric")
    if alloc < 0.0 or alloc > 1.0:
        raise ValueError(f"cost pool component {i} allocation_pct must be between 0 and 1")
    return alloc


def _canonical_managed_notional_monthly_end(
        assumptions: Mapping[str, Any] | None, source_series_id: str,
        n_periods: int, ppy: int, *, growth_context=None) -> tuple[float, list[float]]:
    """Resolve one canonical monthly managed-notional balance path.

    The first return value is the balance immediately before modeled month 1.  It supplies
    the unambiguous first-month period-average convention: (beginning balance + M1 EOP) / 2.
    """
    a = assumptions or {}
    ident = str(source_series_id or "").strip()
    if not ident:
        raise ValueError("balance-derived cost component requires source_series_id")
    ppy = int(ppy)
    if ppy not in (1, 4, 12) or 12 % ppy:
        raise ValueError(f"unsupported cadence periods_per_year={ppy} for balance-derived cost")
    n_months = int(n_periods) * (12 // ppy)

    # Fail with a semantic error rather than allowing a customer-count Series to masquerade
    # as a monetary balance.  r69 introduced first-class CAC count Series alongside AUC; the
    # two identities are intentionally distinct even when they share the same feed label.
    count_hits = [str(name or ident) for name, raw in (a.get("cac_feeds") or {}).items()
                  if str((raw or {}).get("customer_count_series_id") or "").strip() == ident]
    if count_hits:
        raise ValueError(
            f"managed-notional balance source {ident!r} is a CAC customer-count Series "
            f"({', '.join(count_hits)}); expected the feed's canonical AUC / managed-notional series_id")

    catalog = cost_pool_balance_source_catalog(a)
    hits = [m for m in catalog if str(m.get("series_id") or "").strip() == ident]
    if len(hits) != 1:
        raise ValueError(
            f"managed-notional balance source {ident!r} resolved to {len(hits)} canonical monthly AUC sources; expected exactly one")
    feed_name = str(hits[0].get("feed") or hits[0].get("name") or "")
    feed = ((a.get("cac_feeds") or {}).get(feed_name) or {})
    from .cac_feeder import cac_auc_rollforward
    r = cac_auc_rollforward(feed, int(n_periods), ppy, assumptions=a, growth_context=growth_context)
    monthly = [float(x or 0.0) for x in (r.get("auc_end_by_month") or [])[:n_months]]
    if len(monthly) != n_months:
        raise ValueError(
            f"managed-notional balance source {ident!r} produced {len(monthly)} canonical months; expected {n_months}")
    return float(feed.get("beginning_auc") or 0.0), monthly


def _balance_derived_series(comp: Mapping[str, Any], assumptions: Mapping[str, Any] | None,
                            n_periods: int, ppy: int, *, growth_context=None) -> list[float]:
    source_kind = str(comp.get("source_kind") or "managed_notional").strip().lower()
    if source_kind not in _BALANCE_SOURCE_KINDS:
        raise ValueError(
            f"unsupported balance-derived cost source_kind {source_kind!r}; expected managed_notional")
    source_semantic = str(comp.get("source_semantic") or "").strip().lower()
    if source_semantic and source_semantic != "auc_end":
        raise ValueError("balance-derived cost source_semantic must be auc_end")
    source_owner = str(comp.get("source_owner_module") or "").strip().lower()
    if source_owner and source_owner != "customer_acquisition":
        raise ValueError("balance-derived cost source_owner_module must be customer_acquisition")
    source_sid = str(comp.get("source_series_id") or "").strip()
    beginning, monthly_end = _canonical_managed_notional_monthly_end(
        assumptions, source_sid, n_periods, ppy, growth_context=growth_context)

    from .balance_measures import normalize_balance_measure, monthly_balance_measure_series
    try:
        measure = normalize_balance_measure(comp.get("measure"), default="period_average")
    except ValueError as e:
        raise ValueError("balance-derived cost measure must be period_end or period_average") from e

    rate_period = str(comp.get("rate_period") or "year").strip().lower()
    if rate_period not in _RATE_PERIOD_MONTHS:
        raise ValueError("balance-derived cost rate_period must be month/quarter/year")
    rate_spec = dict(comp.get("rate_spec") or {
        "source": "entered", "trajectory": "flat", "value": 0.0})
    if str(rate_spec.get("source") or "entered").strip().lower() != "entered":
        raise ValueError("balance-derived cost rate_spec must be an entered dimensionless Series")

    from .series import resolve_entered_series
    monthly_rate = resolve_entered_series(
        rate_spec, len(monthly_end), 12, context=growth_context, default_value=0.0)
    divisor = float(_RATE_PERIOD_MONTHS[rate_period])
    monthly_base = monthly_balance_measure_series(beginning, monthly_end, measure)
    monthly_cost = [base * float(monthly_rate[mi] or 0.0) / divisor
                    for mi, base in enumerate(monthly_base)]

    width = 12 // int(ppy)
    return [float(sum(monthly_cost[i * width:(i + 1) * width]))
            for i in range(int(n_periods))]


def cost_pool_series(pool: Mapping[str, Any] | None, assumptions: Mapping[str, Any] | None,
                     n_periods: int, ppy: int = 4, *, growth_context=None) -> list[float]:
    """Resolve one eligible-cost pool to native-period dollar *flows*.

    No component posts expense here. Linked modeled costs remain owned by their source module;
    entered and balance-derived components are pricing-base assumptions only.
    """
    pool = pool or {}
    n, ppy = int(n_periods), int(ppy)
    _validate_no_dependency_cycle(pool, assumptions)
    comps = pool.get("components") or []
    if not isinstance(comps, list):
        raise ValueError("cost pool components must be a list")
    total = [0.0] * n
    seen_linked: set[tuple[str, str]] = set()
    seen_owned_ids: set[str] = set()
    from .series import resolve_linked_series

    for i, comp in enumerate(comps):
        comp = comp or {}
        kind = str(comp.get("kind") or "").strip()
        if kind not in _VALID_COMPONENT_KINDS:
            raise ValueError(f"cost pool component {i} has unsupported kind {kind!r}")
        alloc = _allocation(comp, i)

        if kind in _LINKED_COMPONENT_KINDS:
            sid = str(comp.get("series_id") or "").strip()
            if not sid:
                raise ValueError(f"cost pool component {i} requires series_id")
            token = (kind, sid)
            if token in seen_linked:
                raise ValueError(f"cost pool component {i} duplicates {kind}:{sid}")
            seen_linked.add(token)
            arr = resolve_linked_series(
                assumptions or {}, {"kind": kind, "series_id": sid, "aggregation": "sum"},
                n, ppy, context=growth_context)
        elif kind == "assumption_cost_base":
            sid = str(comp.get("series_id") or "").strip()
            if not sid:
                raise ValueError(f"cost pool component {i} assumption_cost_base requires stable series_id")
            if sid in seen_owned_ids:
                raise ValueError(f"cost pool component {i} duplicates cost-pool component series_id {sid!r}")
            seen_owned_ids.add(sid)
            fs = comp.get("flow_spec")
            if fs is None:
                raise ValueError(f"cost pool component {i} assumption_cost_base requires flow_spec")
            from .periodic_flows import resolve_periodic_flow
            arr = resolve_periodic_flow(fs, n, ppy, context=growth_context)
        else:  # balance_derived_cost
            sid = str(comp.get("series_id") or "").strip()
            if not sid:
                raise ValueError(f"cost pool component {i} balance_derived_cost requires stable series_id")
            if sid in seen_owned_ids:
                raise ValueError(f"cost pool component {i} duplicates cost-pool component series_id {sid!r}")
            seen_owned_ids.add(sid)
            arr = _balance_derived_series(
                comp, assumptions, n, ppy, growth_context=growth_context)

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
    # Validate component-owned identities across pools as well as within each pool.
    cost_pool_component_series_ids(assumptions)
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
