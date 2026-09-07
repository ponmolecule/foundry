"""Generic Foundry series primitives and cross-module links.

North-star contract
-------------------
Foundry modules own *equations*; their operands are time-varying series.  A series is
an authored trajectory (flat/growth/explicit) or a link to a series owned elsewhere.
Links reference stable ``series_id`` values, never display names or spreadsheet cells.

This module deliberately does not provide an arbitrary formula language.  It only
resolves series and safe links; domain modules (CAC, workforce, fees, etc.) retain a
small, closed vocabulary of defensible equations.
"""
from __future__ import annotations

from typing import Any, Mapping

from .growth import growth_multiplier, resolve_growth_series

_VALID_SOURCES = {"entered", "link", "derived"}
_VALID_TRAJECTORIES = {"flat", "growth", "explicit"}
_VALID_CADENCES = {"year", "quarter", "month", "model_period"}
_FREQ = {"year": 1, "quarter": 4, "month": 12}
_VALID_EXTEND = {"hold", "zero", "error"}
_VALID_RESOLUTION = {"step", "smooth"}
_VALID_AGG = {"sum", "average", "end", "start"}


def normalize_series_spec(spec: Mapping[str, Any] | None, *, default_value: float = 0.0) -> dict:
    """Normalize an authored series spec while preserving legacy ``mode`` vocabulary.

    Canonical entered shape::

        {source: entered, trajectory: flat, value: x}
        {source: entered, trajectory: growth, base: x, growth_spec: {...}}
        {source: entered, trajectory: explicit, cadence: year,
         values: [...], resolution: step, extend: hold}

    Canonical link shape::

        {source: link, link: {kind: ..., series_id: ..., aggregation: sum|average|end|start}}

    Canonical derived shape::

        {source: derived, series_id: ..., owner_module: ...,
         derived: {kind: <closed module-owned equation id>}}

    ``derived`` is intentionally metadata-only here: the generic Series layer never
    evaluates formulas. The owning domain module must resolve its own whitelisted
    equation and may pass the resulting values through a dedicated module seam.

    Legacy CAC ``{mode: ...}`` specs are intentionally accepted unchanged.
    """
    raw = dict(spec or {})
    source = str(raw.get("source") or "entered").lower()
    if source not in _VALID_SOURCES:
        raise ValueError(f"unsupported Foundry series source {source!r}")
    ident = {}
    if str(raw.get("series_id") or "").strip():
        ident["series_id"] = str(raw.get("series_id")).strip()
    if str(raw.get("owner_module") or "").strip():
        ident["owner_module"] = str(raw.get("owner_module")).strip()
    if str(raw.get("semantic_type") or "").strip():
        ident["semantic_type"] = str(raw.get("semantic_type")).strip()

    if source == "link":
        link = raw.get("link")
        if not isinstance(link, Mapping):
            raise ValueError("linked Foundry series requires a link object")
        if not str(link.get("kind") or "").strip():
            raise ValueError("linked Foundry series requires link.kind")
        if not (str(link.get("series_id") or "").strip() or str(link.get("name") or "").strip()):
            raise ValueError("linked Foundry series requires link.series_id (or legacy link.name)")
        agg = str(link.get("aggregation") or _default_link_aggregation(str(link.get("kind") or ""))).lower()
        if agg not in _VALID_AGG:
            raise ValueError(f"unsupported linked-series aggregation {agg!r}")
        return {**ident, "source": "link", "link": {**dict(link), "aggregation": agg}}

    if source == "derived":
        drv = raw.get("derived")
        if not isinstance(drv, Mapping) or not str(drv.get("kind") or "").strip():
            raise ValueError("derived Foundry series requires derived.kind")
        if not ident.get("series_id") or not ident.get("owner_module"):
            raise ValueError("derived Foundry series requires stable series_id and owner_module")
        return {**ident, "source": "derived", "derived": dict(drv)}

    traj = str(raw.get("trajectory") or raw.get("mode") or "flat").lower()
    if traj not in _VALID_TRAJECTORIES:
        raise ValueError(f"unsupported Foundry series trajectory {traj!r}")
    out = {**ident, "source": "entered", "trajectory": traj}
    if traj == "flat":
        out["value"] = float(raw.get("value") if raw.get("value") is not None else default_value)
    elif traj == "growth":
        out["base"] = float(raw.get("base") if raw.get("base") is not None else default_value)
        out["growth_spec"] = dict(raw.get("growth_spec") or {
            "rate": 0.0, "period": "year", "method": "step", "anchor": "model_year"
        })
    else:
        cadence = str(raw.get("cadence") or "year").lower()
        if cadence not in _VALID_CADENCES:
            raise ValueError(f"unsupported Foundry series cadence {cadence!r}")
        vals = raw.get("values") or []
        if not isinstance(vals, (list, tuple)):
            raise ValueError("explicit Foundry series values must be a list")
        extend = str(raw.get("extend") or "hold").lower()
        if extend not in _VALID_EXTEND:
            raise ValueError(f"unsupported explicit-series extension {extend!r}")
        resolution = str(raw.get("resolution") or "step").lower()
        if resolution not in _VALID_RESOLUTION:
            raise ValueError(f"unsupported explicit-series resolution {resolution!r}")
        out.update({"cadence": cadence, "values": list(vals), "extend": extend,
                    "resolution": resolution})
    return out


def _default_link_aggregation(kind: str) -> str:
    # Expense/spend is a flow; workforce count is a level/population.
    if kind == "operating_expense_category":
        return "sum"
    if kind == "workforce_role_count":
        return "average"
    return "average"


def _explicit_value(values, idx: int, extend: str) -> float:
    if 0 <= idx < len(values):
        v = values[idx]
        if v is None:
            raise ValueError(f"explicit Foundry series has a blank value at source period {idx + 1}")
        return float(v)
    if extend == "hold":
        return float(values[-1]) if values else 0.0
    if extend == "zero":
        return 0.0
    raise ValueError(f"explicit Foundry series has no value for source period {idx + 1}")


def resolve_entered_series(spec: Mapping[str, Any] | None, n_periods: int, ppy: int = 4,
                            *, context=None, default_value: float = 0.0) -> list[float]:
    """Resolve an entered series to native model-period *levels*.

    Explicit source cadences may be coarser than the engine cadence. ``step`` holds a
    source value through its interval. ``smooth`` linearly moves from the current source
    value to the next one across that interval.  A source cadence finer than the engine
    cadence fails closed rather than silently sampling/averaging unknown economics.
    """
    s = normalize_series_spec(spec, default_value=default_value)
    if s["source"] != "entered":
        raise ValueError("resolve_entered_series cannot resolve a linked series without assumptions context")
    n, ppy = int(n_periods), int(ppy)
    if ppy not in (1, 4, 12):
        raise ValueError(f"unsupported cadence periods_per_year={ppy}")
    if s["trajectory"] == "flat":
        return [float(s["value"])] * n
    if s["trajectory"] == "growth":
        return resolve_growth_series(float(s["base"]), s["growth_spec"], n, ppy, context=context)

    cadence = s["cadence"]
    source_freq = ppy if cadence == "model_period" else _FREQ[cadence]
    if source_freq > ppy:
        raise ValueError(
            f"cannot represent explicit {cadence} levels inside {ppy}-period/year model cadence")
    if ppy % source_freq:
        raise ValueError(f"cannot align explicit {cadence} levels to cadence {ppy}")
    width = ppy // source_freq
    vals, extend, resolution = s["values"], s["extend"], s["resolution"]
    out: list[float] = []
    for p in range(1, n + 1):
        src_idx = (p - 1) // width
        cur = _explicit_value(vals, src_idx, extend)
        if resolution == "step" or width == 1:
            out.append(cur)
            continue
        nxt = _explicit_value(vals, src_idx + 1, extend)
        # P1 of an interval is the current source value; final period approaches next.
        pos = (p - 1) % width
        frac = pos / float(width)
        out.append(cur + (nxt - cur) * frac)
    return out


def resolve_series_spec(spec: Mapping[str, Any] | None, assumptions: Mapping[str, Any] | None,
                        n_periods: int, ppy: int = 4, *, context=None,
                        default_value: float = 0.0, _stack=None) -> list[float]:
    """Resolve entered or safely-linked Foundry series to native-period levels/flows."""
    s = normalize_series_spec(spec, default_value=default_value)
    if s["source"] == "entered":
        return resolve_entered_series(s, n_periods, ppy, context=context, default_value=default_value)
    if s["source"] == "link":
        return resolve_linked_series(assumptions or {}, s["link"], n_periods, ppy,
                                     context=context, _stack=_stack)
    raise ValueError(
        "derived Foundry series are resolved only by their owning module's closed equation; "
        "the generic Series resolver does not evaluate formulas")


def _find_by_id_or_name(rows, link, kind):
    sid = str(link.get("series_id") or "").strip()
    name = str(link.get("name") or "").strip()
    if sid:
        hits = [r for r in rows if str((r or {}).get("series_id") or "").strip() == sid]
    else:
        hits = [r for r in rows if str((r or {}).get("name") or (r or {}).get("role") or "").strip() == name]
    if len(hits) != 1:
        ident = sid or name
        raise ValueError(f"linked {kind} series {ident!r} resolved to {len(hits)} matches; expected exactly one")
    return hits[0]


def resolve_linked_series(assumptions: Mapping[str, Any], link: Mapping[str, Any],
                          n_periods: int, ppy: int = 4, *, context=None, _stack=None) -> list[float]:
    """Resolve a whitelisted cross-module link.

    Links are intentionally narrow and causal.  CAC may consume static Operating Expense
    category flows or fixed/entered Workforce count levels.  Metric-triggered workforce
    counts are rejected because CAC can itself drive metrics/AUC used by those triggers,
    which would introduce a circular dependency.
    """
    kind = str(link.get("kind") or "").strip()
    ident = str(link.get("series_id") or link.get("name") or "").strip()
    stack = tuple(_stack or ())
    token = (kind, ident)
    if token in stack:
        raise ValueError(f"circular Foundry series link detected at {kind}:{ident}")
    stack = stack + (token,)
    nd = (assumptions or {}).get("nie_detail") or {}
    if kind == "operating_expense_category":
        from .income_modules import nie_category_series
        row = _find_by_id_or_name(nd.get("categories") or [], link, kind)
        return nie_category_series(row, int(n_periods), int(ppy), growth_context=context)
    if kind == "workforce_role_count":
        from .workforce import workforce_role_count_series
        wf = nd.get("workforce") or {}
        row = _find_by_id_or_name(wf.get("roles") or [], link, kind)
        if row.get("activation"):
            raise ValueError(
                "CAC cannot link to a metric-triggered workforce count; use a fixed/entered count path "
                "or break the circular dependency")
        return workforce_role_count_series(row, int(n_periods), int(ppy), growth_context=context)
    raise ValueError(f"unsupported Foundry linked-series kind {kind!r}")


def annual_value(series: list[float], year: int, ppy: int, aggregation: str = "average") -> float:
    """Reduce one native-period series to a model-year value using explicit semantics."""
    agg = str(aggregation or "average").lower()
    if agg not in _VALID_AGG:
        raise ValueError(f"unsupported annual aggregation {agg!r}")
    y, ppy = int(year), int(ppy)
    lo, hi = (y - 1) * ppy, min(y * ppy, len(series))
    vals = [float(v or 0.0) for v in series[lo:hi]]
    if not vals:
        return 0.0
    if agg == "sum":
        return sum(vals)
    if agg == "end":
        return vals[-1]
    if agg == "start":
        return vals[0]
    return sum(vals) / len(vals)


def resolve_series_value_for_year(spec: Mapping[str, Any] | None, year: int,
                                  assumptions: Mapping[str, Any] | None = None,
                                  *, n_periods: int | None = None, ppy: int = 4,
                                  context=None, default_value: float = 0.0) -> float:
    """Resolve a series operand to one model-year value for annual domain equations (CAC).

    Entered flat/growth/explicit-annual specs preserve the historical CAC semantics exactly.
    Linked series (or finer explicit cadences) are reduced with explicit aggregation semantics.
    """
    raw = dict(spec or {})
    s = normalize_series_spec(raw, default_value=default_value)
    y, ppy = int(year), int(ppy)
    if s["source"] == "entered" and s["trajectory"] in {"flat", "growth"}:
        if s["trajectory"] == "flat":
            return float(s["value"])
        return float(s["base"]) * growth_multiplier(
            s["growth_spec"], current_period=y, start_period=1, ppy=1,
            context=context, base_position="period1")
    if s["source"] == "entered" and s["trajectory"] == "explicit" and s["cadence"] == "year":
        return _explicit_value(s["values"], y - 1, s["extend"])

    n = int(n_periods or max(y * ppy, ppy))
    arr = resolve_series_spec(s, assumptions or {}, n, ppy, context=context,
                              default_value=default_value)
    agg = ((s.get("link") or {}).get("aggregation") if s["source"] == "link"
           else str(raw.get("aggregation") or "average"))
    return annual_value(arr, y, ppy, agg or "average")
