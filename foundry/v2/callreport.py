"""Foundry v2 — Call Report presentation mapping (B.7).

Maps engine result lines and product call_report_line values to Call Report
schedule/item references for exhibits and the console. Presentation only —
never consumed by arithmetic. Codes follow FFIEC 051/041 conventions for the
commonly cited items; schedule+item is authoritative where an RCON/RIAD code
varies by form.
"""

# balance-sheet result keys -> (schedule, item, code, label)
RESULT_CODES_BS = {
    "cash":        ("RC", "1",    "RCON0081/0071", "Cash and balances due"),
    "sec":         ("RC", "2.b",  "RCON1773",      "Available-for-sale securities (fair value)"),
    "afs":         ("RC", "2.b",  "RCON1773",      "Available-for-sale securities (fair value)"),
    "htm":         ("RC", "2.a",  "RCONJJ34",      "Held-to-maturity securities (amortized cost)"),
    "hfs":         ("RC", "4.a",  "RCON5369",      "Loans held for sale"),
    "grossLoans":  ("RC", "4.b",  "RCONB528",      "Loans and leases held for investment"),
    "alll":        ("RC", "4.c",  "RCON3123",      "Allowance for credit losses on loans"),
    "netLoans":    ("RC", "4.d",  "RCONB529",      "Loans and leases, net"),
    "msr":         ("RC-M", "2.a", "RCON6438",     "Mortgage servicing assets"),
    "totalAssets": ("RC", "12",   "RCON2170",      "Total assets"),
    "deposits":    ("RC", "13.a", "RCON2200",      "Deposits in domestic offices"),
    "borrow":      ("RC", "16",   "RCON3190",      "Other borrowed money"),
    "borrowings":  ("RC", "16",   "RCON3190",      "Other borrowed money"),
    "equity":      ("RC", "27.a", "RCON3210",      "Total bank equity capital"),
    "re":          ("RC", "26.a", "RCON3632",      "Retained earnings"),
    "retained":    ("RC", "26.a", "RCON3632",      "Retained earnings"),
    "aoci":        ("RC", "26.b", "RCONB530",      "Accumulated other comprehensive income"),
    "paidIn":      ("RC", "23/24","RCON3230/3839", "Common stock and surplus (paid-in capital)"),
    "afsBook":     ("RC", "2.b",  "RCON1773",      "Available-for-sale securities (designated book)"),
    "htmBook":     ("RC", "2.a",  "RCONJJ34",      "Held-to-maturity securities (amortized cost)"),
    "premises":    ("RC", "6",    "RCON2145",      "Premises and fixed assets (net of depreciation)"),
    "borrowSched": ("RC", "16",   "RCON3190",      "Other borrowed money (scheduled FHLB/term draws)"),
    "retained":    ("RC", "26.a", "RCON3632",      "Retained earnings"),
}

# income-statement result keys -> (schedule, item, code, label)
RESULT_CODES_IS = {
    "loanInt":   ("RI", "1.a",   "RIAD4010", "Interest and fees on loans"),
    "intLoans":  ("RI", "1.a",   "RIAD4010", "Interest and fees on loans"),
    "secInt":    ("RI", "1.d",   "RIADB488/B489", "Interest on securities"),
    "intSec":    ("RI", "1.d",   "RIADB488/B489", "Interest on securities"),
    "bookInt":   ("RI", "1.d",   "RIADB488/B489", "Interest on securities (designated books)"),
    "cashInt":   ("RI", "1.c",   "RIAD4115", "Interest on balances due from depository institutions"),
    "intCash":   ("RI", "1.c",   "RIAD4115", "Interest on balances due from depository institutions"),
    "depExp":    ("RI", "2.a",   "RIAD4508/0093", "Interest on deposits"),
    "intDep":    ("RI", "2.a",   "RIAD4508/0093", "Interest on deposits"),
    "borrExp":   ("RI", "2.c",   "RIAD4185", "Interest on borrowed money"),
    "intBorrow": ("RI", "2.c",   "RIAD4185", "Interest on borrowed money"),
    "nii":       ("RI", "3",     "RIAD4074", "Net interest income"),
    "prov":      ("RI", "4",     "RIADJJ33", "Provision for credit losses"),
    "provision": ("RI", "4",     "RIADJJ33", "Provision for credit losses"),
    "fees":      ("RI", "5",     "RIAD4079", "Noninterest income"),
    "gos":       ("RI", "5.i",   "RIAD5416", "Net gains on sales of loans"),
    "servNet":   ("RI", "5.f",   "RIADB492", "Net servicing fees"),
    "fvPnl":     ("RI", "5.l",   "RIADHT69", "FV option net gains (losses)"),
    "prodOpex":  ("RI", "7",     "RIAD4093", "Noninterest expense (product)"),
    "overhead":  ("RI", "7",     "RIAD4093", "Noninterest expense (overhead)"),
    "opexProd":  ("RI", "7",     "RIAD4093", "Noninterest expense (product)"),
    "fixedOpex": ("RI", "7",     "RIAD4093", "Noninterest expense (overhead)"),
    "pretax":    ("RI", "8.c",   "RIAD4301", "Income before income taxes"),
    "tax":       ("RI", "9",     "RIAD4302", "Applicable income taxes"),
    "ni":        ("RI", "12",    "RIAD4340", "Net income"),
    "nco":       ("RI-B", "9",   "RIAD4635", "Net charge-offs"),
    "chargeoffs":("RI-B", "9",   "RIAD4635", "Net charge-offs"),
    "nol":       ("—", "memo",   "—",        "NOL carryforward (memo)"),
}

# product call_report_line vocabulary -> RC-C / RC-E item references
LINE_CODES = {
    "loanMortgage": ("RC-C", "1.c", "RCON5367/5368", "1-4 family residential"),
    "Loans: 1–4 Family Residential": ("RC-C", "1.c", "RCON5367/5368", "1-4 family residential"),
    "Loans: 1-4 Family Residential": ("RC-C", "1.c", "RCON5367/5368", "1-4 family residential"),
    "loanCommercial": ("RC-C", "4",  "RCON1766", "Commercial and industrial"),
    "Loans: Commercial & Industrial": ("RC-C", "4", "RCON1766", "Commercial and industrial"),
    "Loans: Commercial Real Estate": ("RC-C", "1.e", "RCONF160/F161", "CRE (nonfarm nonresidential)"),
    "loanCRE": ("RC-C", "1.e", "RCONF160/F161", "CRE (nonfarm nonresidential)"),
    "loanConsumer": ("RC-C", "6.c/6.d", "RCONK137/K207", "Other consumer"),
    "Loans: Consumer": ("RC-C", "6.c/6.d", "RCONK137/K207", "Other consumer"),
    "loanCreditCard": ("RC-C", "6.a", "RCONB538", "Credit cards"),
    "Loans: Credit Cards": ("RC-C", "6.a", "RCONB538", "Credit cards"),
    "Loans: Lease Financing": ("RC-C", "10", "RCON2165", "Lease financing receivables"),
    "depDDA": ("RC-E", "1", "RCONB549", "Transaction accounts"),
    "depBrokered": ("RC-E", "M.1.b", "RCON2365", "Brokered deposits (memo)"),
    "depSweep": ("RC-E", "M.1.h", "RCONMT87", "Sweep deposits (memo)"),
    "depInstitutional": ("RC-E", "M.1.f", "RCONK220", "Listing-service / institutional (memo)"),
    "Deposits: Demand (DDA)": ("RC-E", "1", "RCONB549", "Transaction accounts"),
    "Deposits: Transaction (DDA)": ("RC-E", "1", "RCONB549", "Transaction accounts"),
    "depSavings": ("RC-E", "2/3", "RCONB550", "Savings and MMDA"),
    "Deposits: Savings & MMDA": ("RC-E", "2/3", "RCONB550", "Savings and MMDA"),
    "Deposits: Money Market (MMDA)": ("RC-E", "2/3", "RCONB550", "Savings and MMDA"),
    "depTime": ("RC-E", "4/5", "RCON6648/J473", "Time deposits"),
    "Deposits: Time": ("RC-E", "4/5", "RCON6648/J473", "Time deposits"),
    "Deposits: Brokered": ("RC-E", "M.1.b", "RCON2365", "Brokered deposits (memo)"),
}


def code_for_result(key):
    return RESULT_CODES_BS.get(key) or RESULT_CODES_IS.get(key)


def code_for_line(line):
    return LINE_CODES.get(line)


# ---------------------------------------------------------------- builders
# Pro forma schedule assembly (presentation only; every subtotal recomputed
# from engine series and tie-checked by Gate T31). Lines the model does not
# compute are OMITTED and listed in the footer — omission is honest; a zero
# asserts a fact the model never computed (TEST_CASES.md #12).

def _q(series):
    """Normalize to Q1..Q12: balance series carry a Q0 opening (13 points);
    flow series carry 12. Schedules are uniformly quarterly columns."""
    return list(series[1:13]) if len(series) == 13 else list(series[:12])


def _row(item, code, label, vals):
    return {"item": item, "code": code, "label": label, "values": _q(vals)}


def build_rc(res, cfg):
    bs, a = res["financials"]["bs"], cfg["assumptions"]
    n = len(bs["totalAssets"])
    prem = (bs.get("premises") if bs.get("premises")
             else [a.get("premises_equipment", 0) / 1000.0] * n)
    intang = [a.get("intangibles", 0) / 1000.0] * n
    oa = [a.get("other_assets", 0) / 1000.0] * n
    ol = [a.get("other_liabilities", 0) / 1000.0] * n
    rows = [
        _row("1", "RCON0081/0071", "Cash and balances due from depository institutions", bs["cash"]),
        _row("2.a", "RCONJJ34", "Held-to-maturity securities (amortized cost)",
              bs.get("htmBook", [0.0] * len(bs["totalAssets"]))),
        _row("2.b", "RCON1773", "Available-for-sale debt securities (fair value)",
              [bs["sec"][t] + bs.get("afsBook", [0.0] * len(bs["sec"]))[t]
               for t in range(len(bs["sec"]))]),
        _row("4.b", "RCONB528", "Loans and leases held for investment", bs["grossLoans"]),
        _row("4.c", "RCON3123", "LESS: allowance for credit losses", [-x for x in bs["alll"]]),
        _row("4.d", "RCONB529", "Loans and leases, net", bs["netLoans"]),
        _row("6", "RCON2145", "Premises and fixed assets", prem),
        _row("10", "RCON2143", "Intangible assets", intang),
        _row("11", "RCON2160", "Other assets", oa),
        _row("12", "RCON2170", "TOTAL ASSETS", bs["totalAssets"]),
        _row("13.a", "RCON2200", "Deposits in domestic offices", bs["deposits"]),
        _row("16", "RCON3190", "Other borrowed money (incl. scheduled term draws)",
              [(bs["borrow"][t] if t < len(bs["borrow"]) else 0.0)
               + (bs.get("borrowSched", [0.0] * 99)[t] if t < len(bs.get("borrowSched", [])) else 0.0)
               for t in range(len(bs["borrow"]))]),
        _row("20", "RCON2930", "Other liabilities", ol),
        _row("23/24", "RCON3230/3839", "Common stock and surplus (paid-in)",
              bs.get("paidIn", [0.0] * len(bs["re"]))),
        _row("26.a", "RCON3632", "Retained earnings", bs["re"]),
        _row("26.b", "RCONB530", "Accumulated other comprehensive income",
              bs.get("aoci", [0.0] * len(bs["re"]))),
        _row("27.a", "RCON3210", "Total bank equity capital", bs["equity"]),
    ]
    if any(x > 0 for x in bs["msr"]):
        rows.insert(8, _row("RC-M 2.a", "RCON6438", "Mortgage servicing assets (memoranda)", bs["msr"]))
    if any(x > 0 for x in bs["hfs"]):
        rows.append(_row("MEMO", "RCON5369", "Loans held for sale (memoranda — engine carries the "
                          "warehouse outside total assets; carry earns in RI)", bs["hfs"]))
    return {"schedule": "RC", "title": "Balance Sheet", "rows": rows,
            "omitted": ["trading assets (RC 5)",
                          "bank premises detail, foreclosed assets, subordinated debt"],
            "notes": ["Held-for-sale balances shown as memoranda: the engine's total-assets "
                        "composition excludes the warehouse (disclosed convention, tie-checked)."]}


def build_ri(res):
    s = res["financials"]["is"]
    n = len(s["ni"])
    tii = [s["loanInt"][t] + s["secInt"][t] + s["cashInt"][t] + s["bookInt"][t] for t in range(n)]
    tie = [s["depExp"][t] + s["borrExp"][t] for t in range(n)]
    nonint_inc = [s["fees"][t] + s["gos"][t] + s["servNet"][t] + s["fvPnl"][t] for t in range(n)]
    nonint_exp = [s["overhead"][t] + s["prodOpex"][t] for t in range(n)]
    rows = [
        _row("1.a", "RIAD4010", "Interest and fees on loans", s["loanInt"]),
        _row("1.c", "RIAD4115", "Interest on balances due from depository institutions", s["cashInt"]),
        _row("1.d", "RIADB488/B489", "Interest on securities", [s["secInt"][t] + s["bookInt"][t] for t in range(n)]),
        _row("1.h", "RIAD4107", "Total interest income", tii),
        _row("2.a", "RIAD4508/0093", "Interest on deposits", s["depExp"]),
        _row("2.b", "RIAD4185", "Interest on borrowed money", s["borrExp"]),
        _row("2.e", "RIAD4073", "Total interest expense", tie),
        _row("3", "RIAD4074", "Net interest income", s["nii"]),
        _row("4", "RIADJJ33", "Provision for credit losses", s["prov"]),
        _row("5", "RIAD4079", "Noninterest income (fees, gains on sale, net servicing, FV marks)", nonint_inc),
        _row("7", "RIAD4093", "Noninterest expense (overhead and product operating costs)", nonint_exp),
        _row("8", "RIAD4301", "Income before income taxes", s["pretax"]),
        _row("9", "RIAD4302", "Applicable income taxes", s["tax"]),
        _row("12", "RIAD4340", "NET INCOME", s["ni"]),
    ]
    return {"schedule": "RI", "title": "Income Statement", "rows": rows,
            "omitted": ["trading revenue, realized securities gains (RI 6) — none modeled",
                          "extraordinary items, discontinued operations"]}


def build_rce(res, cfg=None):
    lines = {"depDDA": ("Transaction accounts (demand)", []),
             "depBrokered": ("Brokered deposits (memo M.1.b)", []),
             "depSweep": ("Sweep deposits (memo M.1.h)", []),
             "depInstitutional": ("Institutional & listing-service (memo M.1.f)", []),
              "depSavings": ("Nontransaction: savings and MMDA", []),
              "depTime": ("Nontransaction: time deposits", [])}
    n = 0
    for p in res["products"]:
        if p["family"] != "deposit":
            continue
        n = max(n, len(p["bal"]) - 1)
        key = p.get("line") or "depDDA"
        if key in lines:
            lines[key][1].append(p)
    rows = []
    for key, (label, prods) in lines.items():
        if not prods:
            continue
        vals = [sum(p["bal"][t + 1] for p in prods) for t in range(n)]
        rows.append(_row({"depDDA": "1", "depSavings": "M.2.a", "depTime": "M.2.c",
                      "depBrokered": "M.1.b", "depSweep": "M.1.h",
                      "depInstitutional": "M.1.f"}[key],
                          {"depDDA": "RCONB549", "depSavings": "RCON6810/0352", "depTime": "RCON6648/J473",
                      "depBrokered": "RCON2365", "depSweep": "RCONMT87",
                      "depInstitutional": "RCONK220"}[key],
                          label + f" ({len(prods)} product{'s' if len(prods) > 1 else ''})", vals))
    total = [sum(r["values"][t] for r in rows) for t in range(n)] if rows else []
    rows.append(_row("—", "RCON2200", "Total deposits (ties to RC 13.a)", total))
    notes_rce = ["institutional lines (brokered/sweep/listing) are shown at their memo item "
                   "codes but modeled as their own funding balances — they count once in the "
                   "total, which ties to RC 13.a"]
    return {"schedule": "RC-E", "title": "Deposit Liabilities", "rows": rows,
            "notes": notes_rce,
            "insurance": (_rce_insurance(res, cfg) if cfg is not None else
                             {"provided": False, "note": "config unavailable in this call path"})}


def _rce_insurance(res, cfg):
    """F-032 (D-P7 fix): insured/uninsured ESTIMATE from per-product insured_pct.
    Products without the assumption are STATED, never silently bucketed."""
    dps = (cfg["assumptions"].get("deposit_products") or [])
    n = len(_q(res["financials"]["bs"]["totalAssets"]))
    have, missing = [], []
    for p in res.get("products") or []:
        if not str(p.get("line") or "").startswith("dep"):
            continue
        src = next((d for d in dps if d.get("name") == p.get("name")), {})
        ip = src.get("insured_pct")
        balv = p.get("bal") or []
        balq = balv[1:13] if len(balv) == 13 else balv[:12]
        if ip is None:
            missing.append(p.get("name"))
        else:
            have.append((float(ip), balq))
    if not have:
        return {"provided": False,
                 "note": "insured_pct not provided on any deposit product — the estimate "
                          "is omitted, not zero-filled (D-P7: bucketing is an assumption, "
                          "and an absent assumption is stated)"}
    insured = [sum(ip * (b[t] if t < len(b) else 0.0) for ip, b in have) for t in range(n)]
    covered = [sum((b[t] if t < len(b) else 0.0) for _, b in have) for t in range(n)]
    return {"provided": True,
             "insured_est": [round(x, 2) for x in insured],
             "uninsured_est": [round(covered[t] - insured[t], 2) for t in range(n)],
             "coverage_note": ("estimate covers products carrying insured_pct"
                                + (f"; NOT PROVIDED for: {', '.join(missing)}" if missing else
                                    " (all deposit products)")),
             "codes": "memo M.1 (uninsured est, RCON5597) / M.2 (insured)"}


def build_rcc(res, cfg):
    """RC-C Part I — Loans and Leases, by Call Report line, from product balances.
    Held-for-investment per line; HFS shown as its own row; ties to RC 4.a."""
    bs = res["financials"]["bs"]
    n_ref = len(_q(bs["totalAssets"]))
    per_line = {}
    for p in res.get("products") or []:
        ln = p.get("line")
        if not ln or not str(ln).startswith("loan"):
            continue
        balv = p.get("bal") or []
        balq = balv[1:13] if len(balv) == 13 else balv[:12]
        acc = per_line.setdefault(ln, [0.0] * n_ref)
        for t in range(min(n_ref, len(balq))):
            acc[t] += balq[t] or 0.0
    order = [("loanCommercial", "4",   "RCON1766", "Commercial and industrial loans"),
              ("loanCRE",        "1.e", "RCONF160", "CRE: nonfarm nonresidential"),
              ("loanMortgage",   "1.c", "RCON1797", "1-4 family residential first liens"),
              ("loanConsumer",   "6.c", "RCONK137", "Other consumer loans"),
              ("loanCreditCard", "6.a", "RCONB538", "Credit cards"),
              ("loanOther",      "9",   "RCON1563", "Other loans")]
    rows = []
    for ln, item, code, label in order:
        if ln in per_line and any(abs(v) > 1e-9 for v in per_line[ln]):
            rows.append({"item": item, "code": code, "label": label,
                          "values": [round(v, 2) for v in per_line[ln]]})
    hfs = _q(bs.get("hfs") or [0.0] * 13)
    if any(abs(v) > 1e-9 for v in hfs):
        rows.append({"item": "memo", "code": "RCON5369", "label": "Loans held for sale (memo)",
                      "values": [round(v, 2) for v in hfs]})
    gross = _q(bs["grossLoans"])
    total = [round(sum(r["values"][t] for r in rows), 2) for t in range(n_ref)]
    rows.append({"item": "12", "code": "RCON2122",
                  "label": "Total loans and leases (ties to RC 4.a)", "values": total})
    return {"schedule": "RC-C Part I", "title": "Loans and Leases", "rows": rows,
            "notes": ["per-line balances aggregate every product mapped to the line "
                        "(zero lines suppressed, per the artifact's convention)",
                       "total ties to Schedule RC gross loans within rounding"],
            "tie_ok": all(abs(total[t] - gross[t]) < 1.0 for t in range(n_ref))}


def build_rcr(res, cfg):
    bs, ratios = res["financials"]["bs"], res["financials"]["ratios"]
    a = cfg["assumptions"]
    n = len(bs["equity"])
    intang = [a.get("intangibles", 0) / 1000.0] * n
    t1 = [bs["equity"][t] - intang[t] for t in range(n)]
    ch = cfg.get("charter_profile") or {}
    req = None
    for con in (cfg.get("constraints") or []):
        if "lever" in str(con.get("name", con.get("metric", ""))).lower():
            req = con.get("value")
    rows = [
        _row("26", "RCOA8274", "Tier 1 capital (leverage basis: equity less intangibles)", t1),
        _row("—", "RCON2170", "Total assets (quarter-end)", bs["totalAssets"]),
        _row("31", "RCOA7204", "Leverage ratio (%)", ratios["lev"]),
    ]
    st = (res.get("capital") or {}).get("standardized")
    out = {"schedule": "RC-R Part I", "title": "Regulatory Capital", "rows": rows,
            "cblr": bool(ch.get("cblr_election")),
            "requirement_pct": (req * 100.0 if isinstance(req, (int, float)) and req < 1 else req),
            "omitted": ["capital conservation buffer detail"],
            "notes": ["Leverage per the engine's average-assets, MSA-deducted derivation "
                        "(12 CFR 3.22(d)); Tier 1 row here shows the leverage basis.",
                        "Part II below computes the standardized approach whether or not CBLR "
                        "is elected — the election decides which framework GOVERNS, not which "
                        "is visible."]}
    if st:
        pad = [None]
        out["part2"] = {
            "title": "RC-R Part II — Standardized approach (12 CFR 324.32/.33)",
            "rows": [
                _row("A", "RCOAP793", "Common equity tier 1 capital", pad + st["cet1"]),
                _row("B", "RCOA8274", "Tier 1 capital", pad + st["tier1"]),
                _row("C", "RCOA5310", "Tier 2 capital (ALLL, capped 1.25% RWA)", pad + st["tier2"]),
                _row("D", "RCOA3792", "Total capital", pad + st["total"]),
                _row("E", "RCOAA223", "Total risk-weighted assets", pad + st["rwa"]),
                _row("F", "RCOAP840", "CET1 ratio (%)", pad + st["ratios"]["cet1_rwa"]),
                _row("G", "RCOA7206", "Tier 1 ratio (%)", pad + st["ratios"]["tier1_rwa"]),
                _row("H", "RCOA7205", "Total capital ratio (%)", pad + st["ratios"]["total_rwa"]),
            ],
            "notes": st["notes"]}
    return out


def build_call_report(res, cfg):
    return {"RC": build_rc(res, cfg), "RI": build_ri(res),
            "RC-E": build_rce(res, cfg), "RC-C": build_rcc(res, cfg),
            "RC-R": build_rcr(res, cfg)}
