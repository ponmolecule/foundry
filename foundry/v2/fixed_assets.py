"""Canonical fixed-asset / CAPEX resolver for Foundry v2.

The projection engines consume native-period series.  This module owns the accounting
semantics that turn asset records into those series.  Legacy ``premises_equipment`` +
``premises_depreciation_annual`` remains a separate fallback path in the engines; this
resolver is used only when ``assumptions.fixed_assets.mode == 'schedule'``.

V1 exposes straight-line depreciation while retaining a method field in the schema so
future methods do not require a data-model migration.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Tuple


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


def fixed_asset_mode(assumptions: dict | None) -> str:
    fa = (assumptions or {}).get("fixed_assets") or {}
    return "schedule" if fa.get("mode") == "schedule" else "simple"
