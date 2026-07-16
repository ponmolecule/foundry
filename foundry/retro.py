"""Retrodiction harness: the model's projection vs a real bank's filed history.

The empirical half of the 85/15 question: configure the model the way the
bank's organizers would have (application-era assumptions), project, and
compare against what the bank actually filed. This module is the comparison
machinery; the actuals arrive as a small CSV/JSON in the documented format
below (exported from the Call Report substrate — a data drop, not a code
change).

Actuals format (CSV): first column = series label, remaining columns =
consecutive quarters since opening, $000s. Recognized labels (exact, by
design — declaration over guessing): deposits, loans, assets, equity,
net_income. Unknown labels fail closed.

Metrics per series: quarterly error, absolute percentage error, MAPE across
the overlap window, and the terminal-quarter error — the number the 85/15
conversation actually turns on ("did the standardized model land the bank
within X% at quarter N?").
"""
import csv
import io
import json

SERIES_MAP = {
    "deposits": ("bs", "deposits"),
    "loans": ("bs", "netLoans"),
    "assets": ("bs", "totalAssets"),
    "equity": ("bs", "equity"),
    "net_income": ("is", "ni"),
}


def load_actuals(data, filename=""):
    """CSV or JSON -> {"series": {label: [values]}, "quarters": N}."""
    if filename.lower().endswith(".json") or (data.lstrip()[:1] in (b"{", b"[")):
        obj = json.loads(data)
        series = obj.get("series") or obj
    else:
        rows = list(csv.reader(io.StringIO(data.decode("utf-8", errors="replace"))))
        series = {}
        for row in rows:
            if not row or not str(row[0]).strip():
                continue
            label = str(row[0]).strip().lower().replace(" ", "_")
            if label in ("metric", "series", "label"):
                continue
            vals = [float(x) for x in row[1:] if str(x).strip() != ""]
            if vals:
                series[label] = vals
    unknown = [k for k in series if k not in SERIES_MAP]
    if unknown:
        raise ValueError(f"unrecognized actuals series {unknown}; recognized: "
                          f"{sorted(SERIES_MAP)} (exact labels by design)")
    if not series:
        raise ValueError("no actuals series found in the file")
    n = min(len(v) for v in series.values())
    return {"series": {k: v[:n] for k, v in series.items()}, "quarters": n}


def _proj_series(res, key):
    grp, name = SERIES_MAP[key]
    s = res["financials"][grp][name]
    return list(s[1:13]) if len(s) == 13 else list(s[:12])


def compare(res, actuals):
    """Projection run vs actuals -> retrodiction report (deterministic)."""
    import hashlib
    out = {"quarters": 0, "series": [], "summary": {}}
    n = actuals["quarters"]
    for label, act in actuals["series"].items():
        proj = _proj_series(res, label)
        m = min(n, len(proj))
        rows = []
        apes = []
        for t in range(m):
            err = proj[t] - act[t]
            ape = abs(err) / abs(act[t]) if act[t] else None
            if ape is not None:
                apes.append(ape)
            rows.append({"q": t + 1, "projected": proj[t], "actual": act[t],
                          "error": err, "ape": ape})
        mape = sum(apes) / len(apes) if apes else None
        term = rows[-1] if rows else None
        out["series"].append({
            "label": label, "rows": rows,
            "mape_pct": round(mape * 100, 2) if mape is not None else None,
            "terminal_error_pct": (round(term["ape"] * 100, 2)
                                     if term and term["ape"] is not None else None),
        })
        out["quarters"] = max(out["quarters"], m)
    terminal = [s["terminal_error_pct"] for s in out["series"]
                if s["terminal_error_pct"] is not None]
    out["summary"] = {
        "worst_terminal_error_pct": max(terminal) if terminal else None,
        "series_within_15pct_terminal": sum(1 for x in terminal if x <= 15.0),
        "series_compared": len(out["series"]),
        "note": "terminal error <= 15% per series is the working 85/15 read; "
                 "the threshold is a conversation anchor, not a verdict",
    }
    out["report_hash"] = hashlib.sha256(
        json.dumps(out, sort_keys=True, default=str).encode()).hexdigest()[:12]
    return out
