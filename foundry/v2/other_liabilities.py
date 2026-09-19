"""Generalized Formula / level authoring for other balance-sheet liabilities.

Historical Foundry exposed one scalar ``assumptions.other_liabilities`` that was held flat.
This module preserves that contract when the generalized model is absent, while allowing a
period-end liability stock to be built from an entered base plus named liability components.
Each named component is itself an additive set of safe linked-Series × multiplier terms.

The grammar is intentionally generic and source-model agnostic::

    Other liabilities = entered base + Σ(named liability component)
    named liability component = Σ(linked Series × entered multiplier)

Current linkable Series families are Workforce Count and Fixed Assets Formula / level.  Fixed
Assets publishes its entered base, named formula components, and aggregate gross / accumulated-
depreciation / net balances as stable Series.  Signed multipliers are allowed so contra balances
can be represented explicitly; the resolved total Other liabilities balance must remain >= 0.

r127 single-driver components remain readable without migration.  They are adapted to one-term
components at runtime and retain their historical economics until the user actually edits them.
"""
from __future__ import annotations

from typing import Any, Mapping


_ALLOWED_LINK_KINDS = {"workforce_role_count", "fixed_asset_level"}


def _f(v, default=0.0):
    try:
        return float(v if v is not None else default)
    except (TypeError, ValueError):
        return float(default)


def other_liability_mode(assumptions: Mapping[str, Any] | None) -> str:
    """Return the active Other-liabilities authoring mode.

    r127-r129 engagements did not persist an explicit mode: the presence of
    ``other_liabilities_model`` meant Formula / level was active.  Preserve that
    interpretation.  Newer engagements may switch back to ``flat`` without deleting
    the saved Formula / level setup, then switch back later with no data loss.
    """
    a = assumptions or {}
    raw = str(a.get("other_liabilities_mode") or "").strip().lower()
    if raw in {"flat", "formula_level"}:
        return raw
    return "formula_level" if isinstance(a.get("other_liabilities_model"), Mapping) else "flat"


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


def _legacy_term(component: Mapping[str, Any], index: int) -> dict:
    """Adapt one r127 ``driver`` + ``multiplier_spec`` component without rewriting it."""
    from .fixed_assets import FIXED_ASSET_NET_SERIES_ID
    drv = dict(component.get("driver") or {})
    kind = str(drv.get("kind") or "").strip().lower()
    if kind == "workforce_count":
        sid = str(drv.get("series_id") or "").strip()
        if not sid:
            raise ValueError(f"other_liabilities_model.components[{index}] workforce_count requires series_id")
        dspec = {"source": "link", "link": {
            "kind": "workforce_role_count", "series_id": sid, "aggregation": "end"}}
        legacy_kind = "workforce_count"
    elif kind == "fixed_asset_net":
        dspec = {"source": "link", "link": {
            "kind": "fixed_asset_level", "series_id": FIXED_ASSET_NET_SERIES_ID,
            "aggregation": "end"}}
        legacy_kind = "fixed_asset_net"
    else:
        raise ValueError(
            f"other_liabilities_model.components[{index}].driver.kind must be workforce_count or fixed_asset_net")
    return {
        "term_id": f"legacy-{component.get('component_id') or index + 1}",
        "driver_spec": dspec,
        "multiplier_spec": component.get("multiplier_spec") or {
            "source": "entered", "trajectory": "flat", "value": 0.0},
        "legacy_driver_kind": legacy_kind,
        "legacy": True,
    }


def _component_terms(component: Mapping[str, Any], index: int) -> list[dict]:
    terms = component.get("terms")
    if isinstance(terms, list):
        out = []
        for j, raw in enumerate(terms):
            if not isinstance(raw, Mapping):
                raise ValueError(f"other_liabilities_model.components[{index}].terms[{j}] must be an object")
            t = dict(raw)
            tid = str(t.get("term_id") or "").strip()
            if not tid:
                raise ValueError(f"other_liabilities_model.components[{index}].terms[{j}] requires term_id")
            out.append(t)
        return out
    # r127 compatibility: absence of terms means exactly one historical driver term.
    return [_legacy_term(component, index)]


def _driver_metadata(assumptions: Mapping[str, Any], kind: str, series_id: str) -> tuple[str, str]:
    if kind == "workforce_role_count":
        from .opex_extensions import workforce_count_catalog
        hits = [x for x in workforce_count_catalog(assumptions) if str(x.get("series_id") or "") == series_id]
        if len(hits) != 1:
            raise ValueError(f"linked Workforce Count Series {series_id!r} does not exist")
        return str(hits[0].get("role") or series_id), "count"
    if kind == "fixed_asset_level":
        from .fixed_assets import fixed_asset_series_catalog
        hits = [x for x in fixed_asset_series_catalog(assumptions) if str(x.get("series_id") or "") == series_id]
        if len(hits) != 1:
            raise ValueError(f"linked Fixed Asset Series {series_id!r} does not exist")
        return str(hits[0].get("name") or series_id), "$"
    raise ValueError(f"unsupported other-liability linked Series kind {kind!r}")


def prepare_other_liabilities(assumptions: Mapping[str, Any] | None, n_periods: int, ppy: int,
                              *, growth_context=None) -> dict | None:
    """Normalize the generalized Other-liabilities Formula / level.

    Fixed-asset terms are deterministic and can be resolved up front. Workforce terms are
    intentionally kept on the engine's runtime Workforce path. That matters for roles whose
    activation depends on model metrics: resolving those through the generic Series layer before
    the engine has produced the metric would create a false circularity. The runtime path is the
    same one historical r127 liabilities used and preserves those economics without weakening the
    generic Series circularity guard for other consumers.
    """
    from .series import normalize_series_spec, resolve_series_spec

    a = assumptions or {}
    if other_liability_mode(a) != "formula_level":
        return None
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
    term_ids = []
    for i, raw in enumerate(cfg.get("components") or []):
        if not isinstance(raw, Mapping):
            raise ValueError(f"other_liabilities_model.components[{i}] must be an object")
        c = dict(raw)
        cid = str(c.get("component_id") or "").strip()
        if not cid:
            raise ValueError(f"other_liabilities_model.components[{i}] requires component_id")
        ids.append(cid)
        resolved_terms = []
        for j, term in enumerate(_component_terms(c, i)):
            tid = str(term.get("term_id") or "").strip()
            term_ids.append(tid)
            ns = normalize_series_spec(term.get("driver_spec"), default_value=0.0)
            if ns.get("source") != "link":
                raise ValueError(
                    f"other_liabilities_model.components[{i}].terms[{j}].driver_spec must be a linked Series")
            link = dict(ns.get("link") or {})
            kind = str(link.get("kind") or "").strip()
            sid = str(link.get("series_id") or "").strip()
            if kind not in _ALLOWED_LINK_KINDS:
                raise ValueError(
                    f"other_liabilities_model.components[{i}].terms[{j}] linked Series kind {kind!r} unsupported")
            if not sid:
                raise ValueError(
                    f"other_liabilities_model.components[{i}].terms[{j}] linked Series requires series_id")
            legacy_fixed_net = term.get("legacy_driver_kind") == "fixed_asset_net"
            if legacy_fixed_net:
                # r127 allowed aggregate net fixed assets regardless of Fixed Asset authoring mode.
                # Preserve that historical runtime link exactly; new authoring uses published
                # Fixed Asset Formula / level Series instead.
                name, unit = "Premises & fixed assets · net", "$"
            else:
                name, unit = _driver_metadata(a, kind, sid)

            # Workforce and the r127 aggregate-net adapter are resolved from engine runtime state.
            # New Fixed Asset Formula / level Series are safe to resolve up front.
            driver = None
            if kind == "fixed_asset_level" and not legacy_fixed_net:
                driver = [float(x or 0.0) for x in resolve_series_spec(
                    ns, a, n, ppy, context=growth_context, default_value=0.0)]

            mult = _resolve_entered(
                term.get("multiplier_spec") or {"source": "entered", "trajectory": "flat", "value": 0.0},
                n, ppy, growth_context=growth_context, default_value=0.0)
            resolved_terms.append({
                "term_id": tid,
                "driver_kind": kind,
                "series_id": sid,
                "driver_name": name,
                "driver_unit": unit,
                "driver": driver,
                "multiplier": mult,
                "legacy_driver_kind": term.get("legacy_driver_kind"),
                "legacy_fixed_asset_net": bool(legacy_fixed_net),
                "legacy": bool(term.get("legacy")),
            })
        row = {
            "component_id": cid,
            "name": str(c.get("name") or f"Liability component {i + 1}"),
            "terms": resolved_terms,
        }
        # Compatibility metadata for r127 one-driver consumers. Actual runtime arrays are built
        # from period rows in ``other_liability_audit_payload``.
        if len(resolved_terms) == 1:
            t = resolved_terms[0]
            row.update({
                "driver_kind": t.get("legacy_driver_kind") or t.get("driver_kind"),
                "series_id": t.get("series_id") or "",
            })
        rows.append(row)

    if len(ids) != len(set(ids)):
        raise ValueError("other_liabilities_model component_id values must be unique")
    if len(term_ids) != len(set(term_ids)):
        raise ValueError("other_liabilities_model term_id values must be unique")
    return {"opening_balance": max(0.0, opening), "base": base, "components": rows}


def other_liability_period(prepared: Mapping[str, Any] | None, period_index: int,
                           *, workforce_count=None, fixed_asset_net=None, **_ignored) -> dict:
    """Resolve one modeled period using engine-native Workforce counts where required."""
    if prepared is None:
        raise ValueError("generalized other-liability model is not active")
    i = int(period_index)
    base = list(prepared.get("base") or [])
    if i < 0 or i >= len(base):
        raise IndexError("other-liability period index out of range")
    wf = workforce_count if isinstance(workforce_count, Mapping) else {}
    detail = []
    total = float(base[i] or 0.0)
    for c in prepared.get("components") or []:
        terms = []
        component_amount = 0.0
        for t in c.get("terms") or []:
            kind = str(t.get("driver_kind") or "")
            sid = str(t.get("series_id") or "")
            if kind == "workforce_role_count":
                if sid not in wf:
                    raise ValueError(f"runtime Workforce Count Series {sid!r} is unavailable for other liabilities")
                driver = float(wf.get(sid) or 0.0)
            elif t.get("legacy_fixed_asset_net"):
                if fixed_asset_net is None:
                    raise ValueError("runtime net fixed assets are unavailable for legacy r127 other liabilities")
                driver = float(fixed_asset_net or 0.0)
            else:
                dvals = list(t.get("driver") or [])
                if i >= len(dvals):
                    raise IndexError(f"other-liability Fixed Asset Series {sid!r} period index out of range")
                driver = float(dvals[i] or 0.0)
            mvals = list(t.get("multiplier") or [])
            if i >= len(mvals):
                raise IndexError("other-liability multiplier period index out of range")
            mult = float(mvals[i] or 0.0)
            amount = driver * mult
            component_amount += amount
            terms.append({
                "term_id": t.get("term_id"), "driver_kind": kind,
                "series_id": sid, "driver_name": t.get("driver_name"),
                "driver_unit": t.get("driver_unit"), "driver": driver,
                "multiplier": mult, "amount": amount,
            })
        total += component_amount
        detail.append({
            "component_id": c.get("component_id"), "name": c.get("name"),
            "amount": component_amount, "terms": terms,
        })
    if total < -1e-8:
        raise ValueError("resolved other-liability level cannot be negative")
    return {"base": float(base[i] or 0.0), "components": detail, "total": max(0.0, total)}


def other_liability_audit_payload(prepared: Mapping[str, Any] | None, total,
                                   period_rows=None) -> dict:
    """Stable exact-engine audit payload for Formula / level Other liabilities."""
    if prepared is None:
        return {}
    runtime_rows = list(period_rows or [])
    comps = []
    for c in prepared.get("components") or []:
        cid = c.get("component_id")
        c_runtime = []
        for pr in runtime_rows:
            hit = next((x for x in (pr.get("components") or []) if x.get("component_id") == cid), None)
            c_runtime.append(hit or {})
        row = {
            "component_id": cid, "name": c.get("name"),
            "amount": [float(x.get("amount") or 0.0) for x in c_runtime],
            "terms": [],
        }
        for t in c.get("terms") or []:
            tid = t.get("term_id")
            tr = []
            for cr in c_runtime:
                hit = next((x for x in (cr.get("terms") or []) if x.get("term_id") == tid), None)
                tr.append(hit or {})
            row["terms"].append({
                "term_id": tid, "driver_kind": t.get("driver_kind"),
                "series_id": t.get("series_id") or "", "driver_name": t.get("driver_name"),
                "driver_unit": t.get("driver_unit"),
                "driver": [float(x.get("driver") or 0.0) for x in tr],
                "multiplier": [float(x.get("multiplier") or 0.0) for x in tr],
                "amount": [float(x.get("amount") or 0.0) for x in tr],
            })
        if c.get("driver_kind") is not None and len(row["terms"]) == 1:  # r127 projection
            rt = row["terms"][0]
            row.update({
                "driver_kind": c.get("driver_kind"), "series_id": c.get("series_id") or "",
                "driver": list(rt.get("driver") or []),
                "multiplier": list(rt.get("multiplier") or []),
            })
        comps.append(row)
    return {
        "mode": "formula_level", "opening_balance": float(prepared.get("opening_balance") or 0.0),
        "base": list(prepared.get("base") or []), "total": list(total or []), "components": comps,
    }
