"""r247: Governance & QA data checks.

Read-only. Scans a configuration for inputs that are probably mistakes (isolated spikes in explicit schedules,
likely unit errors, same-month anomalies across fields) and for conventions worth knowing, and estimates the
effect of the serious ones by running the model on a deep copy with the suspect values replaced by their
neighbours' level. Never modifies the configuration it is given and never persists anything.

Severity
  review  peak at least 8x the surrounding level of an otherwise steady schedule
  look    peak at least 3x
  info    a modelling convention that is correct if intended
"""
from __future__ import annotations

import copy
import statistics

REVIEW_RATIO = 8.0
LOOK_RATIO = 3.0
COMPANION_RATIO = 2.0
MIN_LEN = 8
MAX_EFFECTS = 4

_SECTION = {"cac_feeds": "Customer acquisition", "nie_detail": "Operating expense", "workforce": "Workforce",
            "categories": "Expense categories", "lending_products": "Loans", "deposit_products": "Deposits",
            "obs_exposures": "Fee products", "fee_streams": "Fee streams", "cost_pools": "Cost pools"}
_FIELD = {"cost_per_customer": "CAC per customer", "cac": "CAC per customer", "attrition": "attrition rate",
          "attrition_rate": "attrition rate", "conversion_rate": "conversion rate", "spend": "spend",
          "avg_auc_per_customer": "AUC per customer", "count_spec": "count", "compensation_spec": "compensation",
          "flow_spec": "amount", "growth_spec": "growth", "rate": "rate", "driver_specs": "", "driver": "driver",
          "params": "", "spec": "", "channels": "", "value": ""}


def _human(k):
    return _FIELD.get(k, str(k).replace("_", " "))


def _where(cfg, path):
    """('Customer acquisition · SKN Customer Build', 'Channel 1 · CAC per customer · explicit')"""
    a = cfg.get("assumptions", cfg)
    main, detail, node = [], [], cfg
    for i, k in enumerate(path):
        try:
            node = node[k]
        except Exception:
            break
        if k == "assumptions":
            continue
        if isinstance(k, int):
            nm = node.get("name") or node.get("role") or node.get("label") if isinstance(node, dict) else None
            parent = path[i - 1] if i else ""
            if parent == "channels":
                detail.append(f"Channel {k + 1}" + (f" ({nm})" if nm else ""))
            elif nm:
                main.append(str(nm))
            else:
                main.append(f"#{k + 1}")
        elif k in _SECTION:
            main.append(_SECTION[k])
        elif isinstance(path[i - 1] if i else None, str) and path[i - 1] == "cac_feeds":
            main.append(str(k))
        else:
            h = _human(k)
            if h:
                detail.append(h)
    main = [m for j, m in enumerate(main) if j == 0 or m != main[j - 1]]
    return " · ".join(main) or "Configuration", " · ".join(detail)


def _explicit_series(o, path=()):
    if isinstance(o, dict):
        mode = o.get("trajectory") or o.get("mode")
        vals = o.get("values")
        if mode == "explicit" and isinstance(vals, list) and len(vals) >= MIN_LEN \
                and all(v is None or isinstance(v, (int, float)) for v in vals):
            yield path, o
        for k, v in o.items():
            yield from _explicit_series(v, path + (k,))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from _explicit_series(v, path + (i,))


def _episodes(vals, threshold=LOOK_RATIO):
    """Isolated runs of values far above an otherwise steady level that return to it afterwards."""
    pts = [(i, float(v)) for i, v in enumerate(vals) if isinstance(v, (int, float))]
    pos = [v for _, v in pts if v > 0]
    if len(pos) < MIN_LEN:
        return []
    level = statistics.median(pos)
    if level <= 0:
        return []
    hot = [i for i, v in pts if v >= threshold * level]
    eps, cur = [], []
    for i in hot:
        if cur and i != cur[-1] + 1:
            eps.append(cur); cur = []
        cur.append(i)
    if cur:
        eps.append(cur)
    out = []
    n = len(vals)
    for ep in eps:
        s, e = ep[0], ep[-1]
        # trail off: following values that are still clearly elevated belong to the episode
        while e + 1 < n and isinstance(vals[e + 1], (int, float)) and vals[e + 1] >= 1.5 * level:
            e += 1
        before = [float(vals[j]) for j in range(max(0, s - 6), s) if isinstance(vals[j], (int, float))]
        after = [float(vals[j]) for j in range(e + 1, min(n, e + 7)) if isinstance(vals[j], (int, float))]
        if not before or not after:
            continue                       # a level change or an end effect, not an isolated spike
        base = statistics.median(before + after)
        if base <= 0:
            continue
        peak_i = max(range(s, e + 1), key=lambda j: float(vals[j]) if isinstance(vals[j], (int, float)) else -1)
        ratio = float(vals[peak_i]) / base
        if ratio < threshold:
            continue
        out.append({"start": s, "end": e, "peak": peak_i, "base": base, "ratio": ratio,
                    "values": [vals[j] for j in range(s, e + 1)]})
    return out



# ---------------------------------------------------------------------------------------------------------
# r286: coverage of every schedule shape, a local-trend break detector with digit-slip signatures, edits
# checked against the last save, and a catalogue of what the checks catch (served with the findings).
# ---------------------------------------------------------------------------------------------------------
TREND_LOOK_Z = 6.0          # robust deviations from the local trend for "Worth a look"
TREND_REVIEW_Z = 12.0       # ... for "Needs review"
TREND_MIN_REL = 0.20        # and at least 20% away from what the neighbours imply
SERIES_KEYS = ("values", "schedule", "series", "path", "curve")


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _schedule_map(d):
    """A period-keyed schedule such as {"1": 1000, "4": 1300}: returns (sorted keys, values) or None."""
    if not isinstance(d, dict) or len(d) < 2:
        return None
    try:
        ks = sorted(d, key=lambda k: int(k))
    except (TypeError, ValueError):
        return None
    if not all(_num(d[k]) for k in ks):
        return None
    return ks, [float(d[k]) for k in ks]


def _all_series(o, path=()):
    """Every numeric schedule in a configuration: explicit {trajectory|mode: explicit, values}, period-keyed
    level schedules {schedule: {period: value}}, and schedule-like numeric lists under SERIES_KEYS."""
    if isinstance(o, dict):
        mode = o.get("trajectory") or o.get("mode")
        per = o.get("cadence") or o.get("period")
        for k, v in o.items():
            p = path + (k,)
            if k in SERIES_KEYS and isinstance(v, list) and len(v) >= MIN_LEN and all(x is None or _num(x) for x in v):
                kind = "explicit" if mode == "explicit" and k == "values" else str(k)
                yield {"path": p, "values": v, "labels": [str(i + 1) for i in range(len(v))], "period": per, "kind": kind}
                continue
            if k in SERIES_KEYS:
                sm = _schedule_map(v)
                if sm and len(sm[0]) >= 3:
                    yield {"path": p, "values": sm[1], "labels": sm[0], "period": per, "kind": "level schedule", "keyed": True}
                    continue
            yield from _all_series(v, p)
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from _all_series(v, path + (i,))


def _digit_candidates(v):
    """Values one keystroke away: a digit added, dropped, doubled or transposed, or a factor of 10/100/1000."""
    out = []
    neg = v < 0
    a = abs(v)
    txt = (f"{a:.6f}".rstrip("0").rstrip(".")) if not float(a).is_integer() else str(int(a))
    digits = [i for i, ch in enumerate(txt) if ch.isdigit()]
    for i in digits:                                       # an extra digit
        t = txt[:i] + txt[i + 1:]
        if t and t not in (".",) and any(c.isdigit() for c in t):
            out.append((float(t), f"an extra {txt[i]}" + (" at the start" if i == digits[0] else "")))
    for pos in range(len(txt) + 1):                        # a digit left out
        for d in "0123456789":
            t = txt[:pos] + d + txt[pos:]
            if t[0] == "0" and len(t) > 1 and t[1] != ".":
                continue
            try:
                out.append((float(t), f"a missing {d}"))
            except ValueError:
                pass
    for a_i, b_i in zip(digits, digits[1:]):              # two adjacent digits swapped
        if b_i == a_i + 1 and txt[a_i] != txt[b_i]:
            t = txt[:a_i] + txt[b_i] + txt[a_i] + txt[b_i + 1:]
            out.append((float(t), f"digits {txt[a_i]}{txt[b_i]} swapped"))
    for f, lab in ((10, "10x too large"), (100, "100x too large"), (1000, "1,000x too large (perhaps $ instead of $000s)")):
        out.append((a / f, lab))
    for f, lab in ((10, "10x too small"), (100, "100x too small"), (1000, "1,000x too small (perhaps $000s instead of $)")):
        out.append((a * f, lab))
    return [((-x if neg else x), lab) for x, lab in out]


def _signature(actual, expected, tol):
    """The one-keystroke explanation that best returns `actual` to `expected`, if any is within `tol`."""
    best = None
    for cand, lab in _digit_candidates(actual):
        err = abs(cand - expected)
        if err <= tol and (best is None or err < best[0]):
            best = (err, cand, lab)
    return None if best is None else {"value": best[1], "why": best[2]}


def _trend_breaks(vals):
    """Isolated values far from what their neighbours imply. Robust scale (MAD of local residuals), iterative
    so one outlier does not contaminate its neighbours, and only points beyond BOTH neighbours (a genuine step
    change sits level with one neighbour and is never flagged). Edges are flagged only with a digit-slip
    signature."""
    x = [float(v) if _num(v) else None for v in vals]
    idx = [i for i, v in enumerate(x) if v is not None]
    if len(idx) < MIN_LEN:
        return []
    work = dict((i, x[i]) for i in idx)
    out, flagged = [], set()

    def residuals():
        res = {}
        for k, i in enumerate(idx):
            if 0 < k < len(idx) - 1:
                l, r = idx[k - 1], idx[k + 1]
                exp = work[l] + (work[r] - work[l]) * (i - l) / (r - l)
            elif len(idx) >= 3:
                if k == 0:
                    a, b = idx[1], idx[2]
                else:
                    a, b = idx[-2], idx[-3]
                exp = work[a] + (work[a] - work[b]) * (i - a) / (a - b)
            else:
                continue
            res[i] = (work[i] - exp, exp)
        return res

    for _ in range(4):
        res = residuals()
        mags = sorted(abs(r) for j, (r, _) in res.items() if j not in flagged)
        if len(mags) < 3:
            break
        med = mags[len(mags) // 2]
        level = statistics.median(abs(v) for v in work.values()) or 1.0
        scale = max(1.4826 * med, 0.002 * level, 1e-12)
        best = None
        # interior points first: edges are judged only once interior outliers are resolved, so an edge is
        # never scored against an extrapolation contaminated by a neighbouring spike
        for want_edge in (False, True):
            for k, i in enumerate(idx):
                if i in flagged or i not in res:
                    continue
                edge = k == 0 or k == len(idx) - 1
                if edge != want_edge:
                    continue
                r, exp = res[i]
                z = abs(r) / scale
                rel = abs(r) / max(abs(exp), 1e-12)
                if not edge:
                    l, rr = work[idx[k - 1]], work[idx[k + 1]]
                    if not ((x[i] > max(l, rr)) or (x[i] < min(l, rr))):
                        continue
                if z >= TREND_LOOK_Z and rel >= TREND_MIN_REL and (best is None or z > best[0]):
                    best = (z, i, r, exp, rel, edge)
            if best is not None:
                break
        if best is None:
            break
        z, i, r, exp, rel, edge = best
        sig = _signature(x[i], exp, max(1.5 * scale, 0.03 * abs(exp)) if edge else max(3 * scale, 0.10 * abs(exp)))
        if edge and not sig:
            flagged.add(i)
            continue
        out.append({"i": i, "actual": x[i], "expected": exp, "z": z, "rel": rel, "scale": scale, "signature": sig})
        flagged.add(i)
        work[i] = exp                              # re-score the rest as if this value were on trend
    return out


def _get(o, path):
    for k in path:
        o = o[k] if isinstance(o, (dict, list)) else None
        if o is None:
            return None
    return o


def _series_value(cfg, s, label):
    node = _get(cfg, s["path"])
    if s.get("keyed"):
        return node.get(label) if isinstance(node, dict) else None
    try:
        return node[int(label) - 1]
    except (TypeError, IndexError, ValueError):
        return None


def _set_series_value(cfg, s, label, value):
    node = _get(cfg, s["path"])
    if s.get("keyed"):
        node[label] = value
    else:
        node[int(label) - 1] = value


def _per_word(s):
    p = str(s.get("period") or "")
    return {"quarter": "Q", "year": "Y", "annual": "Y", "month": "M"}.get(p, "M" if len(s["values"]) >= 24 else "")


CATALOG = [
    {"check": "Digit slip against the trend",
     "catches": "A value one keystroke away from what its neighbours imply: an extra, missing or doubled digit, or two adjacent digits swapped.",
     "example": "634 typed as 1,634 in a schedule running 123, 634, 1,106, 1,200, ...",
     "severity": "Needs review", "where": "Every numeric schedule: explicit paths, level schedules, count and balance series."},
    {"check": "Unit slip (x10 / x100 / x1,000)",
     "catches": "A value off by a power of ten against its neighbours, including $ entered where $000s are expected.",
     "example": "2,000 entered as 2,000,000 in a $000s series; 4.5% entered as 45.",
     "severity": "Needs review", "where": "Every numeric schedule."},
    {"check": "Isolated break from the trend",
     "catches": "A single value far outside the series' own period-to-period movement, beyond both neighbours, that has no one-keystroke explanation.",
     "example": "A balance series rising about 30 a month with one month at +900.",
     "severity": "Worth a look (Needs review when extreme)", "where": "Every numeric schedule; interior points (edges only with a digit-slip explanation)."},
    {"check": "Edited since the last save",
     "catches": "A value changed since the last save by a digit slip or a factor of ten, even where the series is noisy or the value sits at an edge.",
     "example": "Changed from 634 to 1,634 since the last save.",
     "severity": "Needs review", "where": "Values that differ from the last save (when the engagement is saved)."},
    {"check": "Isolated spike on a steady level",
     "catches": "A run of values at 3x or more of an otherwise steady level that returns to it; 8x or more is serious.",
     "example": "Monthly attrition steady near 1.4% with one month at 17%.",
     "severity": "Worth a look / Needs review", "where": "Explicit schedules."},
    {"check": "Annual rate in a monthly series; percentage as a whole number",
     "catches": "Spikes near 12x (an annual figure in a monthly schedule) or near 100x (a percentage typed as a whole number).",
     "example": "A monthly rate of 0.5% entered once as 6%.",
     "severity": "Hint on the finding", "where": "Explicit schedules."},
    {"check": "Same-period companions",
     "catches": "A smaller jump (2x or more) in the same period as a flagged change elsewhere, which usually means one stale paste.",
     "example": "Attrition and churn both jumping in M7.",
     "severity": "As the related finding", "where": "Explicit schedules."},
    {"check": "Annual attrition at period end",
     "catches": "An annual attrition rate taken in month 12 under monthly flows, which keeps average balances above a straight line.",
     "example": "Customer acquisition feeds with year-period attrition and period-end timing.",
     "severity": "Info", "where": "Customer acquisition feeds."},
]
LIMITS = [
    "A wrong value that still fits the trend (for example 1,206 instead of 1,200) is not flagged; it is indistinguishable from data.",
    "A whole schedule entered in the wrong unit is consistent with itself and is not flagged against its own trend.",
    "Single values and short schedules (fewer than 6 points) have no trend to compare with; edits to them are caught only against the last save.",
    "A slip in the first or last period of a steeply ramping schedule can be attributed to its neighbour by the trend check; the edited-since-save check still names the changed value.",
    "Judgments, methods and economic reasonableness are reviewed elsewhere (Executive Summary challenge layer), not here.",
]


def trend_findings(cfg, saved=None):
    """r286 findings: digit slips, unit slips and isolated trend breaks in every schedule, plus edits since
    the last save that look like a one-keystroke slip."""
    out = []
    for s in _all_series(cfg):
        per = _per_word(s)
        main, detail = _where(cfg, s["path"])
        # r286: a readable field name, and the schedule kind appended only if the location lacks it
        if s["kind"] and s["kind"] not in detail:
            detail = (detail + " \u00b7 " + s["kind"]).strip(" \u00b7")
        p = [str(k) for k in s["path"]]
        field = ("Count" if "level_schedule" in p else
                 _human(p[-2]) if p[-1] in SERIES_KEYS and len(p) > 1 and not p[-2].isdigit() else _human(p[-1]))
        hits = {}
        for b in _trend_breaks(s["values"]):
            lab = s["labels"][b["i"]]
            sig = b["signature"]
            sev = "review" if (sig or b["z"] >= TREND_REVIEW_Z and b["rel"] >= 0.5) else "look"
            hits[lab] = {"severity": sev, "path": list(s["path"]), "where": main, "detail": detail, "field": field,
                         "kind": "trend", "label": lab, "period_word": per, "actual": b["actual"], "expected": b["expected"],
                         "headline_values": [_fmt(b["expected"]), _fmt(b["actual"])],
                         "signature": (f"{_fmt(b['actual'])} looks like {_fmt(sig['value'])} with {sig['why']}" if sig else ""),
                         "suggest": sig["value"] if sig else b["expected"], "z": round(b["z"], 1),
                         "effects": None, "same_period_as": [], "start": b["i"], "end": b["i"], "peak": b["i"], "period": s.get("period") or "period"}
        if saved is not None:
            for j, lab in enumerate(s["labels"]):
                old = _series_value(saved, s, lab)
                new = s["values"][j]
                if not (_num(old) and _num(new)) or abs(float(old) - float(new)) <= 1e-9 * max(1.0, abs(float(old))):
                    continue
                sig = _signature(float(new), float(old), max(1e-9, 0.002 * abs(float(old))))
                f = hits.get(lab)
                if f:
                    f["changed_from"] = _fmt(old)
                elif sig and abs(float(new) - float(old)) >= 0.2 * max(abs(float(old)), 1e-12):
                    hits[lab] = {"severity": "review", "path": list(s["path"]), "where": main, "detail": detail, "field": field,
                                 "kind": "edit", "label": lab, "period_word": per, "actual": float(new), "expected": float(old),
                                 "headline_values": [_fmt(old), _fmt(new)], "changed_from": _fmt(old),
                                 "signature": f"{_fmt(new)} looks like {_fmt(sig['value'])} with {sig['why']}",
                                 "suggest": float(old), "effects": None, "same_period_as": [],
                                 "start": j, "end": j, "peak": j, "period": s.get("period") or "period"}
        out.extend(hits[k] for k in sorted(hits, key=lambda k: s["labels"].index(k)))
    return out


def _trend_effect(cfg, f, s_lookup, base_out, runner):
    cf = copy.deepcopy(cfg)
    s = s_lookup[tuple(f["path"])]
    _set_series_value(cf, s, f["label"], f["suggest"])
    out = _key_outputs(runner(cf))
    return [{"measure": k, "delta": v - out[k], "without": out[k], "with": v}
            for k, v in base_out.items() if k in out and abs(v - out[k]) >= max(1.0, abs(out[k]) * 1e-4)]


def _field_of(f):
    parts = [x for x in (f.get("detail") or "").split(" · ") if x and x != "explicit"]
    return parts[-1] if parts else f.get("where", "")


def _fmt(v):
    v = float(v)
    if abs(v) < 1:
        return f"{v * 100:.2f}%" if abs(v) < 0.995 else f"{v:,.2f}"
    return f"{v:,.2f}" if abs(v) < 100 else f"{v:,.0f}"


def _key_outputs(R):
    R = R.get("public", R) if isinstance(R, dict) else {}
    fin = R.get("financials") or {}
    is_ = fin.get("is") or {}
    bs = fin.get("bs") or {}
    out = {}
    for name, feed in (R.get("customer_acquisition") or {}).items():
        if isinstance(feed, dict):
            c, u = feed.get("customerEndByPeriod"), feed.get("aucEndByPeriod")
            if isinstance(c, list) and c:
                out[f"Ending customers · {name}"] = c[-1] or 0
            if isinstance(u, list) and u:
                out[f"Ending AUC · {name} ($000s)"] = u[-1] or 0
    if isinstance(is_.get("ni"), list):
        out["Net income over the horizon ($000s)"] = sum(x or 0 for x in is_["ni"])
    if isinstance(is_.get("fees"), list):
        out["Fee income over the horizon ($000s)"] = sum(x or 0 for x in is_["fees"])
    dep = bs.get("deposits")
    if isinstance(dep, list) and dep:
        out["Ending deposits ($000s)"] = dep[-1] or 0
    return out


def _effect(cfg, path, ep, base_out, runner):
    cf = copy.deepcopy(cfg)
    node = cf
    for k in path:
        node = node[k]
    for j in range(ep["start"], ep["end"] + 1):
        node["values"][j] = ep["base"]
    out = _key_outputs(runner(cf))
    lines = []
    for k, v in base_out.items():
        if k in out:
            d = v - out[k]
            if abs(d) >= max(1.0, abs(out[k]) * 1e-4):
                lines.append({"measure": k, "delta": d, "without": out[k], "with": v})
    return lines


def run_checks(cfg, runner=None, saved=None):
    """Return findings for a configuration. `runner(cfg) -> results` estimates effects (optional); `saved`
    (the last saved configuration) enables the edited-since-save check."""
    findings = []
    for path, spec in _explicit_series(cfg):
        vals = spec["values"]
        period = spec.get("cadence") or spec.get("period") or ("month" if len(vals) >= 24 else "period")
        for ep in _episodes(vals):
            sev = "review" if ep["ratio"] >= REVIEW_RATIO else "look"
            main, detail = _where(cfg, path)
            hint = ""
            if period == "month" and 10.5 <= ep["ratio"] <= 13.5:
                hint = "This is close to the surrounding monthly level expressed annually: possibly an annual rate in a monthly series."
            elif 85 <= ep["ratio"] <= 115:
                hint = "About 100x the surrounding level: possibly a percentage entered as a whole number."
            seq = ", ".join(_fmt(v) for v in ep["values"][1:4]) if ep["end"] > ep["start"] else ""
            findings.append({
                "severity": sev, "path": list(path), "where": main, "detail": (detail + " · explicit").strip(" ·"),
                "start": ep["start"], "end": ep["end"], "peak": ep["peak"], "period": period,
                "base": ep["base"], "ratio": round(ep["ratio"], 2),
                "headline_values": [_fmt(ep["base"]), _fmt(vals[ep["peak"]])],
                "then": seq, "hint": hint, "effects": None, "same_period_as": []})
    # companions: a smaller jump (2x or more) in the same period as a finding elsewhere is flagged too,
    # since fields that jump together usually point to one stale or mistaken paste
    starts = {f["start"]: f["severity"] for f in findings}
    seen = {(tuple(f["path"]), f["start"]) for f in findings}
    for path, spec in _explicit_series(cfg):
        vals = spec["values"]
        period = spec.get("cadence") or spec.get("period") or ("month" if len(vals) >= 24 else "period")
        for ep in _episodes(vals, threshold=COMPANION_RATIO):
            if ep["start"] not in starts or (tuple(path), ep["start"]) in seen:
                continue
            main, detail = _where(cfg, path)
            findings.append({
                "severity": starts[ep["start"]], "path": list(path), "where": main,
                "detail": (detail + " · explicit").strip(" ·"), "start": ep["start"], "end": ep["end"],
                "peak": ep["peak"], "period": period, "base": ep["base"], "ratio": round(ep["ratio"], 2),
                "headline_values": [_fmt(ep["base"]), _fmt(vals[ep["peak"]])], "then": "", "hint": "",
                "companion": True, "effects": None, "same_period_as": []})
            seen.add((tuple(path), ep["start"]))
    # same-period anomalies across fields
    for f in findings:
        f["same_period_as"] = [_field_of(g) for g in findings if g is not f and g["start"] == f["start"]]
    # conventions (info): annual attrition applied at period end under monthly flows
    a = cfg.get("assumptions", {})
    for name, feed in (a.get("cac_feeds") or {}).items():
        if not isinstance(feed, dict):
            continue
        ds = feed.get("driver_specs") or {}
        att = next((ds[k] for k in ds if "attrition" in k and isinstance(ds[k], dict)), None)
        if att and (att.get("period") == "year") and feed.get("intra_period_path", "monthly_flows") == "monthly_flows" \
                and feed.get("attrition_timing", "period_end") == "period_end":
            findings.append({"severity": "info", "path": ["assumptions", "cac_feeds", name], "where": f"Customer acquisition · {name}",
                             "detail": "attrition timing", "convention": "annual_attrition_period_end",
                             "effects": None, "same_period_as": []})
    # r286: trend breaks, digit and unit slips in every schedule; edits since the last save
    # a trend finding inside an already-reported spike episode (same series, any month of the run) is the
    # same problem; spike findings point at the schedule object, trend findings at its values list
    spiked = {(tuple(f["path"]), j) for f in findings if "start" in f and "end" in f
              for j in range(f["start"], f["end"] + 1)}
    for t in trend_findings(cfg, saved):
        tp = tuple(t["path"])
        keys = {tp} | ({tp[:-1]} if tp and tp[-1] == "values" else set())
        if not any((k, t["peak"]) in spiked for k in keys):
            findings.append(t)
    # effects for the serious findings
    if runner:
        serious = [f for f in findings if f["severity"] == "review"][:MAX_EFFECTS]
        if serious:
            try:
                base_out = _key_outputs(runner(copy.deepcopy(cfg)))
                s_lookup = {tuple(x["path"]): x for x in _all_series(cfg)}
                for f in serious:
                    if f.get("kind") in ("trend", "edit"):
                        f["effects"] = _trend_effect(cfg, f, s_lookup, base_out, runner)
                    else:
                        ep = {"start": f["start"], "end": f["end"], "base": f["base"]}
                        f["effects"] = _effect(cfg, f["path"], ep, base_out, runner)
            except Exception as e:      # effects are optional; a failed estimate never hides a finding
                for f in serious:
                    f["effects_error"] = f"{type(e).__name__}"
    order = {"review": 0, "look": 1, "info": 2}
    findings.sort(key=lambda f: (order[f["severity"]], f["where"]))
    return findings
