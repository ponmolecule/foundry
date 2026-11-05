"""Canonical fixed-asset / CAPEX resolver for Foundry v2.

The projection engines consume native-period series.  This module owns the accounting
semantics for the two active authoring methodologies:

* ``formula_level`` — directly resolves the period-end fixed-asset level from an entered
  base plus compatible linked Series × multipliers. The level basis is explicit (gross or net
  PP&E); new authoring defaults to gross so depreciation does not manufacture replacement CAPEX.
* ``schedule`` — reconstructs PP&E from asset/CAPEX vintages, useful lives and depreciation.

Historical ``premises_equipment`` + ``premises_depreciation_annual`` remains a separate
backward-compatibility fallback until a saved model explicitly opts into Formula / level.
The schedule path currently exposes straight-line depreciation while retaining a method
field in the schema so future schedule methods do not require a data-model migration.
"""

from __future__ import annotations

import math
from copy import deepcopy

from typing import Any, Dict, Iterable, List, Mapping, Tuple


def _f(v, default=0.0):
    try:
        return float(v if v is not None else default)
    except (TypeError, ValueError):
        return float(default)


def _i(v, default=0):
    try:
        return int(v if v is not None else default)
    except (TypeError, ValueError):
        return int(default)



_LEVEL_RATE_FREQ = {"year": 1.0, "quarter": 4.0, "month": 12.0}

# Canonical stable Series IDs for fixed-asset Formula / level outputs. These IDs
# identify economic quantities, not engagement-specific labels. Formula-level linked
# component ``component_id`` values are themselves stable Series IDs for the
# component contribution.
FIXED_ASSET_GROSS_SERIES_ID = "bank.fixed_assets.gross"
FIXED_ASSET_ACCUM_DEP_SERIES_ID = "bank.fixed_assets.accumulated_depreciation"
FIXED_ASSET_NET_SERIES_ID = "bank.fixed_assets.net"
FIXED_ASSET_FORMULA_BASE_SERIES_ID = "bank.fixed_assets.formula_level.base"


def _formula_level_config(fixed_assets: Mapping[str, Any] | None) -> dict:
    fa = dict(fixed_assets or {})
    raw = fa.get("formula_level")
    if not isinstance(raw, Mapping):
        raise ValueError("fixed_assets.formula_level must be an object")
    return dict(raw)


def _resolve_entered_level(spec: Mapping[str, Any] | None, n_periods: int, ppy: int,
                            *, growth_context=None, default_value: float = 0.0) -> list[float]:
    """Resolve a stock/level assumption without inventing a natural time unit."""
    from .series import normalize_series_spec, resolve_entered_series
    ns = normalize_series_spec(spec, default_value=default_value)
    if ns["source"] != "entered":
        raise ValueError("fixed-asset level and multiplier trajectories must be entered Series")
    return [float(x or 0.0) for x in resolve_entered_series(
        ns, int(n_periods), int(ppy), context=growth_context, default_value=default_value)]


def _natural_period_factor(period: Any, ppy: int) -> float:
    period = str(period or "").strip().lower()
    if period not in _LEVEL_RATE_FREQ:
        raise ValueError(f"fixed-asset amount/rate period {period!r} unsupported; expected month/quarter/year")
    ppy = int(ppy)
    if ppy not in (1, 4, 12):
        raise ValueError(f"unsupported cadence periods_per_year={ppy}")
    # An authored amount/rate is stated per its natural period.  Convert linearly to one
    # engine period exactly once: 12%/year -> 1%/month; 1%/month -> 3%/quarter.
    return _LEVEL_RATE_FREQ[period] / float(ppy)


def _resolve_natural_period_series(spec: Mapping[str, Any] | None, n_periods: int, ppy: int,
                                   *, growth_context=None, default_value: float = 0.0) -> list[float]:
    """Resolve Flat/Growth/Explicit authored values, then periodize their natural unit.

    ``period`` owns the economic unit (Month / Quarter / Year).  Explicit ``cadence``
    independently owns how often the authored value may change.
    """
    raw = dict(spec or {})
    factor = _natural_period_factor(raw.get("period"), int(ppy))
    vals = _resolve_entered_level(raw, int(n_periods), int(ppy),
                                  growth_context=growth_context, default_value=default_value)
    return [float(v or 0.0) * factor for v in vals]


def _resolve_natural_period_flow(spec: Mapping[str, Any] | None, n_periods: int, ppy: int,
                                 *, growth_context=None, default_value: float = 0.0) -> list[float]:
    """Resolve a depreciation flow, including source schedules finer than the engine.

    Most Fixed Asset Formula / level inputs are stocks or rates and therefore use the
    ordinary Series rule that rejects a source cadence finer than the model cadence.
    Entered depreciation is different: it is an additive expense flow.  A monthly
    depreciation schedule in a quarterly model is representable without approximation by
    resolving the authored amounts on a conceptual monthly grid and summing three months
    into each engine quarter, just as recurring Operating Expense schedules do.

    Preserve the historical resolver for flat/growth paths and explicit schedules that are
    no finer than the engine.  Only the previously-unrepresentable fine-cadence case takes
    the monthly aggregation path.
    """
    raw = dict(spec or {})
    ppy = int(ppy)
    n = int(n_periods)
    cadence = str(raw.get("cadence") or "year").strip().lower()
    source_freq = {"year": 1, "quarter": 4, "month": 12,
                   "model_period": ppy}.get(cadence)
    if (str(raw.get("trajectory") or raw.get("mode") or "flat").strip().lower() != "explicit"
            or source_freq is None or source_freq <= ppy):
        return _resolve_natural_period_series(
            raw, n, ppy, growth_context=growth_context, default_value=default_value)

    if ppy not in (1, 4, 12) or 12 % ppy:
        raise ValueError(f"unsupported cadence periods_per_year={ppy}")
    months_per_engine_period = 12 // ppy
    monthly = _resolve_entered_level(
        raw, n * months_per_engine_period, 12,
        growth_context=growth_context, default_value=default_value)
    month_factor = _natural_period_factor(raw.get("period"), 12)
    monthly_flows = [float(v or 0.0) * month_factor for v in monthly]
    return [sum(monthly_flows[i:i + months_per_engine_period])
            for i in range(0, len(monthly_flows), months_per_engine_period)]




def _formula_component_display_name(component: Mapping[str, Any] | None, index: int,
                                    assumptions: Mapping[str, Any] | None = None,
                                    normalized_driver: Mapping[str, Any] | None = None) -> str:
    """Human-facing name for a Formula / level component.

    Early releases seeded the literal placeholder ``Linked asset component``.  That is
    implementation vocabulary, not a useful balance-sheet label.  Preserve an authored
    name, but replace legacy/generic placeholders with a stable description derived from
    the linked Series when possible.
    """
    c = component or {}
    raw = str(c.get("name") or "").strip()
    generic = (not raw or raw == "Linked asset component" or
               (raw.lower().startswith("linked component ") and raw.split()[-1].isdigit()))
    if not generic:
        return raw
    ns = normalized_driver or {}
    link = dict(ns.get("link") or ((c.get("driver_spec") or {}).get("link") or {}))
    kind = str(link.get("kind") or "").strip()
    sid = str(link.get("series_id") or "").strip()
    if kind == "workforce_role_count" and sid:
        try:
            from .opex_extensions import workforce_count_catalog
            hit = next((x for x in workforce_count_catalog(assumptions or {})
                        if str(x.get("series_id") or "") == sid), None)
            if hit:
                return f"Fixed assets · {str(hit.get('role') or sid)}"
        except Exception:
            pass
    return f"Fixed-asset component {index + 1}"

def _monthly_workforce_driver(ns, assumptions, months, source_ppy, context):
    """Preserve native hire windows and capacity-feed cadence on a monthly grid."""
    from .workforce import workforce_role_count_series, workforce_capacity_monthly
    wf = (assumptions.get("nie_detail") or {}).get("workforce") or {}
    sid = (ns.get("link") or {}).get("series_id")
    roles = list(wf.get("roles") or [])
    if sid != wf.get("total_count_series_id"):
        roles = [r for r in roles if r.get("series_id") == sid]
        if len(roles) != 1:
            raise ValueError("Fixed-asset workforce source is missing or ambiguous")
    span = 12 // source_ppy
    native_cadence = {1:"year",4:"quarter",12:"month"}[source_ppy]
    out = [0.0] * months
    def remap(obj):
        if isinstance(obj, dict):
            for k,v in list(obj.items()):
                if k in ("cadence", "period") and v == "model_period": obj[k] = native_cadence
                else: remap(v)
        elif isinstance(obj,list):
            for v in obj: remap(v)
    for raw in roles:
        if raw.get("activation"):
            raise ValueError("Fixed-asset links cannot consume metric-triggered workforce")
        role = deepcopy(raw)
        remap(role)
        hire = (int(raw.get("hire_period") or 1)-1)*span+1
        end = raw.get("end_period")
        end = int(end)*span if end not in (None, "") else months
        role["hire_period"] = hire
        role["end_period"] = end
        if raw.get("capacity_count"):
            vals = workforce_capacity_monthly(raw, months, assumptions=assumptions,
                growth_context=context, source_ppy=source_ppy)["counts"]
            vals = [v if hire <= i <= end else 0.0 for i,v in enumerate(vals,1)]
        else:
            vals = workforce_role_count_series(role, months, 12,
                growth_context=context, assumptions=assumptions)
        out = [a+b for a,b in zip(out,vals)]
    return out


def fixed_asset_formula_level(fixed_assets: Mapping[str, Any] | None,
                              assumptions: Mapping[str, Any] | None,
                              n_periods: int, ppy: int, *, growth_context=None, _source_ppy=None) -> Dict[str, Any]:
    """Resolve the Formula / level fixed-asset methodology.

    The authored period-end fixed-asset level is composed from an entered base plus zero
    or more safe linked driver Series × entered multipliers::

        fixed-asset level = base level + Σ(driver Series × multiplier)

    ``level_basis`` makes the accounting meaning explicit:

    * ``gross`` (default) — the authored level is gross PP&E. Depreciation rolls into
      accumulated depreciation and therefore reduces net PP&E. A flat gross level does
      **not** create replacement CAPEX. Gross declines relieve accumulated depreciation
      pro rata so the implied disposal occurs at carrying value rather than inventing a gain.
    * ``net`` — the authored level is an explicit net-PP&E target. This preserves r119's
      deliberate target-net behavior for models that actually want replacement CAPEX; gross
      PP&E is reconciled as ``net + accumulated depreciation`` and implied CAPEX is
      ``Δnet + depreciation``.

    ``opening_net`` is retained only as an r119 read-compatibility alias for
    ``opening_level``. Missing ``level_basis`` defaults to ``gross`` in r120 because r119's
    hidden net-basis assumption was the accounting bug corrected by this release.
    """
    n, ppy = int(n_periods), int(ppy)
    if n < 0 or ppy <= 0:
        raise ValueError("n_periods must be >= 0 and ppy must be > 0")
    cfg = _formula_level_config(fixed_assets)
    # New transforms are evaluated on the monthly economic grid, before sampling
    # closing stocks and summing flows. Old configurations retain their exact path.
    enhanced = (str((cfg.get("depreciation") or {}).get("kind")) == "component_rates"
                or any(c.get("lag_months") or c.get("driver_divisor", 1) != 1
                       or c.get("driver_rounding", "none") != "none"
                       for c in cfg.get("components") or []))
    if enhanced and ppy != 12:
        if ppy not in (1, 4):
            raise ValueError("fixed-asset transforms require monthly, quarterly or annual cadence")
        span = 12 // ppy
        monthly_fa = deepcopy(fixed_assets)
        def native_paths(obj):
            if isinstance(obj, dict):
                for k,v in list(obj.items()):
                    if k in ("cadence", "period") and v == "model_period":
                        obj[k] = {1:"year",4:"quarter"}[ppy]
                    else:
                        native_paths(v)
            elif isinstance(obj,list):
                for v in obj: native_paths(v)
        native_paths(monthly_fa)
        result = fixed_asset_formula_level(monthly_fa, assumptions, n * span, 12,
                                          growth_context=growth_context, _source_ppy=ppy)
        for key in ("gross", "accumulated_depreciation", "net"):
            v = result[key]
            result[key] = [v[0]] + [v[t] for t in range(span, len(v), span)]
        for key in ("depreciation_expense", "capex"):
            v = result[key]
            result[key] = [v[0]] + [sum(v[t:t+span]) for t in range(1, len(v), span)]
        fl = result["formula_level"]
        fl["base"] = fl["base"][span-1::span]
        rr = fl["depreciation_rate_per_engine_period"]
        fl["depreciation_rate_per_engine_period"] = [sum(rr[t:t+span]) for t in range(0,len(rr),span)]
        v = fl["accumulated_depreciation_relief"]
        fl["accumulated_depreciation_relief"] = [v[0]] + [sum(v[t:t+span]) for t in range(1,len(v),span)]
        for c in fl["components"]:
            for key in ("driver", "raw_driver", "multiplier", "amount"):
                c[key] = c[key][span-1::span]
            c["depreciation"] = [sum(c["depreciation"][t:t+span])
                                  for t in range(0,len(c["depreciation"]),span)]
        return result
    basis = str(cfg.get("level_basis") or "gross").strip().lower()
    if basis not in {"gross", "net"}:
        raise ValueError("fixed_assets.formula_level.level_basis must be gross or net")
    opening_level = _f(cfg.get("opening_level", cfg.get("opening_net", 0.0)), 0.0)
    opening_accum = _f(cfg.get("opening_accumulated_depreciation"), 0.0)
    if opening_level < 0 or opening_accum < 0:
        raise ValueError("Formula / level opening balances must be non-negative")
    if basis == "gross" and opening_accum > opening_level + 1e-9:
        raise ValueError("Formula / level opening accumulated depreciation cannot exceed opening gross PP&E")

    base = _resolve_entered_level(cfg.get("base_spec") or {"source":"entered","trajectory":"flat","value":0.0},
                                  n, ppy, growth_context=growth_context)
    target = list(base)
    component_rows = []
    from .series import normalize_series_spec, resolve_series_spec
    for i, raw in enumerate(cfg.get("components") or []):
        if not isinstance(raw, Mapping):
            raise ValueError(f"fixed_assets.formula_level.components[{i}] must be an object")
        comp = dict(raw)
        dspec = comp.get("driver_spec")
        ns = normalize_series_spec(dspec, default_value=0.0)
        if ns["source"] not in {"link", "entered"}:
            raise ValueError(f"fixed_assets.formula_level.components[{i}].driver_spec must be an entered or linked Series")
        if _source_ppy and _source_ppy != 12 and (ns.get("link") or {}).get("kind") == "workforce_role_count":
            drivers = _monthly_workforce_driver(ns, assumptions or {}, n, _source_ppy, growth_context)
        else:
            drivers = resolve_series_spec(ns, assumptions or {}, n, ppy,
                                          context=growth_context, default_value=0.0)
        raw_drivers = [float(v or 0) for v in drivers]
        lag = comp.get("lag_months", 0)
        divisor = float(comp.get("driver_divisor", 1))
        initial = float(comp.get("initial_driver", 0))
        rounding = comp.get("driver_rounding", "none")
        if (not isinstance(lag, int) or isinstance(lag, bool) or lag < 0 or lag > 1200
                or not math.isfinite(divisor) or divisor <= 0
                or not math.isfinite(initial) or initial < 0
                or rounding not in ("none", "floor", "ceil", "nearest")):
            raise ValueError("Invalid fixed-asset driver timing or grouping")
        drivers = ([initial] * min(lag, n) + raw_drivers[:max(0,n-lag)]) if lag else raw_drivers
        drivers = [v / divisor for v in drivers]
        if rounding != "none":
            fn = {"floor": math.floor, "ceil": math.ceil,
                  "nearest": lambda v: math.floor(v + 0.5)}[rounding]
            drivers = [float(fn(v)) for v in drivers]
        mults = _resolve_entered_level(comp.get("multiplier_spec") or {"source":"entered","trajectory":"flat","value":0.0},
                                       n, ppy, growth_context=growth_context)
        values = [float(d or 0.0) * float(m or 0.0) for d, m in zip(drivers, mults)]
        target = [float(a or 0.0) + float(b or 0.0) for a, b in zip(target, values)]
        component_rows.append({
            "component_id": str(comp.get("component_id") or ""),
            "name": _formula_component_display_name(comp, i, assumptions, ns),
            "driver_series_id": str((ns.get("link") or {}).get("series_id") or ""),
            "driver_kind": str((ns.get("link") or {}).get("kind") or ""),
            "raw_driver": raw_drivers,
            "driver": [float(x or 0.0) for x in drivers],
            "depreciation": [0.0] * n,
            "multiplier": [float(x or 0.0) for x in mults],
            "amount": values,
        })

    if any(float(v or 0.0) < -1e-9 for v in target):
        raise ValueError("Formula / level fixed-asset level cannot be negative")
    target = [max(0.0, float(v or 0.0)) for v in target]

    depcfg = dict(cfg.get("depreciation") or {})
    kind = str(depcfg.get("kind") or "entered").strip().lower()
    if kind == "rate_of_level":
        rs = dict(depcfg.get("rate_spec") or {
            "source":"entered","trajectory":"flat","value":0.0,"period":"year"})
        rates = _resolve_natural_period_series(rs, n, ppy, growth_context=growth_context)
        if any(r < -1e-12 for r in rates):
            raise ValueError("Formula / level depreciation rate cannot be negative")
        dep_authored = [float(level or 0.0) * float(rate or 0.0)
                        for level, rate in zip(target, rates)]
    elif kind == "component_rates":
        if basis != "gross":
            raise ValueError("Component depreciation requires Gross PP&E")
        def component_dep(amounts, spec):
            # r464's editor displayed Year before persisting a new rate's period.
            # Missing/empty component-rate periods therefore mean the displayed Year;
            # explicit invalid periods still fail validation.
            rate_spec = dict(spec or {"source":"entered", "trajectory":"flat", "value":0})
            if not rate_spec.get("period"):
                rate_spec["period"] = "year"
            rr = _resolve_natural_period_series(rate_spec,
                n, ppy, growth_context=growth_context)
            if any(not math.isfinite(r) or r < 0 for r in rr):
                raise ValueError("Component depreciation rates must be finite and non-negative")
            return [v*r for v,r in zip(amounts,rr)]
        dep_authored = component_dep(base, depcfg.get("base_rate_spec"))
        for comp, row in zip(cfg.get("components") or [], component_rows):
            row["depreciation"] = component_dep(row["amount"], comp.get("depreciation_rate_spec"))
            dep_authored = [a+b for a,b in zip(dep_authored,row["depreciation"])]
        rates = []
    elif kind == "entered":
        es = dict(depcfg.get("amount_spec") or {
            "source":"entered","trajectory":"flat","value":0.0,"period":"year"})
        dep_authored = _resolve_natural_period_flow(es, n, ppy, growth_context=growth_context)
        if any(v < -1e-9 for v in dep_authored):
            raise ValueError("Formula / level entered depreciation cannot be negative")
        rates = []
    else:
        raise ValueError("fixed_assets.formula_level.depreciation.kind must be entered, rate_of_level or component_rates")

    dep = [0.0] * (n + 1)
    capex = [0.0] * (n + 1)
    accum_relief = [0.0] * (n + 1)

    if basis == "net":
        net = [opening_level] + target
        accum = [opening_accum]
        for t in range(1, n + 1):
            dep[t] = float(dep_authored[t - 1] or 0.0)
            accum.append(float(accum[-1]) + dep[t])
            capex[t] = float(net[t]) - float(net[t - 1]) + dep[t]
        gross = [float(net[t]) + float(accum[t]) for t in range(n + 1)]
    else:
        gross = [opening_level] + target
        accum = [opening_accum]
        net = [max(0.0, opening_level - opening_accum)]
        for t in range(1, n + 1):
            prev_gross = float(gross[t - 1])
            curr_gross = float(gross[t])
            prev_accum = float(accum[-1])
            # Direct gross-level declines imply disposal of the same proportion of the
            # existing asset pool. Relieve the same proportion of accumulated depreciation
            # so the balance-sheet reduction occurs at carrying value rather than at cost.
            relief = 0.0
            if curr_gross < prev_gross - 1e-12 and prev_gross > 1e-12:
                relief = prev_accum * min(1.0, max(0.0, (prev_gross - curr_gross) / prev_gross))
            accum_before_dep = max(0.0, prev_accum - relief)
            max_dep = max(0.0, curr_gross - accum_before_dep)
            dep[t] = min(float(dep_authored[t - 1] or 0.0), max_dep)
            accum.append(accum_before_dep + dep[t])
            accum_relief[t] = relief
            net.append(max(0.0, curr_gross - accum[t]))
            # In gross-basis Formula / level, the signed change in authored gross PP&E is
            # the implied additions/(disposals) at cost. Depreciation never creates CAPEX.
            capex[t] = curr_gross - prev_gross

    return {
        "gross": gross,
        "accumulated_depreciation": accum,
        "net": net,
        "depreciation_expense": dep,
        "capex": capex,
        "preopening_capex": 0.0,
        "asset_rows": [],
        "formula_level": {
            "level_basis": basis,
            "opening_level": opening_level,
            "opening_accumulated_depreciation": opening_accum,
            "base_name": str(cfg.get("base_name") or "Base asset level"),
            "base_series_id": FIXED_ASSET_FORMULA_BASE_SERIES_ID,
            "base": [float(x or 0.0) for x in base],
            "components": component_rows,
            "depreciation_kind": kind,
            "depreciation_rate_per_engine_period": [float(x or 0.0) for x in rates],
            "accumulated_depreciation_relief": [float(x or 0.0) for x in accum_relief],
        },
    }


def fixed_asset_schedule(fixed_assets: dict | None, n_periods: int, ppy: int) -> Dict[str, List[float]]:
    """Resolve a fixed-asset schedule into native-cadence series.

    Series include an opening position at index 0, followed by model periods 1..N.

    New / CAPEX asset schema (all dollar fields are raw dollars)::

        {"name": "Furniture", "cost": 350000, "in_service_period": 0,
         "useful_life_years": 7, "method": "straight_line", "residual_value": 0}

    ``in_service_period=0`` means owned/placed in service at opening; depreciation begins
    in model period 1.  A positive value means the asset is placed in service during that
    model period and receives a full period of straight-line depreciation in that period.

    Existing/opening assets can instead provide::

        {"name": "Existing PP&E", "opening_gross_cost": 800000,
         "opening_accumulated_depreciation": 300000, "remaining_life_years": 4}

    They depreciate the opening NBV (subject to residual value) over the remaining life.
    """
    n = int(n_periods)
    ppy = int(ppy)
    if n < 0 or ppy <= 0:
        raise ValueError("n_periods must be >= 0 and ppy must be > 0")

    gross = [0.0] * (n + 1)
    accum = [0.0] * (n + 1)
    dep = [0.0] * (n + 1)
    capex = [0.0] * (n + 1)
    preopen_capex = 0.0
    rows = []

    for idx, asset in enumerate((fixed_assets or {}).get("assets") or []):
        if not isinstance(asset, dict):
            continue
        method = str(asset.get("method") or "straight_line").strip().lower()
        if method != "straight_line":
            raise ValueError(f"fixed_assets.assets[{idx}].method {method!r} unsupported; use straight_line")
        residual = max(0.0, _f(asset.get("residual_value"), 0.0))

        is_existing = asset.get("opening_gross_cost") is not None or asset.get("opening_accumulated_depreciation") is not None
        if is_existing:
            g0 = max(0.0, _f(asset.get("opening_gross_cost"), asset.get("cost", 0.0)))
            residual = min(residual, g0)
            ad0 = min(g0, max(0.0, _f(asset.get("opening_accumulated_depreciation"), 0.0)))
            nbv0 = max(0.0, g0 - ad0)
            life_years = _f(asset.get("remaining_life_years"), asset.get("useful_life_years", 0.0))
            life_periods = max(1, int(round(life_years * ppy))) if nbv0 > residual else 1
            depreciable = max(0.0, nbv0 - residual)
            per_dep = depreciable / life_periods if depreciable > 0 else 0.0
            gross[0] += g0
            accum[0] += ad0
            for t in range(1, n + 1):
                gross[t] += g0
                d = per_dep if t <= life_periods else 0.0
                dep[t] += d
                accum[t] += min(g0 - residual, ad0 + per_dep * min(t, life_periods))
            rows.append({"name": asset.get("name") or f"Asset {idx+1}", "type": "existing",
                         "opening_gross": g0, "opening_accumulated_depreciation": ad0,
                         "remaining_life_periods": life_periods, "depreciation_per_period": per_dep})
            continue

        cost = max(0.0, _f(asset.get("cost"), 0.0))
        residual = min(residual, cost)
        start = _i(asset.get("in_service_period"), 0)
        life_years = _f(asset.get("useful_life_years"), 0.0)
        life_periods = max(1, int(round(life_years * ppy))) if cost > residual else 1
        depreciable = max(0.0, cost - residual)
        per_dep = depreciable / life_periods if depreciable > 0 else 0.0
        if start == 0:
            preopen_capex += cost
            capex[0] += cost
        elif 1 <= start <= n:
            capex[start] += cost

        for t in range(0, n + 1):
            active = (start == 0 and t >= 0) or (start > 0 and t >= start)
            if not active:
                continue
            gross[t] += cost
            if t == 0:
                periods_dep = 0
            elif start == 0:
                periods_dep = min(t, life_periods)
            else:
                periods_dep = min(t - start + 1, life_periods)
            ad = min(depreciable, per_dep * max(0, periods_dep))
            accum[t] += ad
            if t >= 1 and ((start == 0 and t <= life_periods) or (start > 0 and start <= t < start + life_periods)):
                dep[t] += per_dep

        rows.append({"name": asset.get("name") or f"Asset {idx+1}", "type": "new",
                     "cost": cost, "in_service_period": start, "useful_life_periods": life_periods,
                     "depreciation_per_period": per_dep})

    net = [max(0.0, gross[t] - accum[t]) for t in range(n + 1)]
    return {
        "gross": gross,
        "accumulated_depreciation": accum,
        "net": net,
        "depreciation_expense": dep,
        "capex": capex,
        "preopening_capex": preopen_capex,
        "asset_rows": rows,
    }



def fixed_asset_series_catalog(assumptions: Mapping[str, Any] | None) -> list[dict]:
    """Return linkable fixed-asset level Series owned by the fixed-assets module.

    Formula / level publishes its entered base and each named linked component as
    separate stock Series, in addition to the aggregate gross / accumulated-depreciation /
    net balances.  Component IDs are already stable identities, so no display-name link
    is required and renaming a component cannot break a downstream relationship.
    """
    a = assumptions or {}
    if fixed_asset_mode(dict(a)) != "formula_level":
        return []
    fl = _formula_level_config((a.get("fixed_assets") or {}))
    rows = [
        {"series_id": FIXED_ASSET_FORMULA_BASE_SERIES_ID,
         "name": str(fl.get("base_name") or "Base asset level"),
         "semantic": "formula_base", "unit": "$", "owner_module": "fixed_assets"},
        {"series_id": FIXED_ASSET_GROSS_SERIES_ID, "name": "Gross fixed assets",
         "semantic": "gross", "unit": "$", "owner_module": "fixed_assets"},
        {"series_id": FIXED_ASSET_ACCUM_DEP_SERIES_ID, "name": "Accumulated depreciation",
         "semantic": "accumulated_depreciation", "unit": "$", "owner_module": "fixed_assets"},
        {"series_id": FIXED_ASSET_NET_SERIES_ID, "name": "Net fixed assets",
         "semantic": "net", "unit": "$", "owner_module": "fixed_assets"},
    ]
    for i, raw in enumerate(fl.get("components") or []):
        if not isinstance(raw, Mapping):
            continue
        sid = str(raw.get("component_id") or "").strip()
        if not sid:
            continue
        rows.append({"series_id": sid,
                     "name": _formula_component_display_name(raw, i, a),
                     "semantic": "formula_component", "unit": "$",
                     "owner_module": "fixed_assets"})
    return rows


def fixed_asset_series_by_id(assumptions: Mapping[str, Any] | None, series_id: str,
                             n_periods: int, ppy: int, *, growth_context=None) -> list[float]:
    """Resolve one published fixed-asset Formula / level Series by stable ID.

    Values are native model-period *levels* and intentionally exclude the opening slot,
    matching the generic Foundry linked-Series contract.  Only Formula / level publishes
    component Series; Asset schedule and historical Simple retain aggregate statement
    outputs but do not invent component identities that were never authored.
    """
    a = assumptions or {}
    if fixed_asset_mode(dict(a)) != "formula_level":
        raise ValueError("fixed-asset component Series require Formula / level authoring")
    sid = str(series_id or "").strip()
    if not sid:
        raise ValueError("fixed-asset linked Series requires series_id")
    fa = fixed_asset_formula_level(a.get("fixed_assets"), a, int(n_periods), int(ppy),
                                   growth_context=growth_context)
    fl = fa.get("formula_level") or {}
    if sid == FIXED_ASSET_FORMULA_BASE_SERIES_ID:
        return [float(x or 0.0) for x in (fl.get("base") or [])]
    if sid == FIXED_ASSET_GROSS_SERIES_ID:
        return [float(x or 0.0) for x in (fa.get("gross") or [])[1:]]
    if sid == FIXED_ASSET_ACCUM_DEP_SERIES_ID:
        return [float(x or 0.0) for x in (fa.get("accumulated_depreciation") or [])[1:]]
    if sid == FIXED_ASSET_NET_SERIES_ID:
        return [float(x or 0.0) for x in (fa.get("net") or [])[1:]]
    hits = [c for c in (fl.get("components") or []) if str((c or {}).get("component_id") or "") == sid]
    if len(hits) != 1:
        raise ValueError(f"linked fixed-asset Series {sid!r} resolved to {len(hits)} matches; expected exactly one")
    return [float(x or 0.0) for x in (hits[0].get("amount") or [])]

def fixed_asset_mode(assumptions: dict | None) -> str:
    fa = (assumptions or {}).get("fixed_assets") or {}
    mode = str(fa.get("mode") or "simple").strip().lower()
    if mode == "schedule":
        return "schedule"
    if mode == "formula_level":
        return "formula_level"
    # Historical configs used ``simple`` or omitted fixed_assets entirely.  Keep that
    # runtime contract byte-for-byte until the user explicitly opts into Formula / level.
    return "simple"
