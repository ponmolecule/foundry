"""r482/r484: name the component behind an incomplete explicit schedule.

Blocking is done by the strict resolvers (series.py, periodic_flows.py, income_modules.py,
cost_recovery.py, cac_feeder.py, balance_components.py): only schedules the model actually
uses are resolved, so a dormant schedule kept for a non-destructive mode switch never blocks
a run. Those resolvers know the cadence and period but not where the schedule lives.

r484: before validation or a run, ``tag_schedules`` marks every saved explicit schedule with
its path (series.ScheduleList / ScheduleDict). A resolver that fails records the tag of the
schedule it was given together with its error text. ``relabel`` names exactly those paths, so
a dormant schedule is never named even when its content is identical to the failing one. A
failure without a tag leaves the engine message unchanged. The walker never blocks.
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


def _schedules(a: dict, include_inactive: bool = False):
    """Yield (path, parent, key, container, kind, cadence, need) for every saved explicit schedule.

    ``path`` is a tuple into the assumptions; ``parent[key]`` is the container. Dormant schedules
    (inactive modes, switched-off scenario items, ``_`` keys) are skipped unless asked for.
    """
    a = a or {}
    try:
        n, ppy = int(a.get("n_periods") or 12), int(a.get("periods_per_year") or 4)   # engine defaults
    except (TypeError, ValueError):
        return
    if n <= 0 or ppy not in (1, 4, 12):
        return
    model = _MODEL[ppy]
    found: list = []

    def walk(o, path):
        if isinstance(o, list):
            for i, v in enumerate(o):
                walk(v, path + [i])
            return
        if not isinstance(o, dict):
            return
        if not include_inactive and path and (_inactive(a, path) or o.get("_scenario_off")):
            return
        traj = str(o.get("trajectory") or "").strip().lower()
        if traj == "explicit" and o.get("source", "entered") == "entered" and isinstance(o.get("values"), list):
            raw = str(o.get("cadence") or o.get("period") or "year").strip().lower()
            cad = model if raw == "model_period" else raw
            if cad in _FREQ:
                found.append((tuple(path + ["values"]), o, "values", "list", cad, _need(cad, n, ppy), path))
            return
        if traj == "explicit" and isinstance(o.get("schedule"), list):          # legacy opex list
            found.append((tuple(path + ["schedule"]), o, "schedule", "list", model, n, path)); return
        if traj == "explicit_schedule" and isinstance(o.get("schedule"), dict) and "day1" not in o:   # managed-notional lumps are an event list
            raw = str(o.get("period") or "model_period").strip().lower()
            cad = model if raw == "model_period" else raw
            if cad in _FREQ:
                found.append((tuple(path + ["schedule"]), o, "schedule", "map", cad, _need(cad, n, ppy), path))
            return
        if isinstance(o.get("level_schedule"), dict):
            ls = o["level_schedule"]
            cad = str(ls.get("period") or "").strip().lower()
            if cad in _FREQ and isinstance(ls.get("schedule"), dict):
                found.append((tuple(path + ["level_schedule", "schedule"]), ls, "schedule", "map", cad,
                              _need(cad, n, ppy), path + ["level_schedule"]))
        if str(o.get("behavior") or "") == "scheduled" and isinstance((o.get("params") or {}).get("schedule"), dict):
            found.append((tuple(path + ["params", "schedule"]), o["params"], "schedule", "map", model, n,
                          path + ["rate schedule"]))
        for k, v in list(o.items()):
            if isinstance(k, str) and k.startswith("_"):
                continue
            walk(v, path + [k])

    for k, v in list(a.items()):
        if isinstance(k, str) and k.startswith("_"):
            continue
        walk(v, [k])
    for path, parent, key, kind, cad, need, label_path in found:
        yield path, parent, key, parent[key], kind, cad, need, label_path


def _describe(a, kind, container, cad, need, label_path) -> list[str]:
    out: list[str] = []
    (_check_list if kind == "list" else _check_map)(container, need, cad, out, _label(a, label_path))
    return out


def schedule_errors(a: dict) -> list[str]:
    """Describe every active explicit schedule that does not cover the horizon (never blocks)."""
    out: list[str] = []
    for _p, _par, _k, cont, kind, cad, need, lp in _schedules(a):
        out.extend(_describe(a, kind, cont, cad, need, lp))
    return out


def tag_schedules(a: dict) -> dict:
    """Mark every saved explicit schedule (active or dormant) in ``a`` with its path, in place.

    Pass a private copy. Tagged containers compare, hash and serialise like plain lists/dicts.
    """
    from .series import tag_schedule
    for path, parent, key, cont, _kind, _cad, _need_, _lp in list(_schedules(a, include_inactive=True)):
        if isinstance(cont, (list, dict)):
            parent[key] = tag_schedule(cont, path)
    return a


def tagged_config(cfg):
    """A deep copy of ``cfg`` whose assumptions carry schedule path tags (r484)."""
    from copy import deepcopy
    if not isinstance(cfg, dict) or not isinstance(cfg.get("assumptions"), dict):
        return cfg
    out = deepcopy(cfg)
    try:
        tag_schedules(out["assumptions"])
    except Exception:
        return deepcopy(cfg)
    return out


def relabel(a: dict, message: str, failures=None) -> str:
    """Replace resolver schedule errors with the component-named description of the schedule
    that actually failed.

    ``failures`` are (path tag, error text) pairs the resolvers recorded
    (series.record_schedule_failure). Each schedule error in ``message`` is attributed only to
    the resolver records with that exact text, and only by their saved path. Content is never
    compared, so a dormant schedule identical to the failing one is never named. If any error
    cannot be attributed to a tagged path, the message is returned unchanged.
    """
    if "schedule" not in str(message) or not failures:
        return message
    try:
        index = {p: (kind, cont, cad, need, lp)
                 for p, _par, _k, cont, kind, cad, need, lp in _schedules(a, include_inactive=True)}
    except Exception:
        return message
    out, extra = [], []
    for part in str(message).split("; "):
        if not _RES.search(part):
            # A resolver alternative ("expected exactly one ...") adds nothing once the failing
            # schedule is named.
            (extra if part.strip().startswith("expected exactly one") else out).append(part)
            continue
        recs = [(tag, txt) for tag, txt in failures if txt and txt in part]
        if not recs or any(tag is None or tuple(tag) not in index for tag, _ in recs):
            return message
        for tag, txt in dict.fromkeys(recs):
            kind, cont, cad, need, lp = index[tuple(tag)]
            desc = _describe(a, kind, cont, cad, need, lp) or [f"{_label(a, lp)}: {txt}"]
            for d in desc:
                if d not in out:
                    out.append(d)
    return "; ".join(out)


import re as _re

_RES = _re.compile(r"explicit (month|quarter|year|natural-period) schedule (?:has \d+ of \d+ \w+ values, ([MQY])(\d+)|has no value for ([MQY])(\d+)|has a (?:blank or non-numeric|non-numeric|non-finite) value at ([MQY])(\d+))|Year-end target schedule has \d+ annual values?, Y\d+ missing")
