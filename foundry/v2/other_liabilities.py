"""Generalized Formula / level authoring for other balance-sheet liabilities.

Historical Foundry exposed one scalar ``assumptions.other_liabilities`` that was held flat.
This module preserves that contract when the generalized model is absent, while allowing a
period-end liability stock to be built from an entered base level plus named linked
Series × multiplier components.

The component vocabulary is deliberately small:

* ``workforce_count`` — a stable Workforce Count Series (including Total workforce)
* ``fixed_asset_net`` — the engine's resolved net premises/fixed-asset balance

Names are presentation only.  The engine understands the linked source and multiplier, not
engagement-specific concepts such as Accounts Payable or Operating Lease Liability.
"""
from __future__ import annotations

from typing import Any, Mapping


VALID_DRIVER_KINDS = {"workforce_count", "fixed_asset_net"}


def _f(v, default=0.0):
    try:
        return float(v if v is not None else default)
    except (TypeError, ValueError):
        return float(default)


def other_liability_model(assumptions: Mapping[str, Any] | None) -> dict | None:
    raw = (assumptions or {}).get("other_liabilities_model")
    return dict(raw) if isinstance(raw, Mapping) else None


def _resolve_entered(spec: Mapping[str, Any] | None, n_periods: int, ppy: int,
                     *, growth_context=None, default_value: float = 0.0) -> list[float]:
    from .series import normalize_series_spec, resolve_entered_series
    ns = normalize_series_spec(spec, default_value=default_value)
    if ns["source"] != "entered":
        raise ValueError("other-liability base and multiplier trajectories must be entered Series")
    vals = resolve_entered_series(ns, int(n_periods), int(ppy),
                                  context=growth_context, default_value=default_value)
    return [float(v or 0.0) for v in vals]


def prepare_other_liabilities(assumptions: Mapping[str, Any] | None, n_periods: int, ppy: int,
                              *, growth_context=None) -> dict | None:
    """Normalize and resolve all authored trajectories except runtime linked drivers."""
    a = assumptions or {}
    cfg = other_liability_model(a)
    if cfg is None:
        return None
    n, ppy = int(n_periods), int(ppy)
    opening = _f(cfg.get("opening_balance", a.get("other_liabilities", 0.0)), 0.0)
    if opening < -1e-9:
        raise ValueError("other_liabilities_model.opening_balance cannot be negative")
    base = _resolve_entered(
        cfg.get("base_spec") or {"source": "entered", "trajectory": "flat", "value": 0.0},
        n, ppy, growth_context=growth_context, default_value=0.0)
    if any(v < -1e-9 for v in base):
        raise ValueError("other-liability base level cannot be negative")

    rows = []
    ids = []
    for i, raw in enumerate(cfg.get("components") or []):
        if not isinstance(raw, Mapping):
            raise ValueError(f"other_liabilities_model.components[{i}] must be an object")
        c = dict(raw)
        cid = str(c.get("component_id") or "").strip()
        if not cid:
            raise ValueError(f"other_liabilities_model.components[{i}] requires component_id")
        ids.append(cid)
        drv = dict(c.get("driver") or {})
        kind = str(drv.get("kind") or "").strip().lower()
        if kind not in VALID_DRIVER_KINDS:
            raise ValueError(
                f"other_liabilities_model.components[{i}].driver.kind must be workforce_count or fixed_asset_net")
        sid = str(drv.get("series_id") or "").strip()
        if kind == "workforce_count" and not sid:
            raise ValueError(f"other_liabilities_model.components[{i}] workforce_count requires series_id")
        mult = _resolve_entered(
            c.get("multiplier_spec") or {"source": "entered", "trajectory": "flat", "value": 0.0},
            n, ppy, growth_context=growth_context, default_value=0.0)
        if any(v < -1e-12 for v in mult):
            raise ValueError("other-liability component multiplier cannot be negative")
        rows.append({
            "component_id": cid,
            "name": str(c.get("name") or f"Liability component {i + 1}"),
            "driver_kind": kind,
            "series_id": sid,
            "multiplier": mult,
        })
    if len(ids) != len(set(ids)):
        raise ValueError("other_liabilities_model component_id values must be unique")
    return {"opening_balance": max(0.0, opening), "base": base, "components": rows}


def other_liability_period(prepared: Mapping[str, Any] | None, period_index: int,
                           *, workforce_count: Mapping[str, float] | None = None,
                           fixed_asset_net: float = 0.0) -> dict:
    """Resolve one modeled period (zero-based) from runtime driver values."""
    if prepared is None:
        raise ValueError("generalized other-liability model is not active")
    i = int(period_index)
    base = list(prepared.get("base") or [])
    if i < 0 or i >= len(base):
        raise IndexError("other-liability period index out of range")
    total = float(base[i] or 0.0)
    detail = []
    wc = workforce_count or {}
    for c in prepared.get("components") or []:
        kind = str(c.get("driver_kind") or "")
        if kind == "workforce_count":
            sid = str(c.get("series_id") or "")
            if sid not in wc:
                raise ValueError(f"linked Workforce Count Series {sid!r} is unavailable in this engine period")
            driver = float(wc[sid] or 0.0)
        elif kind == "fixed_asset_net":
            driver = float(fixed_asset_net or 0.0)
        else:  # normalized earlier; defensive fail-closed seam
            raise ValueError(f"unsupported other-liability driver {kind!r}")
        mults = list(c.get("multiplier") or [])
        mult = float(mults[i] if i < len(mults) else 0.0)
        amount = driver * mult
        total += amount
        detail.append({
            "component_id": c.get("component_id"), "name": c.get("name"),
            "driver_kind": kind, "series_id": c.get("series_id") or "",
            "driver": driver, "multiplier": mult, "amount": amount,
        })
    if total < -1e-8:
        raise ValueError("resolved other-liability level cannot be negative")
    return {"base": float(base[i] or 0.0), "components": detail, "total": max(0.0, total)}
