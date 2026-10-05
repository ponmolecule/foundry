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


def _is_n(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _close(a, b):
    """r286: numbers equal to within float noise are not a change."""
    return _is_n(a) and _is_n(b) and abs(a - b) <= 1e-9 * max(1.0, abs(a), abs(b))


def _pair(a, b):
    """r286: display two values; if they differ but would display identically, add decimals until they don't."""
    va, vb = _val(a), _val(b)
    if va == vb and _is_n(a) and _is_n(b) and a != b:
        for d in range(1, 9):
            fa, fb = f"{a:,.{d}f}", f"{b:,.{d}f}"
            if fa != fb:
                return fa, fb
    return va, vb


def _keyed(d):
    """A period-keyed schedule {"1": v, "2": v, ...}: returns {int key: value} or None."""
    if not isinstance(d, dict) or not d:
        return None
    try:
        m = {int(k): v for k, v in d.items()}
    except (TypeError, ValueError):
        return None
    return m if all(v is None or _is_n(v) for v in m.values()) else None


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


_ID_KEYS = ("series_id", "id", "name", "role", "label")


def _item_key(x, i):
    if isinstance(x, dict):
        for k in _ID_KEYS:
            if x.get(k) not in (None, ""):
                return (k, str(x[k]))
    return ("#", i)


def _summary(v):
    """Short description of a whole added or removed subtree."""
    if isinstance(v, dict):
        nm = next((str(v[k]) for k in ("name", "role", "label") if v.get(k)), "")
        vals = v.get("values")
        extra = f"{len(vals)} values" if isinstance(vals, list) else f"{len(v)} settings"
        return (nm + " · " if nm else "") + extra
    if isinstance(v, list):
        return f"{len(v)} item{'' if len(v) == 1 else 's'}"
    return _val(v)


def diff(old, new):
    """Field-level changes. Lists of objects are matched by identity (series_id, id, name, role, label),
    so removing one item is one 'removed' change rather than a cascade of shifted positions."""
    out = []

    def emit(path, before, after, kind):
        where, field = _label(new if kind != "removed" else old, path)
        out.append({"where": where, "field": field or "value", "kind": kind,
                    "before": before if before is not None else "", "after": after if after is not None else ""})

    def walk(a, b, path):
        ka_, kb_ = _keyed(a), _keyed(b)
        if ka_ is not None and kb_ is not None and (len(ka_) >= 2 or len(kb_) >= 2):
            # r286: a period-keyed schedule is a series: merge consecutive changed periods into ranges
            pre = _prefix(new, path)
            where, field = _label(new, path)
            keys = sorted(set(ka_) | set(kb_))
            chg = [k for k in keys if not (k in ka_ and k in kb_ and (ka_[k] == kb_[k] or _close(ka_[k], kb_[k])))]
            for r in _runs(chg):
                when = f"{pre}{r[0]}" + (f" to {pre}{r[-1]}" if len(r) > 1 else "")
                pairs = [_pair(ka_.get(k), kb_.get(k)) for k in r]
                show = pairs[:8]
                bef = " / ".join(p[0] for p in show) + (" / …" if len(pairs) > 8 else "")
                aft = " / ".join(p[1] for p in show) + (" / …" if len(pairs) > 8 else "")
                out.append({"where": where, "field": (field + " · " if field else "") + when, "kind": "changed",
                            "before": bef, "after": aft})
            return
        if isinstance(a, dict) and isinstance(b, dict):
            for k in list(a.keys()) + [k for k in b.keys() if k not in a]:
                if isinstance(k, str) and k.startswith("_"):
                    continue
                if k not in b:
                    emit(path + (k,), _summary(a[k]), None, "removed")
                elif k not in a:
                    emit(path + (k,), None, _summary(b[k]), "added")
                else:
                    walk(a[k], b[k], path + (k,))
            return
        if _is_num_list(a) and _is_num_list(b) and len(a) == len(b):
            idx = [i for i in range(len(a)) if a[i] != b[i] and not _close(a[i], b[i])]
            pre = _prefix(new, path + ("values",)) if path and path[-1] == "values" else _prefix(new, path + (0,))
            where, field = _label(new, path)
            for r in _runs(idx):
                when = f"{pre}{r[0] + 1}" + (f" to {pre}{r[-1] + 1}" if len(r) > 1 else "")
                out.append({"where": where, "field": (field + " · " if field else "") + when, "kind": "changed",
                            "before": " / ".join(_pair(a[i], b[i])[0] for i in r), "after": " / ".join(_pair(a[i], b[i])[1] for i in r)})
            return
        if isinstance(a, list) and isinstance(b, list) and not _is_num_list(a) and not _is_num_list(b):
            ka = {_item_key(x, i): (i, x) for i, x in enumerate(a)}
            kb = {_item_key(x, i): (i, x) for i, x in enumerate(b)}
            for key, (i, x) in ka.items():
                if key not in kb:
                    emit(path + (i,), _summary(x), None, "removed")
            for key, (j, y) in kb.items():
                if key not in ka:
                    emit(path + (j,), None, _summary(y), "added")
                else:
                    walk(ka[key][1], y, path + (j,))
            return
        if a != b and not _close(a, b):
            if _is_n(a) and _is_n(b):
                pa, pb = _pair(a, b)
                where, field = _label(new, path)
                out.append({"where": where, "field": field, "kind": "changed", "before": pa, "after": pb})
            else:
                emit(path, _val(a), _val(b), "changed")

    walk(old or {}, new or {}, ())
    return out


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
