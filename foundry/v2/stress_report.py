"""r499: stress reporting. Annual statements (Tables X and Y), capital against three threshold tiers,
dollar cushions and dates, for one base and one stressed result.

Presentation only: it reads engine results and never changes a calculation. Aggregation reuses the
business-plan exhibit's model (bpt_enhanced._Model), so stress tables and the BPT agree line for line.
"""
from __future__ import annotations

import math

STRESS_KEYS = ("stress_scenarios", "stress_reporting", "liquidity_stress")
RATIOS = (("leverage", "Tier 1 leverage"), ("cet1_rwa", "CET1 / RWA"), ("tier1_rwa", "Tier 1 / RWA"),
          ("total_rwa", "Total capital / RWA"))
TIERS = (("regulatory", "Regulatory"), ("commitment", "Charter commitment"), ("policy", "Bank policy"))
NA = "not separately available"


def base_only(cfg):
    return {k: v for k, v in (cfg or {}).items() if k not in STRESS_KEYS}


def settings(cfg) -> dict:
    s = dict((cfg or {}).get("stress_reporting") or {})
    s.setdefault("deposit_classes", {})
    s.setdefault("expense_classes", {})
    s.setdefault("policy_minimums", {})
    return s


def settings_snapshot(cfg) -> dict:
    """The reporting settings that shape a package (classifications, policy minimums, window), without the
    primary-case pointer. Stored with each run and each issued package so a package can be reproduced."""
    s = settings(cfg)
    s.pop("primary_run_id", None)
    return s


def settings_fingerprint(snapshot) -> str:
    """Fingerprint of a settings snapshot (from ``settings_snapshot``)."""
    import hashlib
    import json as _json
    s = {k: v for k, v in (snapshot or {}).items() if k != "primary_run_id"}
    return hashlib.sha256(_json.dumps(s, sort_keys=True, default=str).encode()).hexdigest()[:16]


def _n(x):
    try:
        v = float(x)
        return v if math.isfinite(v) else 0.0
    except (TypeError, ValueError):
        return 0.0


# ------------------------------------------------------------------ the reporting window (one definition)
def report_window(cfg) -> dict:
    """The window every stress table, minimum, cushion and attribution uses.

    Default: the whole projection. ``stress_reporting.window_periods`` narrows it (for example a
    three-year plan inside a longer model). Years are model years from opening; a year with fewer
    periods than a full year is flagged partial and its rates are annualized."""
    a = (cfg or {}).get("assumptions") or {}
    ppy = int(a.get("periods_per_year") or 4)
    n = int(a.get("n_periods") or 12)
    w = settings(cfg).get("window_periods")
    w = n if not isinstance(w, int) or w < 1 or w > n else w
    years = []
    for y in range(1, (w + ppy - 1) // ppy + 1):
        idxs = [i for i in ((y - 1) * ppy + k for k in range(ppy)) if i < w]
        if idxs:
            years.append({"label": f"Year {y}", "partial": len(idxs) < ppy, "stock_idx": idxs[-1], "flow_idxs": idxs})
    pre = {12: "M", 4: "Q", 1: "Y"}.get(ppy, "P")
    return {"periods": w, "ppy": ppy, "n": n, "label": f"{pre}1 to {pre}{w}", "years": years,
            "basis": "stress_reporting.window_periods" if w != n else "full projection"}


def period_label(cfg, p):
    ppy = int(((cfg or {}).get("assumptions") or {}).get("periods_per_year") or 4)
    return f"{ {12: 'M', 4: 'Q', 1: 'Y'}.get(ppy, 'P')}{p}" if p else None


# ------------------------------------------------------------------ classification (explicit, user-confirmed)
def _pkey(p):
    return str(p.get("source_catalog_id") or p.get("stable_id") or ("name:" + str(p.get("name") or "")))


def deposit_classification(cfg, res=None) -> list[dict]:
    """Every deposit product with its confirmed class (ib / nib / None) and a suggestion.

    The suggestion comes from the product's pricing; it never decides the reporting category."""
    a = (cfg or {}).get("assumptions") or {}
    cls = settings(cfg)["deposit_classes"]
    out = []
    for p in a.get("deposit_products") or []:
        if not isinstance(p, dict):
            continue
        floating = p.get("rate_type") == "float"
        paid = _n(p.get("rate_paid_ann")) > 0 or _n(p.get("yield_ann")) > 0
        sug = "ib" if (floating or paid) else "nib"
        k = _pkey(p)
        c = cls.get(k)
        out.append({"key": k, "name": p.get("name") or "Deposit product", "suggested": sug,
                    "class": c if c in ("ib", "nib") else None,
                    "why": "floating rate" if floating else ("pays a rate" if paid else "no rate paid")})
    return out


def expense_classification(cfg) -> list[dict]:
    a = (cfg or {}).get("assumptions") or {}
    cls = settings(cfg)["expense_classes"]
    out = []
    for i, c in enumerate(((a.get("nie_detail") or {}).get("categories")) or []):
        k = str(c.get("series_id") or ("name:" + str(c.get("name") or i)))
        v = cls.get(k)
        out.append({"key": k, "index": i, "name": c.get("name") or f"Category {i + 1}",
                    "class": v if v in ("salaries", "premises", "other") else "other"})
    return out


# ------------------------------------------------------------------ thresholds: three tiers, never merged
def thresholds(cfg, res) -> dict:
    """{ratio: {tier: {"value": percent, "source": str} or None}} for the regulatory threshold, the
    charter or supervisory commitment and the bank policy minimum. Policy is blank until entered."""
    from .regparams import REG_PARAMS
    cap = (res or {}).get("capital") or {}
    pca = REG_PARAMS["pca_well_capitalized"]
    cb = cap.get("cblr_tiering") or {}
    pol = settings(cfg)["policy_minimums"]
    mct = (cfg or {}).get("management_capital_target")
    con = next((c for c in ((cfg or {}).get("constraints") or []) if c.get("key") == "leverage_min"), None)
    out = {}
    for r, _lab in RATIOS:
        reg = {"value": round(pca[r] * 100, 4), "source": "Well capitalized, 12 CFR 324.403 / 12 CFR 6.4"}
        if r == "leverage" and cb.get("elected"):
            reg = {"value": float(cb.get("requirement_pct")), "source": "Community bank leverage ratio framework (elected)"}
        com = None
        if r == "leverage" and con is not None and con.get("value") is not None:
            com = {"value": round(float(con["value"]) * 100, 4), "source": con.get("source") or con.get("text") or "Engagement constraint"}
        p = pol.get(r)
        if isinstance(p, dict) and p.get("value") is not None:
            p = {"value": float(p["value"]), "source": p.get("source") or "Bank capital policy", "effective": p.get("effective")}
        elif isinstance(p, (int, float)) and not isinstance(p, bool):
            p = {"value": float(p), "source": "Bank capital policy"}
        elif r == "leverage" and mct is not None:
            p = {"value": round(float(mct) * 100, 4), "source": "Management capital target (engagement)"}
        else:
            p = None
        out[r] = {"regulatory": reg, "commitment": com, "policy": p}
    out["_cblr_elected"] = bool(cb.get("elected"))
    return out


def _cap_series(res):
    cap = (res or {}).get("capital") or {}
    rows, st = cap.get("rows") or {}, cap.get("standardized") or {}
    rt = st.get("ratios") or {}
    pct = lambda xs: [None if x is None else _n(x) for x in (xs or [])]
    return {
        "leverage": (pct([None if x is None else _n(x) * 100 for x in rows.get("leverage") or []]), rows.get("tier1") or [], rows.get("avg_assets_net") or []),
        "cet1_rwa": (pct(rt.get("cet1_rwa")), st.get("cet1") or [], st.get("rwa") or []),
        "tier1_rwa": (pct(rt.get("tier1_rwa")), st.get("tier1") or [], st.get("rwa") or []),
        "total_rwa": (pct(rt.get("total_rwa")), st.get("total") or [], st.get("rwa") or []),
    }


def capital_assessment(cfg, res, window=None) -> dict:
    """Lowest ratio and lowest dollar cushion per ratio and tier inside the window, each with its own date.

    Cushion = capital numerator less floor x the ratio's own denominator ($000s). The lowest cushion
    can fall in a different period from the lowest ratio. A shortfall here is a diagnostic gap, not a
    modeled capital raise."""
    w = (window or report_window(cfg))["periods"]
    th = thresholds(cfg, res)
    S = _cap_series(res)
    out = {"window": w, "cblr_elected": th["_cblr_elected"], "ratios": {}}
    for r, lab in RATIOS:
        ratio, num, den = S[r]
        ratio, num, den = ratio[:w], num[:w], den[:w]
        avail = [i for i, x in enumerate(ratio) if x is not None]
        if not avail:
            out["ratios"][r] = {"label": lab, "available": False}
            continue
        lo = min(avail, key=lambda i: ratio[i])
        tiers = {}
        for t, tlab in TIERS:
            f = th[r][t]
            if f is None:
                tiers[t] = None
                continue
            fl = f["value"] / 100.0
            cush = [(_n(num[i]) - fl * _n(den[i])) if i < len(num) and i < len(den) else None for i in range(len(ratio))]
            ci = [i for i, x in enumerate(cush) if x is not None]
            cmin = min(ci, key=lambda i: cush[i]) if ci else None
            breach = next((i for i in avail if ratio[i] < f["value"] - 1e-9), None)
            tiers[t] = {"label": tlab, "floor": f["value"], "source": f["source"],
                        "min_cushion": None if cmin is None else round(cush[cmin], 3),
                        "min_cushion_period": None if cmin is None else cmin + 1,
                        "first_breach_period": None if breach is None else breach + 1,
                        "status": "below" if breach is not None else ("thin" if ratio[lo] - f["value"] < 0.5 else "above")}
        out["ratios"][r] = {"label": lab, "available": True, "min": round(ratio[lo], 4), "min_period": lo + 1,
                            "year_end": [None if y["stock_idx"] >= len(ratio) else ratio[y["stock_idx"]] for y in (window or report_window(cfg))["years"]],
                            "tiers": tiers}
    binding = [(r, t, v["first_breach_period"]) for r, x in out["ratios"].items() if x.get("available")
               for t, v in x["tiers"].items() if v and v["first_breach_period"]]
    out["first_breach"] = None if not binding else dict(zip(("ratio", "tier", "period"), min(binding, key=lambda z: z[2])))
    return out


# ------------------------------------------------------------------ annual statements (Tables X and Y)
def _model(cfg, res):
    from .bpt_enhanced import _Model
    return _Model(cfg, res)


def _sum(*vs):
    vs = [v for v in vs if isinstance(v, list)]
    if not vs:
        return None
    n = max(len(v) for v in vs)
    return [sum(_n(v[i]) if i < len(v) else 0.0 for v in vs) for i in range(n)]


def _minus(a, b):
    if a is None:
        return None
    b = b or []
    return [_n(x) - (_n(b[i]) if i < len(b) else 0.0) for i, x in enumerate(a)]


def statements(cfg, res, window=None) -> dict:
    """Annual values for every Table X and Y row. Stocks at year end; flows summed over the year."""
    win = window or report_window(cfg)
    Y = win["years"]
    m = _model(cfg, res)
    bs, is_ = m.bs, m.is_
    st = lambda s: m.stock(s, Y) if s is not None else [None] * len(Y)
    fl = lambda s: m.flow(s, Y) if s is not None else [None] * len(Y)
    afs = _sum(*[bs.get(k) for k in ("afs", "sec", "afsBook")])
    htm = _sum(*[bs.get(k) for k in ("htm", "htmBook")])
    hfs = bs.get("hfs")
    hfi = _minus(bs.get("grossLoans"), hfs)
    alll = [-_n(x) for x in (bs.get("alll") or [])] if bs.get("alll") else None
    prem = bs.get("premises")
    intang = m.intangibles_series()
    listed = _sum(bs.get("cash"), afs, htm, hfs, hfi, alll, prem, intang)
    other_a = _minus(bs.get("totalAssets"), listed)
    # deposits by explicit classification
    dcls = {d["key"]: d["class"] for d in deposit_classification(cfg)}
    ib, nib, unclassified = [], [], []
    for p, c in zip(m.dep, m.dep_cfg):
        k = dcls.get(_pkey(c)) if c else None
        (ib if k == "ib" else nib if k == "nib" else unclassified).append(p.get("bal"))
    dep_ok = not unclassified
    borrowed = _sum(*[bs.get(k) for k in ("borrow", "borrowings")])
    tl = m.total_liab_series()
    other_l = _minus(_minus(tl, bs.get("deposits")), borrowed)
    # income statement
    ii = m.interest_income()
    ie = m.interest_expense()
    nonii = m.nonint_income()
    svc = _sum(*[p.get("fees") for p in m.dep])
    nie = m.nonint_expense()
    sal = is_.get("workforceComp")
    ecls = expense_classification(cfg)
    cats = m.opex_categories() if any(e["class"] != "other" for e in ecls) else []
    by = {"salaries": [], "premises": []}
    for e in ecls:
        if e["class"] in by and e["index"] < len(cats):
            by[e["class"]].append(cats[e["index"]][1])
    sal_all = _sum(sal, *by["salaries"]) if (sal is not None or by["salaries"]) else None
    prem_x = _sum(is_.get("depreciationExpense"), *by["premises"])
    oth_x = _minus(_minus(nie, sal_all), prem_x)
    # ratios (time-weighted average balances; partial years annualized)
    ann = [win["ppy"] / float(len(y["flow_idxs"])) for y in Y]
    ata = m.avg(m.period_avg(bs.get("totalAssets")), Y)
    aeq = m.avg(m.period_avg(bs.get("equity")), Y)
    ni_y, nii_y, nonii_y, nie_y = fl(is_.get("ni")), fl(m.nii()), fl(nonii), fl(nie)
    div = lambda a, b: None if a is None or not b else a / b * 100.0
    capr = _cap_series(res)
    ye = lambda r: [None if y["stock_idx"] >= len(capr[r][0]) else capr[r][0][y["stock_idx"]] for y in Y]
    X = [
        ("g:assets", "Assets"),
        ("cash", "Cash and Balances Due from Banks", st(bs.get("cash"))),
        ("afs", "AFS Debt Securities", st(afs)),
        ("?htm", "HTM Debt Securities", st(htm) if htm else [0.0] * len(Y)),     # shown when either case holds any
        ("?hfs", "Loans Held for Sale", st(hfs) if hfs else [0.0] * len(Y)),
        ("hfi", "Loans Held for Investment", st(hfi)),
        ("acl", "Allowance for Credit Losses", st(alll)),
        ("premises", "Premises and Fixed Assets", st(prem)),
        ("intangibles", "Intangible Assets", st(intang)),
        ("other_assets", "Other Assets", st(other_a)),
        ("t:total_assets", "Total Assets", st(bs.get("totalAssets"))),
        ("g:liabilities", "Liabilities and Equity"),
        ("nib", "Noninterest-Bearing Deposits", st(_sum(*nib)) if dep_ok else None),
        ("ib", "Interest-Bearing Deposits", st(_sum(*ib)) if dep_ok else None),
        *([] if dep_ok else [("deposits", "Deposits (classification incomplete)", st(bs.get("deposits")))]),
        ("borrowed", "Other Borrowed Money", st(borrowed)),
        ("other_liab", "Other Liabilities", st(other_l)),
        ("t:total_liab", "Total Liabilities", st(tl)),
        ("t:equity", "Equity", st(bs.get("equity"))),
        ("g:capital", "Capital Ratios"),
        ("%:leverage", "Tier 1 Leverage Ratio", ye("leverage")),
        ("%:cet1_rwa", "CET 1 Capital Ratio", ye("cet1_rwa")),
        ("%:tier1_rwa", "Tier 1 Capital Ratio", ye("tier1_rwa")),
        ("%:total_rwa", "Total Capital Ratio", ye("total_rwa")),
    ]
    Yr = [
        ("t:ii", "Interest Income", fl(ii)),
        ("s:ii_loans", "Interest and Fee Income on Loans", fl(is_.get("loanInt"))),
        ("s:ii_cash", "Interest Income on Cash", fl(is_.get("cashInt"))),
        ("s:ii_sec", "Interest Income on Securities", fl(is_.get("secInt"))),
        ("t:ie", "Interest Expense", fl(ie)),
        ("s:ie_dep", "Interest on Deposits", fl(is_.get("depExp"))),
        ("s:ie_other", "Other Interest Expense", fl(_minus(ie, is_.get("depExp")))),
        ("t:nii", "Net Interest Income", nii_y),
        ("prov", "Provision for Loan and Lease Losses", fl(is_.get("prov"))),
        ("t:nonii", "Noninterest Income", nonii_y),
        ("s:svc", "Service Charges on Deposit Accounts", fl(svc)),
        ("s:nonii_other", "Other Noninterest Income", fl(_minus(nonii, svc))),
        ("t:nie", "Noninterest Expense", nie_y),
        ("s:salaries", "Salaries and Employee Benefits", fl(sal_all) if sal_all is not None else None),
        ("s:premises_x", "Expenses of Premises and Fixed Assets", fl(prem_x)),
        ("s:nie_other", "Other Noninterest Expense", fl(oth_x)),
        ("t:pretax", "Pre-Tax Net Income", fl(is_.get("pretax"))),
        ("tax", "Taxes", fl(is_.get("tax"))),
        ("t:ni", "Net Income", ni_y),
        ("g:performance", "Performance"),
        ("%:roaa", "ROAA", [div(None if v is None else v * f, d) for v, f, d in zip(ni_y, ann, ata)]),
        ("%:roae", "ROAE", [div(None if v is None else v * f, d) for v, f, d in zip(ni_y, ann, aeq)]),
        ("%:eff", "Efficiency Ratio", [div(e, _n(a) + _n(b)) for e, a, b in zip(nie_y, nii_y, nonii_y)]),
    ]
    return {"years": [{"label": y["label"], "partial": y["partial"]} for y in Y], "X": X, "Y": Yr,
            "deposits_classified": dep_ok, "unclassified_deposits": len(unclassified),
            "salaries_available": sal_all is not None}


def _rows(base_rows, stress_rows):
    """Join base and stressed rows by their reporting key, never by position, keeping the union of rows.

    A conditional row (key starting with "?") appears when either case holds a balance; the other case then
    shows its own computed zero. A row present on one side only is unavailable on the other, not zero."""
    bmap = {r[0]: r for r in base_rows}
    smap = {r[0]: r for r in stress_rows}
    order = [r[0] for r in base_rows]
    for i, r in enumerate(stress_rows):           # stress-only rows go after their predecessor in stress order
        if r[0] not in bmap:
            prev = next((stress_rows[j][0] for j in range(i - 1, -1, -1) if stress_rows[j][0] in order), None)
            order.insert(order.index(prev) + 1 if prev else 0, r[0])
    out = []
    for key in order:
        b, s = bmap.get(key), smap.get(key)
        ref = b or s
        if key.startswith("g:"):
            out.append({"kind": "group", "label": ref[1]})
            continue
        cond = key.startswith("?")
        k0 = key[1:] if cond else key
        bv, sv = (b[2] if b else None), (s[2] if s else None)
        if cond and all(abs(_n(x)) <= 1e-9 for x in (bv or []) + (sv or [])):
            continue
        style, k = (k0.split(":", 1) if ":" in k0 else ("", k0))
        pct = style == "%"
        b = ref
        if bv is None or sv is None:
            out.append({"key": k, "label": b[1], "style": style, "available": False, "note": NA})
            continue
        d = [None if (x is None or y is None) else (y - x) for x, y in zip(bv, sv)]
        r = lambda xs: [None if x is None else round(x, 4 if pct else 3) for x in xs]
        out.append({"key": k, "label": b[1], "style": style, "unit": "pct" if pct else "money", "available": True,
                    "base": r(bv), "stress": r(sv), "delta": r(d)})
    return out


def report(base_cfg, base_res, stress_cfg, stress_res, settings_cfg=None) -> dict:
    """Tables X and Y (stress, base, change) and the capital assessment for both cases.

    ``settings_cfg`` supplies the current reporting settings (classifications, policy minimums,
    window); by default the base configuration's own."""
    sc = settings_cfg or base_cfg
    rep_cfg_b = dict(base_only(base_cfg), stress_reporting=settings(sc))
    rep_cfg_s = dict(base_only(stress_cfg), stress_reporting=settings(sc))
    win = report_window(rep_cfg_b)
    sb, ss = statements(rep_cfg_b, base_res, win), statements(rep_cfg_s, stress_res, win)
    snap = settings_snapshot(sc)
    return {"settings_used": snap, "settings_fingerprint": settings_fingerprint(snap),
            "window": {k: win[k] for k in ("periods", "label", "basis")}, "years": sb["years"],
            "X": _rows(sb["X"], ss["X"]), "Y": _rows(sb["Y"], ss["Y"]),
            "deposits_classified": sb["deposits_classified"] and ss["deposits_classified"],
            "unclassified_deposits": sb["unclassified_deposits"],
            "capital": {"base": capital_assessment(rep_cfg_b, base_res, win),
                        "stress": capital_assessment(rep_cfg_s, stress_res, win)},
            "thresholds": {k: v for k, v in thresholds(rep_cfg_b, base_res).items() if not k.startswith("_")},
            "conventions": ["Balances at year end; income and expense summed over the year.",
                            "ROAA and ROAE: annual net income over time-weighted average assets and equity; partial years annualized.",
                            "Deposits split by each product's confirmed interest-bearing setting.",
                            "Cushion: capital less floor x the ratio's own denominator; not a modeled capital raise.",
                            f"Lines marked '{NA}' carry no value; they are not zero."]}


# ------------------------------------------------------------------ workbook
def add_report_sheets(wb, rep, record):
    from openpyxl.styles import Font
    bold = Font(bold=True)
    name = f"{record.get('scenario_name')} · {record.get('severity_label')}"
    for title, key, cap in (("Table X Balance Sheet", "X", "Period end, $ in thousands"),
                            ("Table Y Income Statement", "Y", "Annual flows, $ in thousands")):
        ws = wb.create_sheet(title)
        yl = [y["label"] + (" (partial)" if y["partial"] else "") for y in rep["years"]]
        ws.append([f"{title.split(' ', 2)[0]} {title.split(' ', 2)[1]}: {name}"])
        ws.append([cap + f" · window {rep['window']['label']} · reporting settings {rep.get('settings_fingerprint', '')}"])
        ws.append(["", *(["Stressed"] * len(yl)), *(["Change relative to base"] * len(yl)), *(["Base"] * len(yl))])
        ws.append(["", *yl, *yl, *yl])
        for c in ws[4]:
            c.font = bold
        for r in rep[key]:
            if r.get("kind") == "group":
                ws.append([r["label"]])
                ws.cell(ws.max_row, 1).font = bold
            elif not r["available"]:
                ws.append([r["label"], r["note"]])
            else:
                ws.append([r["label"], *r["stress"], *r["delta"], *r["base"]])
        ws.append([])
        ws.append(["Ratios in percent; ratio changes in percentage points."])
    ws = wb.create_sheet("Capital vs Thresholds")
    ws.append(["Case", "Ratio", "Lowest ratio %", "Period", "Tier", "Floor %", "Source", "Lowest cushion ($000s)",
               "Cushion period", "First breach period"])
    for c in ws[1]:
        c.font = bold
    for case in ("base", "stress"):
        ca = rep["capital"][case]
        for r, x in ca["ratios"].items():
            if not x.get("available"):
                ws.append([case, x["label"], "not available"])
                continue
            for t, v in x["tiers"].items():
                if v is None:
                    continue
                ws.append([case, x["label"], x["min"], x["min_period"], v["label"], v["floor"], v["source"],
                           v["min_cushion"], v["min_cushion_period"], v["first_breach_period"] or "none"])
    return wb

    ws = wb.create_sheet("Reporting settings")
    ws.append(["Reporting settings used for this package"])
    ws.append(["Fingerprint", rep.get("settings_fingerprint", "")])
    snap = rep.get("settings_used") or {}
    ws.append(["Window (periods)", snap.get("window_periods") or "full horizon"])
    for r, v in sorted((snap.get("policy_minimums") or {}).items()):
        ws.append([f"Policy minimum: {r}", (v or {}).get("value"), (v or {}).get("source")])
    for k, v in sorted((snap.get("deposit_classes") or {}).items()):
        ws.append([f"Deposit class: {k}", v])
    for k, v in sorted((snap.get("expense_classes") or {}).items()):
        ws.append([f"Expense class: {k}", v])
