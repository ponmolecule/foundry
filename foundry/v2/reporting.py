"""Reporting manifest: presentation-only grouping of authoring products into reporting products.

The financial engine never reads ``cfg["reporting_manifest"]``.  This module runs after the engine,
reads its product registry (``res["products"]``) and per-stream economics, and decides only how those
results are *presented* in Business Plan Tables and product summaries.  Accounting statements and the
Call Report keep every product's own classification.

Rules enforced here (and checked by ``reconcile``):

* Whole-product membership.  A reporting product lists products by ``(family, name)``; each product
  brings every one of its results, including all fee-stream results.  A stream cannot be placed
  anywhere other than with its product.
* One destination per underlying result.  Results carry stable IDs
  (``family/product/measure`` or ``family/product/stream:<quantity_series_id>/income|cost``).
  Products not listed by any reporting product are standalone entries.
* Report lines default from the accounting classification.  An override may only rename or regroup a
  result within its own class (a cost cannot be presented as income, interest expense cannot become a
  fee, and so on).  Overrides change presentation only.
* Reconciliation is by measure and by engine period over the full forecast horizon: the sum over
  reporting entries must equal the engine's product totals, and product totals plus named lines outside
  product contributions must equal the engine's bank totals.  There is no residual line.
* Earnings on deposits are never inferred from balances.  A reporting product that holds deposits shows
  that line as unresolved.
"""

import copy
import hashlib
import json

MANIFEST_KEY = "reporting_manifest"
FAMILIES = {"lending": "lending_products", "deposit": "deposit_products", "obs": "obs_exposures"}
FAMILY_LABEL = {"lending": "Lending", "deposit": "Deposit", "obs": "Fee product"}

# accounting classes ------------------------------------------------------------------------------
CLASSES = {
    "loans": {"label": "Loans (asset)", "kind": "stock", "section": "balances", "default": "Loans · ending balance"},
    "deposits": {"label": "Deposit liability", "kind": "stock", "section": "balances",
                 "default": "Deposits · ending balance"},
    "interest_income": {"label": "Interest income", "kind": "flow", "section": "income", "default": "Interest income"},
    "noninterest_income": {"label": "Noninterest income", "kind": "flow", "section": "income", "default": "Fee income"},
    "interest_expense": {"label": "Interest expense", "kind": "flow", "section": "expense", "default": "Cost of funds"},
    "noninterest_expense": {"label": "Noninterest expense", "kind": "flow", "section": "expense",
                            "default": "Attributable costs"},
    "credit_losses": {"label": "Net charge-offs", "kind": "flow", "section": "expense", "default": "Net charge-offs"},
}
# Standard report lines per class.  An override may choose any of its own class's lines or a new name,
# never a line that belongs to another class.
CLASS_LINES = {
    "loans": ["Loans · ending balance"],
    "deposits": ["Deposits · ending balance"],
    "interest_income": ["Interest income"],
    "noninterest_income": ["Fee income", "Gains on sale", "Net servicing"],
    "interest_expense": ["Cost of funds"],
    "noninterest_expense": ["Attributable costs"],
    "credit_losses": ["Net charge-offs"],
}
RESERVED_LINES = {"earnings on deposits", "direct contribution"}

# (measure key, class, default line, result label)
_MEASURES = {
    "lending": [("bal", "loans", "Loans · ending balance", "Ending balance"),
                ("whCarry", "loans", "Loans · ending balance", "Held-for-sale warehouse"),
                ("intInc", "interest_income", "Interest income", "Interest income"),
                ("fees", "noninterest_income", "Fee income", "Fee income"),
                ("gos", "noninterest_income", "Gains on sale", "Gains on sale"),
                ("servNet", "noninterest_income", "Net servicing", "Net servicing income"),
                ("opex", "noninterest_expense", "Attributable costs", "Operating costs · base"),
                ("passCost", "noninterest_expense", "Attributable costs", "Fee-stream direct costs"),
                ("co", "credit_losses", "Net charge-offs", "Net charge-offs")],
    "deposit": [("bal", "deposits", "Deposits · ending balance", "Ending balance"),
                ("intExp", "interest_expense", "Cost of funds", "Interest expense"),
                ("fees", "noninterest_income", "Fee income", "Fee income"),
                ("opex", "noninterest_expense", "Attributable costs", "Operating costs · base"),
                ("passCost", "noninterest_expense", "Attributable costs", "Fee-stream direct costs")],
    "obs": [("fees", "noninterest_income", "Fee income", "Fee income"),
            ("opex", "noninterest_expense", "Attributable costs", "Operating costs · base"),
            ("passCost", "noninterest_expense", "Attributable costs", "Fee-stream direct costs")],
}
_EPS = 1e-9
_NOISE = 0.011   # per-period rounding between exact stream dollars and 2-dp product $000s


def _num(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return 0.0
    return v if v == v else 0.0


def product_key(family, name):
    return f"{family}/{name}"


def result_id(family, name, measure, stream=None, part=None):
    base = f"{family}/{name}"
    return f"{base}/stream:{stream}/{part}" if stream else f"{base}/{measure}"


# manifest -----------------------------------------------------------------------------------------
def manifest(cfg):
    """Normalized copy of the reporting manifest (never None)."""
    raw = (cfg or {}).get(MANIFEST_KEY) or {}
    out = []
    for i, rp in enumerate(raw.get("reporting_products") or []):
        if not isinstance(rp, dict):
            continue
        members = []
        for m in rp.get("members") or []:
            if isinstance(m, dict) and m.get("family") in FAMILIES and str(m.get("name") or "").strip():
                members.append({"family": m["family"], "name": str(m["name"])})
        ov = {str(k): str(v) for k, v in (rp.get("line_overrides") or {}).items()
              if isinstance(v, str) and v.strip()}
        out.append({"id": str(rp.get("id") or f"rp-{i + 1}"), "name": str(rp.get("name") or "").strip(),
                    "members": members, "line_overrides": ov})
    return {"reporting_products": out}


def manifest_signature(cfg):
    blob = json.dumps(manifest(cfg), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def _horizon_label(ppy, n):
    tag = {12: "M", 4: "Q", 1: "Y"}.get(int(ppy), "P")
    return f"{tag}1–{tag}{n}"


# results ------------------------------------------------------------------------------------------
def _stream_split(cfg_p, prod, measure, econ, n):
    """Split a product's fees or passCost into per-stream results (by quantity_series_id).

    Returns (streams, remainder) where streams is [(sid, stream name, series)] and remainder is the
    product-level part (product total less identified streams).  Rounding noise between exact stream
    dollars and the product's 2-dp $000s is absorbed by the largest stream, so the parts always sum to
    the engine's product series exactly."""
    total = [_num(x) for x in (prod.get(measure) or [])][:n]
    total += [0.0] * (n - len(total))
    field = "reported_fee_income" if measure == "fees" else "fee_product_cost"
    streams = []
    for st in (cfg_p or {}).get("fee_streams") or []:
        sid = str((st or {}).get("quantity_series_id") or "").strip()
        rec = econ.get(sid) if sid else None
        if not rec:
            continue
        ser = [_num(x) / 1000.0 for x in (rec.get(field) or [])][:n]
        ser += [0.0] * (n - len(ser))
        if any(abs(v) > _EPS for v in ser):
            streams.append([sid, str(st.get("name") or sid), ser])
    rem = [t - sum(s[2][i] for s in streams) for i, t in enumerate(total)]
    if streams and all(abs(x) <= _NOISE for x in rem):
        big = max(streams, key=lambda s: sum(abs(v) for v in s[2]))
        big[2] = [v + r for v, r in zip(big[2], rem)]
        rem = [0.0] * n
    return [tuple(s) for s in streams], rem


def _results_for(fam, cfg_p, prod, econ, n):
    name = prod.get("name")
    out = []
    for measure, cls, line, label in _MEASURES[fam]:
        if CLASSES[cls]["kind"] == "stock":
            ser = _arr(prod.get(measure), n, True)
            if measure != "bal" and not any(abs(v) > _EPS for v in ser):
                continue
            out.append({"id": result_id(fam, name, measure), "measure": measure, "class": cls, "default_line": line,
                        "label": label, "stream": None, "series": ser})
            continue
        if measure in ("fees", "passCost"):
            streams, rem = _stream_split(cfg_p, prod, measure, econ, n)
            part = "income" if measure == "fees" else "cost"
            for sid, sname, ser in streams:
                out.append({"id": result_id(fam, name, measure, sid, part), "measure": measure, "class": cls,
                            "default_line": line, "label": sname + (" · fee-stream cost" if part == "cost" else ""),
                            "stream": sid, "series": ser})
            if any(abs(v) > _EPS for v in rem):
                lab = label if not streams else (
                    "Fee income · product level and other streams" if measure == "fees" else
                    "Fee-stream direct costs · other streams")
                out.append({"id": result_id(fam, name, measure), "measure": measure, "class": cls,
                            "default_line": line, "label": lab, "stream": None, "series": rem})
            continue
        ser = [_num(x) for x in (prod.get(measure) or [])][:n]
        if any(abs(v) > _EPS for v in ser):
            out.append({"id": result_id(fam, name, measure), "measure": measure, "class": cls, "default_line": line,
                        "label": label, "stream": None, "series": ser + [0.0] * (n - len(ser))})
    return out


def _cfg_product(cfg, fam, name):
    for p in ((cfg or {}).get("assumptions") or {}).get(FAMILIES[fam]) or []:
        if p.get("name") == name:
            return p
    return {}


def override_problem(cls, label):
    """Why ``label`` may not be used for a result of class ``cls`` (None when allowed)."""
    lab = str(label or "").strip()
    if not lab:
        return "A report line needs a name."
    if len(lab) > 60:
        return "Keep report-line names to 60 characters."
    low = lab.lower()
    if low in RESERVED_LINES:
        return f"“{lab}” is a computed line and cannot hold a result."
    for other, lines in CLASS_LINES.items():
        if other != cls and low in (x.lower() for x in lines + [CLASSES[other]["default"]]):
            return (f"Not allowed: “{lab}” belongs to {CLASSES[other]['label'].lower()}; this result is "
                    f"{CLASSES[cls]['label'].lower()}.")
    return None


# view ---------------------------------------------------------------------------------------------
def build_view(cfg, res):
    """Presentation view of the engine result under the engagement's reporting manifest."""
    a = (cfg or {}).get("assumptions") or {}
    ppy = int(a.get("periods_per_year") or 4)
    n = int(a.get("n_periods") or 12)
    man = manifest(cfg)
    econ = ((res or {}).get("fee_stream_economics") or {}).get("series") or {}
    prods = [p for p in ((res or {}).get("products") or []) if p.get("family") in FAMILIES]
    problems = []

    # products and their results
    plist = []
    for p in prods:
        fam = p["family"]
        cp = _cfg_product(cfg, fam, p.get("name"))
        plist.append({"key": product_key(fam, p.get("name")), "family": fam, "name": p.get("name"),
                      "results": _results_for(fam, cp, p, econ, n)})
    by_key = {p["key"]: p for p in plist}

    # assignment: product -> reporting products that list it
    assign = {p["key"]: [] for p in plist}
    names_seen = {}
    for rp in man["reporting_products"]:
        if not rp["name"]:
            problems.append({"code": "unnamed", "rp": rp["id"], "message": "A reporting product has no name."})
        low = rp["name"].lower()
        if low and low in names_seen:
            problems.append({"code": "duplicate_name", "rp": rp["id"],
                             "message": f"Two reporting products are named “{rp['name']}”."})
        names_seen[low] = rp["id"]
        if not rp["members"]:
            problems.append({"code": "empty", "rp": rp["id"],
                             "message": f"“{rp['name']}” has no member products."})
        seen = set()
        for m in rp["members"]:
            k = product_key(m["family"], m["name"])
            if k in seen:
                continue
            seen.add(k)
            if k not in assign:
                problems.append({"code": "stale_member", "rp": rp["id"], "product": k,
                                 "message": f"“{rp['name']}” lists “{m['name']}”, which is not in this engagement's "
                                            "results."})
                continue
            assign[k].append(rp["id"])
    for k, rps in assign.items():
        if len(rps) > 1:
            problems.append({"code": "overlap", "product": k, "rps": rps,
                             "message": f"“{by_key[k]['name']}” is listed by more than one reporting product, so its "
                                        "results would be reported twice."})

    # entries
    entries = []
    rp_by_id = {rp["id"]: rp for rp in man["reporting_products"]}
    for rp in man["reporting_products"]:
        members = [k for k, rps in assign.items() if rp["id"] in rps]
        members.sort(key=lambda k: [x["key"] for x in plist].index(k))
        entries.append({"id": rp["id"], "kind": "reporting", "name": rp["name"], "members": members})
    for p in plist:
        if not assign[p["key"]]:
            entries.append({"id": "standalone:" + p["key"], "kind": "standalone", "name": p["name"],
                            "members": [p["key"]]})

    # results with destinations and lines
    results = []
    for p in plist:
        dests = assign[p["key"]] or ["standalone:" + p["key"]]
        for r in p["results"]:
            line, src = r["default_line"], "default"
            for d in dests:
                ov = (rp_by_id.get(d) or {}).get("line_overrides", {}).get(r["id"])
                if ov is not None:
                    why = override_problem(r["class"], ov) if CLASSES[r["class"]]["kind"] == "flow" else \
                        "Balance lines cannot be renamed."
                    if why:
                        problems.append({"code": "invalid_override", "rp": d, "result": r["id"], "message": why})
                    else:
                        line, src = ov.strip(), "override"
            results.append({**r, "product": p["key"], "product_name": p["name"], "family": p["family"],
                            "destinations": dests, "line": line, "line_source": src})
    known = {r["id"] for r in results}
    for rp in man["reporting_products"]:
        for rid in rp["line_overrides"]:
            if rid not in known:
                problems.append({"code": "orphan_override", "rp": rp["id"], "result": rid,
                                 "message": "A report-line override refers to a result that no longer exists; it has "
                                            "no effect."})

    for e in entries:
        e["schedule"] = _schedule(e, results, n)

    view = {"version": 1, "manifest_signature": manifest_signature(cfg), "manifest": man, "ppy": ppy, "n_periods": n,
            "window": {"label": _horizon_label(ppy, n), "periods": n, "basis": "forecast horizon"},
            "products": [{"key": p["key"], "family": p["family"], "name": p["name"],
                          "entries": assign[p["key"]] or ["standalone:" + p["key"]]} for p in plist],
            "entries": entries, "results": results, "classes": CLASSES, "class_lines": CLASS_LINES}
    view["reconciliation"] = reconcile(view, res, problems)
    view["problems"] = problems
    view["ok"] = view["reconciliation"]["ok"]
    return view


def _add(a, b):
    m = max(len(a), len(b))
    return [(a[i] if i < len(a) else 0.0) + (b[i] if i < len(b) else 0.0) for i in range(m)]


def _schedule(entry, results, n):
    """Ordered presentation lines for one entry.  Lines with more than one result are subtotals whose
    detail rows are display-only ("within subtotal") and never added again."""
    mine = [r for r in results if entry["id"] in r["destinations"]]
    has_dep = any(r["family"] == "deposit" for r in mine)
    groups = {}
    order = []
    for r in mine:
        key = (r["class"], r["line"])
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(r)
    multi = len(entry["members"]) > 1

    def _line(cls, label, rs):
        stock = CLASSES[cls]["kind"] == "stock"
        ser = []
        for r in rs:
            ser = _add(ser, r["series"])
        detail = []
        if len(rs) > 1:
            for r in rs:
                lab = (r["product_name"] + " · " + r["label"]) if multi else r["label"]
                if stock:
                    lab = r["product_name"]
                detail.append({"label": lab, "series": r["series"], "result": r["id"]})
        return {"label": label, "class": cls, "section": CLASSES[cls]["section"], "stock": stock,
                "series": ser, "results": [r["id"] for r in rs], "detail": detail}

    sec_order = {"balances": 0, "income": 1, "expense": 2}
    cls_order = list(CLASSES)
    std = {c: (CLASS_LINES[c] + [CLASSES[c]["default"]]) for c in CLASSES}

    def _rank(k):
        cls, lab = k
        pos = std[cls].index(lab) if lab in std[cls] else 50 + order.index(k)
        return (sec_order[CLASSES[cls]["section"]], cls_order.index(cls), pos)

    lines = [_line(cls, lab, groups[(cls, lab)]) for cls, lab in sorted(order, key=_rank)]
    out = {"lines": lines, "unresolved": []}
    if has_dep:
        out["unresolved"].append({"label": "Earnings on deposits", "section": "income",
                                  "reason": "No earnings attribution is set for this entry. Foundry does not infer "
                                            "earnings from deposit balances, so investment earnings stay outside "
                                            "product contributions."})
    contrib = [0.0] * n
    for ln in lines:
        if ln["stock"]:
            continue
        sgn = 1.0 if ln["section"] == "income" else -1.0
        contrib = [c + sgn * (ln["series"][i] if i < len(ln["series"]) else 0.0) for i, c in enumerate(contrib)]
    out["direct_contribution"] = contrib
    return out


# reconciliation ------------------------------------------------------------------------------------
_RECON = [
    ("loans", "Loans · ending balance", "stock"),
    ("deposits", "Deposits · ending balance", "stock"),
    ("interest_income", "Interest income", "flow"),
    ("interest_expense", "Interest expense", "flow"),
    ("noninterest_income", "Fee, sale and servicing income", "flow"),
    ("noninterest_expense", "Operating costs", "flow"),
    ("credit_losses", "Net charge-offs", "flow"),
]
_PRODUCT_FIELDS = {
    "loans": ("lending", ["bal", "whCarry"]), "deposits": ("deposit", ["bal"]),
    "interest_income": (None, ["intInc"]), "interest_expense": (None, ["intExp"]),
    "noninterest_income": (None, ["fees", "gos", "servNet"]), "noninterest_expense": (None, ["opex", "passCost"]),
    "credit_losses": (None, ["co"]),
}


def _arr(x, n, stock):
    a = [_num(v) for v in (x or [])]
    if stock and len(a) == n:          # engine stocks normally carry an opening slot
        a = [0.0] + a
    want = n + 1 if stock else n
    return (a + [0.0] * want)[:want]


def reconcile(view, res, problems=None):
    problems = problems if problems is not None else []
    n = view["n_periods"]
    fin = (res or {}).get("financials") or {}
    IS, BS = fin.get("is") or {}, fin.get("bs") or {}
    der = ((res or {}).get("presentation") or {}).get("derived") or {}
    prods = [p for p in ((res or {}).get("products") or []) if p.get("family") in FAMILIES]
    nprod = max(1, len(prods))
    out = []
    ok = True
    for cls, label, kind in _RECON:
        stock = kind == "stock"
        fam, fields = _PRODUCT_FIELDS[cls]
        # reported: every result counted once per destination (an overlap shows as a difference)
        reported = [0.0] * (n + 1 if stock else n)
        for r in view["results"]:
            if r["class"] != cls:
                continue
            ser = _arr(r["series"], n, stock)
            for _ in r["destinations"]:
                reported = [x + y for x, y in zip(reported, ser)]
        engine_products = [0.0] * len(reported)
        for p in prods:
            if fam and p.get("family") != fam:
                continue
            if stock and p.get("family") not in ("lending", "deposit"):
                continue
            for f in fields:
                engine_products = [x + y for x, y in zip(engine_products, _arr(p.get(f), n, stock))]
        outside, bank, bank_label = [], None, None
        if cls == "loans":
            if BS.get("grossLoans") is not None:
                bank = _arr(BS.get("grossLoans"), n, True)
                bank_label = "Balance sheet · gross loans, including held for sale"
        elif cls == "deposits":
            if BS.get("deposits") is not None:
                bank, bank_label = _arr(BS.get("deposits"), n, True), "Balance sheet · total deposits"
        elif cls == "interest_income":
            outside = [("Securities interest", IS.get("secInt")), ("Cash and due-from interest", IS.get("cashInt"))]
            src = der.get("totalIntInc")
            if src is not None:
                bank, bank_label = _arr(src, n, False), "Income statement · total interest income"
        elif cls == "interest_expense":
            outside = [("Borrowing interest", IS.get("borrExp"))]
            src = der.get("totalIntExp")
            if src is not None:
                bank, bank_label = _arr(src, n, False), "Income statement · total interest expense"
        elif cls == "noninterest_income":
            if any(IS.get(k) is not None for k in ("fees", "gos", "servNet")):
                bank = [0.0] * n
                for k in ("fees", "gos", "servNet"):
                    bank = [x + y for x, y in zip(bank, _arr(IS.get(k), n, False))]
                bank_label = "Income statement · fees, gains on sale and net servicing"
        elif cls == "noninterest_expense":
            outside = [("Corporate overhead (workforce, other operating expense, depreciation)", IS.get("overhead"))]
            src = der.get("nie")
            if src is not None:
                bank, bank_label = _arr(src, n, False), "Income statement · total noninterest expense"
        elif cls == "credit_losses":
            if IS.get("nco") is not None:
                bank, bank_label = _arr(IS.get("nco"), n, False), "Income statement · memo net charge-offs"
        outside = [(lab, _arr(s, n, stock)) for lab, s in outside if s is not None]
        tol_rep = 1e-6
        tol_bank = 0.005 * (nprod + len(outside) + 2) + 1e-6
        d_rep = [a - b for a, b in zip(reported, engine_products)]
        total = list(engine_products)
        for _, s in outside:
            total = [x + y for x, y in zip(total, s)]
        d_bank = [a - b for a, b in zip(total, bank)] if bank is not None else None
        rng = range(1, n + 1) if stock else range(n)
        m_ok = all(abs(d_rep[i]) <= tol_rep for i in rng) and (
            d_bank is None or all(abs(d_bank[i]) <= tol_bank for i in rng))
        ok = ok and m_ok
        out.append({"class": cls, "label": label, "kind": kind, "reported": reported,
                    "engine_products": engine_products, "outside": [{"label": l, "series": s} for l, s in outside],
                    "bank_total": total, "engine_bank": bank, "engine_bank_label": bank_label,
                    "diff_reported": d_rep, "diff_bank": d_bank, "ok": m_ok,
                    "tolerance": {"reported": tol_rep, "bank": tol_bank}})
    blocking = [p for p in problems if p["code"] in ("stale_member", "overlap", "invalid_override", "duplicate_name",
                                                     "unnamed", "empty")]
    n_rep = sum(1 for r in view["results"] if any(not d.startswith("standalone:") for d in r["destinations"]))
    cov = {"results": len(view["results"]), "in_reporting": n_rep,
           "standalone": len(view["results"]) - n_rep,
           "outside_lines": sum(len(m["outside"]) for m in out),
           "omitted": [], "reported_twice": [r["id"] for r in view["results"] if len(r["destinations"]) > 1]}
    return {"ok": ok and not blocking and not cov["reported_twice"], "window": view["window"], "measures": out,
            "coverage": cov}


def attach(cfg, res):
    """Add the presentation view to an engine result (no engine value is read back or changed)."""
    try:
        res["reporting"] = build_view(cfg, res)
    except Exception as e:  # presentation must never break a run
        res["reporting"] = {"version": 1, "error": f"{type(e).__name__}: {e}"[:300], "ok": False}
    return res


def exhibit_entries(cfg, res):
    """Entries for exhibits: reporting products first, then standalone products, in registry order."""
    v = res.get("reporting") if isinstance(res.get("reporting"), dict) and "entries" in res.get("reporting") else None
    if v is None or v.get("manifest_signature") != manifest_signature(cfg):
        v = build_view(cfg, res)
    return v


def copy_manifest(cfg):
    return copy.deepcopy(manifest(cfg))
