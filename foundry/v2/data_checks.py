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


def run_checks(cfg, runner=None):
    """Return findings for a configuration. `runner(cfg) -> results` estimates effects (optional)."""
    findings = []
    for path, spec in _explicit_series(cfg):
        vals = spec["values"]
        period = spec.get("period") or ("month" if len(vals) >= 24 else "period")
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
        period = spec.get("period") or ("month" if len(vals) >= 24 else "period")
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
    # effects for the serious findings
    if runner:
        serious = [f for f in findings if f["severity"] == "review"][:MAX_EFFECTS]
        if serious:
            try:
                base_out = _key_outputs(runner(copy.deepcopy(cfg)))
                for f in serious:
                    ep = {"start": f["start"], "end": f["end"], "base": f["base"]}
                    f["effects"] = _effect(cfg, f["path"], ep, base_out, runner)
            except Exception as e:      # effects are optional; a failed estimate never hides a finding
                for f in serious:
                    f["effects_error"] = f"{type(e).__name__}"
    order = {"review": 0, "look": 1, "info": 2}
    findings.sort(key=lambda f: (order[f["severity"]], f["where"]))
    return findings
