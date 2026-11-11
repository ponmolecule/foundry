"""r482: name the component behind an incomplete explicit schedule.

Blocking is done by the strict resolvers (series.py, periodic_flows.py, income_modules.py,
cost_recovery.py, cac_feeder.py, balance_components.py): only schedules the model actually
uses are resolved, so a dormant schedule kept for a non-destructive mode switch never blocks
a run. Those resolvers know the cadence and period but not where the schedule lives.

``schedule_errors`` walks the saved assumptions and describes every explicit schedule that
does not cover the horizon, with component and field. ``relabel`` replaces a resolver message
with the walker's description of the matching schedule(s), keyed on cadence, first missing or
blank period, and kind. The walker never blocks on its own.
"""
from __future__ import annotations

from math import ceil, isfinite
from typing import Any

_FREQ = {"year": 1, "quarter": 4, "month": 12}
_LETTER = {"month": "M", "quarter": "Q", "year": "Y"}
_MODEL = {12: "month", 4: "quarter", 1: "year"}

_TOP = {
    "lending_products": "Lending", "deposit_products": "Deposit", "obs_exposures": "Fee product",
    "cac_feeds": "CAC feed", "cost_pools": "Cost pool", "account_adoption": "Account activity",
    "managed_securities_portfolios": "Securities portfolio", "fixed_assets": "Fixed assets",
    "balance_components_model": "Interest-bearing balances", "other_assets_model": "Other assets",
    "other_liabilities_model": "Other liabilities", "nie_detail": "Operating expense",
}
_CHILD = {"fee_streams": "stream", "channels": "channel", "components": "component",
          "sleeves": "sleeve", "categories": "category", "roles": "role", "terms": "term",
          "bands": "band", "assets": "asset"}
_SKIP_FIELD = {"params", "driver", "rate", "cost", "driver_specs", "formula_level", "workforce",
               "calculation", "spec", "flow_path"}


def _need(cadence: str, n: int, ppy: int) -> int:
    if cadence in (None, "", "model_period"):
        return n
    return max(1, ceil(n * _FREQ[cadence] / ppy))


def _rng(cad: str, a: int, b: int) -> str:
    L = _LETTER.get(cad, "P")
    return f"{L}{a}" if a == b else f"{L}{a}–{L}{b}"


def _num(v) -> bool:
    if v is None or isinstance(v, bool):
        return False
    try:
        f = float(v)
    except (TypeError, ValueError):
        return False
    return isfinite(f)


def _label(a: dict, path: list) -> str:
    parts, node, i = [], a, 0
    field = []
    while i < len(path):
        k = path[i]
        nxt = node[k] if isinstance(node, (dict, list)) and (isinstance(node, dict) and k in node or isinstance(node, list) and isinstance(k, int) and k < len(node)) else None
        if i == 0 and k in _TOP:
            if isinstance(nxt, list) and i + 1 < len(path) and isinstance(path[i + 1], int):
                item = nxt[path[i + 1]] if path[i + 1] < len(nxt) else {}
                nm = (item or {}).get("name") or (item or {}).get("role") or f"#{path[i + 1] + 1}"
                parts.append(f"{_TOP[k]} '{nm}'"); node = item; i += 2; continue
            if k == "cac_feeds" and i + 1 < len(path):
                parts.append(f"CAC feed '{path[i + 1]}'"); node = (nxt or {}).get(path[i + 1]) or {}; i += 2; continue
            parts.append(_TOP[k]); node = nxt; i += 1; continue
        if k in _CHILD and isinstance(nxt, list) and i + 1 < len(path) and isinstance(path[i + 1], int):
            item = nxt[path[i + 1]] if path[i + 1] < len(nxt) else {}
            nm = (item or {}).get("name") or (item or {}).get("role") or (item or {}).get("id") or f"#{path[i + 1] + 1}"
            parts.append(f"{_CHILD[k]} '{nm}'"); node = item; i += 2; continue
        if isinstance(k, str) and k not in _SKIP_FIELD:
            field.append(k[:-5] if k.endswith("_spec") else k)
        node = nxt; i += 1
    where = " · ".join(parts) or "Schedule"
    fld = " ".join(f.replace("_", " ") for f in field[-2:])
    return where + (f" · {fld}" if fld else "")


def _check_list(vals, need, cad, out, label):
    vals = list(vals or [])
    blanks = [i + 1 for i, v in enumerate(vals[:need]) if not _num(v)]
    if blanks:
        shown = ", ".join(_rng(cad, b, b) for b in blanks[:6]) + (" …" if len(blanks) > 6 else "")
        out.append(f"{label}: {cad} schedule has a blank or non-numeric value at {shown}")
    elif len(vals) < need:
        out.append(f"{label}: {cad} schedule has {len(vals)} of {need} {cad} values, "
                   f"{_rng(cad, len(vals) + 1, need)} missing")


def _check_map(sched, need, cad, out, label):
    sched = sched if isinstance(sched, dict) else {}
    get = lambda i: sched.get(str(i), sched.get(i))
    blanks = [i for i in range(1, need + 1) if (str(i) in sched or i in sched) and not _num(get(i))]
    missing = [i for i in range(1, need + 1) if not (str(i) in sched or i in sched)]
    if blanks:
        shown = ", ".join(_rng(cad, b, b) for b in blanks[:6]) + (" …" if len(blanks) > 6 else "")
        out.append(f"{label}: {cad} schedule has a blank or non-numeric value at {shown}")
    if missing:
        runs, start, prev = [], missing[0], missing[0]
        for m in missing[1:] + [None]:
            if m is not None and m == prev + 1:
                prev = m; continue
            runs.append(_rng(cad, start, prev)); start = prev = m
        out.append(f"{label}: {cad} schedule has {need - len(missing)} of {need} {cad} values, "
                   f"{', '.join(runs[:4])}{' …' if len(runs) > 4 else ''} missing")


def _inactive(a: dict, path: list) -> bool:
    top = path[0] if path else None
    if isinstance(top, str) and top.startswith("_"):
        return True
    if top == "fixed_assets" and len(path) > 1 and path[1] == "formula_level":
        return str((a.get("fixed_assets") or {}).get("mode") or "") != "formula_level"
    if top == "other_assets_model":
        return str(a.get("other_assets_mode") or "") != "formula_level"
    if top == "other_liabilities_model":
        try:
            from .other_liabilities import other_liability_mode
            return other_liability_mode(a) != "formula_level"
        except Exception:
            return not isinstance(a.get("other_liabilities_model"), dict)
    if top == "balance_components_model":
        return (a.get("balance_components_model") or {}).get("enabled", True) is False
    return False


def schedule_errors(a: dict) -> list[str]:
    a = a or {}
    try:
        n, ppy = int(a.get("n_periods") or 12), int(a.get("periods_per_year") or 4)   # engine defaults
    except (TypeError, ValueError):
        return []
    if n <= 0 or ppy not in (1, 4, 12):
        return []
    model = _MODEL[ppy]
    out: list[str] = []

    def walk(o, path):
        if isinstance(o, list):
            for i, v in enumerate(o):
                walk(v, path + [i])
            return
        if not isinstance(o, dict):
            return
        if path and _inactive(a, path):
            return
        if o.get("_scenario_off"):
            return
        traj = str(o.get("trajectory") or "").strip().lower()
        if traj == "explicit" and o.get("source", "entered") == "entered" and isinstance(o.get("values"), list):
            cad = str(o.get("cadence") or o.get("period") or "year").strip().lower()
            cad = model if cad == "model_period" else cad
            if cad in _FREQ:
                _check_list(o["values"], _need(cad, n, ppy), cad, out, _label(a, path))
            return
        if traj == "explicit" and isinstance(o.get("schedule"), list):          # legacy opex list
            _check_list(o["schedule"], n, model, out, _label(a, path)); return
        if traj == "explicit_schedule" and isinstance(o.get("schedule"), dict) and "day1" not in o:   # managed-notional lumps are an event list
            cad = str(o.get("period") or "model_period").strip().lower()
            cad = model if cad == "model_period" else cad
            if cad in _FREQ:
                _check_map(o["schedule"], _need(cad, n, ppy), cad, out, _label(a, path))
            return
        if isinstance(o.get("level_schedule"), dict):
            ls = o["level_schedule"]
            cad = str(ls.get("period") or "").strip().lower()
            if cad in _FREQ and isinstance(ls.get("schedule"), dict):
                _check_map(ls["schedule"], _need(cad, n, ppy), cad, out, _label(a, path + ["level_schedule"]))
        if str(o.get("behavior") or "") == "scheduled" and isinstance((o.get("params") or {}).get("schedule"), dict):
            _check_map(o["params"]["schedule"], n, model, out, _label(a, path + ["rate schedule"]))
        for k, v in o.items():
            if isinstance(k, str) and k.startswith("_"):
                continue
            walk(v, path + [k])

    for k, v in a.items():
        if isinstance(k, str) and k.startswith("_"):
            continue
        walk(v, [k])
    return out


import re as _re

_RES = _re.compile(r"explicit (month|quarter|year|natural-period) schedule (?:has \d+ of \d+ \w+ values, ([MQY])(\d+)|has no value for ([MQY])(\d+)|has a (?:blank or non-numeric|non-numeric|non-finite) value at ([MQY])(\d+))")
_WALK = _re.compile(r": (month|quarter|year) schedule (?:has \d+ of \d+ \w+ values, ([MQY])(\d+)|has a blank or non-numeric value at ([MQY])(\d+))")


def _key(m, missing_groups, blank_groups):
    for g in missing_groups:
        if m.group(g):
            return ("missing", m.group(g), int(m.group(g + 1)))
    for g in blank_groups:
        if m.group(g):
            return ("blank", m.group(g), int(m.group(g + 1)))
    return None


def relabel(a: dict, message: str) -> str:
    """Return ``message`` with each resolver schedule error replaced by its component-named form."""
    if "schedule" not in str(message):
        return message
    try:
        walked = schedule_errors(a)
    except Exception:
        return message
    index: dict = {}
    for w in walked:
        m = _WALK.search(w)
        if m:
            index.setdefault(_key(m, (2,), (4,)), []).append(w)
    out, seen = [], set()
    for part in str(message).split("; "):
        m = _RES.search(part)
        k = _key(m, (2, 4), (6,)) if m else None
        hits = index.get(k) if k else None
        if hits:
            for h in hits:
                if h not in seen:
                    out.append(h); seen.add(h)
        else:
            out.append(part)
    return "; ".join(out)
