"""r248: field-level differences between two saved configurations, for Change history.

Read-only. Leaves are compared by value; numeric schedules (lists of numbers) are compared cell by cell and
consecutive changed cells are reported as one change ("attrition rate · M8 to M10: a / b / c -> x / y / z").
Keys beginning with an underscore are bookkeeping and ignored. Labels reuse the data checks' location names.
"""
from __future__ import annotations

from foundry.v2.data_checks import _where, _fmt

MAX_CHANGES = 60


def _is_num_list(v):
    return isinstance(v, list) and len(v) >= 2 and all(x is None or isinstance(x, (int, float)) for x in v)


def _leaves(o, path=()):
    if isinstance(o, dict):
        for k, v in o.items():
            if isinstance(k, str) and k.startswith("_"):
                continue
            yield from _leaves(v, path + (k,))
    elif isinstance(o, list) and not _is_num_list(o):
        for i, v in enumerate(o):
            yield from _leaves(v, path + (i,))
    else:
        yield path, o


def _val(v):
    if v is None:
        return "—"
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, (int, float)):
        return _fmt(v)
    if isinstance(v, list):
        return f"{len(v)} values"
    return str(v)


_NAMES = {"yield_ann": "yield (annual)", "fee_yield_ann": "fee yield (annual)", "rate_paid_ann": "rate paid (annual)",
          "charge_off_ann": "charge-offs (annual)", "reserve_rate_pct_bal": "reserve (% of balance)",
          "opex_pct_ann": "operating cost (annual %)", "opex_fixed_per_period": "fixed operating cost",
          "opening_balance": "starting balance", "runoff_per_period": "runoff", "growth_per_period": "growth",
          "originations_per_period": "new originations", "new_deposits_per_period": "new deposits",
          "index_spread": "spread over index", "rate_type": "rate type", "scenario_name": "engagement name",
          "avg_maturity_m": "average maturity (months)", "term_q": "term (quarters)"}


def _label(cfg, path):
    main, detail = _where(cfg, list(path[:-1]) if path else [])
    leaf = path[-1] if path else ""
    leaf_txt = "" if isinstance(leaf, int) else _NAMES.get(str(leaf), str(leaf).replace("_", " "))
    parts = [x for x in (detail, leaf_txt) if x and x not in ("values", "value")]
    return main, " · ".join(parts)


def _runs(idx):
    runs, cur = [], []
    for i in idx:
        if cur and i != cur[-1] + 1:
            runs.append(cur); cur = []
        cur.append(i)
    if cur:
        runs.append(cur)
    return runs


def _prefix(cfg, path):
    node = cfg
    try:
        for k in path[:-1]:
            node = node[k]
    except Exception:
        return "M"
    per = (node.get("cadence") or node.get("period") or "month") if isinstance(node, dict) else "month"
    return {"quarter": "Q", "year": "Y", "annual": "Y"}.get(str(per), "M")


def diff(old, new):
    a = dict(_leaves(old or {}))
    b = dict(_leaves(new or {}))
    changes = []
    for path in sorted(set(a) | set(b), key=lambda p: [str(x) for x in p]):
        va, vb = a.get(path, None), b.get(path, None)
        if va == vb:
            continue
        where, field = _label(new if path in b else old, path)
        if _is_num_list(va) and _is_num_list(vb) and len(va) == len(vb):
            idx = [i for i in range(len(va)) if va[i] != vb[i]]
            period_prefix = _prefix(new, path)
            for r in _runs(idx):
                when = f"{period_prefix}{r[0] + 1}" + (f" to {period_prefix}{r[-1] + 1}" if len(r) > 1 else "")
                changes.append({"where": where, "field": (field + " · " if field else "") + when,
                                "before": " / ".join(_val(va[i]) for i in r), "after": " / ".join(_val(vb[i]) for i in r)})
        else:
            kind = "added" if path not in a else ("removed" if path not in b else "changed")
            changes.append({"where": where, "field": field or "value", "kind": kind,
                            "before": "" if kind == "added" else _val(va), "after": "" if kind == "removed" else _val(vb)})
    return changes


def history(versions):
    """Newest first: each version with its changes against the previous recorded version."""
    out = []
    for i, v in enumerate(versions):
        prev = versions[i - 1]["config"] if i else None
        ch = diff(prev, v.get("config")) if prev is not None else []
        areas = []
        for c in ch:
            area = (c["where"] or "").split(" · ")[0]
            if area and area not in areas:
                areas.append(area)
        out.append({"id": v.get("id"), "saved_at": v.get("saved_at"), "user": v.get("user") or "",
                    "first": prev is None, "n_changes": len(ch), "areas": areas,
                    "changes": ch[:MAX_CHANGES], "more": max(0, len(ch) - MAX_CHANGES)})
    out.reverse()
    return out
