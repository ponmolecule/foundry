"""Foundry v2 — presentation layer (PC-3).

The engine speaks in keys; clients read statements. This module is the single
source of professional labels and statement STRUCTURE — sections, per-product
detail rows, subtotals, totals, and the balance-identity attestation — consumed
by both the Modeling Workspace and the Excel exhibit, so the screen and the
filing read identically. Presentation only: arithmetic never consumes it.

Row types:
  section  — uppercase group header
  line     — a result key rendered with its full label (+ optional indent)
  detail   — per-product rows drawn from the products summary, filtered by family
  total    — a result key styled as a total
  identity — the assets-vs-liabilities+equity check row
  spacer
"""

BS_LAYOUT = [
    {"t": "section", "label": "ASSETS"},
    {"t": "line", "key": "cash", "label": "Cash and balances due from banks"},
    {"t": "line", "key": "htm", "label": "Securities held-to-maturity, at amortized cost"},
    {"t": "line", "key": "afs", "label": "Securities available-for-sale, at fair value"},
    {"t": "line", "key": "sec", "label": "Securities available-for-sale, at fair value (incl. liquidity portfolio)"},
    {"t": "line", "key": "hfs", "label": "Loans held for sale, at carrying value"},
    {"t": "detail", "family": "lending", "label": "Loans and leases held for investment:"},
    {"t": "line", "key": "grossLoans", "label": "Gross loans and leases (incl. held for sale)", "indent": 1},
    {"t": "line", "key": "alll", "label": "Less: allowance for credit losses on loans", "indent": 1, "negate": True},
    {"t": "line", "key": "netLoans", "label": "Loans and leases, net of allowance", "subtotal": True},
    {"t": "line", "key": "msr", "label": "Mortgage servicing rights, net"},
    {"t": "line", "key": "nonEarn", "label": "Premises, equipment, and other assets"},
    {"t": "total", "key": "totalAssets", "label": "TOTAL ASSETS"},
    {"t": "spacer"},
    {"t": "section", "label": "LIABILITIES"},
    {"t": "detail", "family": "deposit", "label": "Deposits:"},
    {"t": "line", "key": "deposits", "label": "Total deposits", "subtotal": True},
    {"t": "line", "key": "borrow", "label": "Borrowed funds"},
    {"t": "line", "key": "borrowings", "label": "Borrowed funds"},
    {"t": "line", "key": "otherLiab", "label": "Accrued expenses and other liabilities"},
    {"t": "line", "key": "totalLiab", "label": "Total liabilities", "subtotal": True},
    {"t": "spacer"},
    {"t": "section", "label": "EQUITY"},
    {"t": "line", "key": "paidIn", "label": "Common stock and paid-in capital"},
    {"t": "line", "key": "re", "label": "Retained earnings (accumulated deficit)"},
    {"t": "line", "key": "retained", "label": "Retained earnings (accumulated deficit)"},
    {"t": "line", "key": "equity", "label": "Total equity capital", "subtotal": True},
    {"t": "total", "key": "totalLiabEq", "label": "TOTAL LIABILITIES AND EQUITY"},
    {"t": "identity", "label": "Balance identity: assets = liabilities + equity"},
]

IS_LAYOUT = [
    {"t": "section", "label": "INTEREST INCOME"},
    {"t": "line", "key": "loanInt", "label": "Interest and fees on loans (incl. warehouse)", "indent": 1},
    {"t": "line", "key": "intLoans", "label": "Interest and fees on loans", "indent": 1},
    {"t": "line", "key": "secInt", "label": "Interest on securities", "indent": 1},
    {"t": "line", "key": "intSec", "label": "Interest on securities", "indent": 1},
    {"t": "line", "key": "cashInt", "label": "Interest on balances due from banks", "indent": 1},
    {"t": "line", "key": "intCash", "label": "Interest on balances due from banks", "indent": 1},
    {"t": "line", "key": "totalIntInc", "label": "Total interest income", "subtotal": True},
    {"t": "section", "label": "INTEREST EXPENSE"},
    {"t": "line", "key": "depExp", "label": "Interest on deposits", "indent": 1},
    {"t": "line", "key": "intDep", "label": "Interest on deposits", "indent": 1},
    {"t": "line", "key": "borrExp", "label": "Interest on borrowed funds", "indent": 1},
    {"t": "line", "key": "intBorrow", "label": "Interest on borrowed funds", "indent": 1},
    {"t": "line", "key": "totalIntExp", "label": "Total interest expense", "subtotal": True},
    {"t": "line", "key": "nii", "label": "NET INTEREST INCOME", "subtotal": True},
    {"t": "line", "key": "prov", "label": "Provision for credit losses", "negate_style": True},
    {"t": "line", "key": "provision", "label": "Provision for credit losses", "negate_style": True},
    {"t": "spacer"},
    {"t": "section", "label": "NONINTEREST INCOME"},
    {"t": "line", "key": "fees", "label": "Service charges and fee income", "indent": 1},
    {"t": "line", "key": "gos", "label": "Net gains on sales of loans (incl. capitalized MSRs)", "indent": 1},
    {"t": "line", "key": "servNet", "label": "Net servicing fees", "indent": 1},
    {"t": "line", "key": "fvPnl", "label": "Net gains (losses) on fair-value-option instruments", "indent": 1},
    {"t": "section", "label": "NONINTEREST EXPENSE"},
    {"t": "line", "key": "prodOpex", "label": "Product operating expense", "indent": 1},
    {"t": "line", "key": "opexProd", "label": "Product operating expense", "indent": 1},
    {"t": "line", "key": "overhead", "label": "Salaries, occupancy, and other overhead", "indent": 1},
    {"t": "line", "key": "fixedOpex", "label": "Salaries, occupancy, and other overhead", "indent": 1},
    {"t": "spacer"},
    {"t": "line", "key": "pretax", "label": "INCOME (LOSS) BEFORE INCOME TAXES", "subtotal": True},
    {"t": "line", "key": "tax", "label": "Applicable income taxes", "negate_style": True},
    {"t": "total", "key": "ni", "label": "NET INCOME (LOSS)"},
    {"t": "spacer"},
    {"t": "section", "label": "MEMORANDA"},
    {"t": "line", "key": "nco", "label": "Net charge-offs", "indent": 1},
    {"t": "line", "key": "chargeoffs", "label": "Net charge-offs", "indent": 1},
    {"t": "line", "key": "bookInt", "label": "of which: interest on designated securities books", "indent": 1},
    {"t": "line", "key": "nol", "label": "Net operating loss carryforward, end of period", "indent": 1},
]

RATIO_LABELS = {
    "roa": "Return on average assets (annualized)",
    "roe": "Return on average equity (annualized)",
    "nim": "Net interest margin (annualized, avg earning assets)",
    "lev": "Tier 1 leverage ratio (avg assets, MSR threshold deduction)",
    "leverage": "Equity / total assets (leverage)",
    "alllPct": "Allowance for credit losses / gross loans",
}

SCENARIO_LABELS = {
    "base": "Base case",
    "rate_shock_300": "+300bp rate shock",
    "credit_stress": "Credit stress (2.5x charge-offs, 1.5x reserves)",
    "combined_downturn": "Combined downturn (credit + rates + volume/GOS/MSR overlays)",
}


def derived_lines(res, cfg):
    """Compute presentation-only derived rows ($000s): totals, other assets/liabs,
    paid-in capital, interest totals, and the balance-identity check. Pure
    arithmetic on engine output; nothing feeds back into the engine."""
    bs, is_ = res["bs"], res["is"]
    n = len(bs["totalAssets"])
    a = cfg["assumptions"]
    non_earn = round((a["premises_equipment"] + a["intangibles"] + a["other_assets"]) / 1000.0, 2)
    other_liab = round(a["other_liabilities"] / 1000.0, 2)
    paid_in = round(cfg["target_state"]["initial_capital"] / 1000.0, 2)
    bor = bs.get("borrow") or bs.get("borrowings") or [0.0] * n
    dep = bs["deposits"]
    eq = bs["equity"]
    out = {
        "nonEarn": [non_earn] * n,
        "otherLiab": [other_liab] * n,
        "paidIn": [paid_in] * n,
        "totalLiab": [round((dep[i] or 0) + (bor[i] or 0) + other_liab, 2) for i in range(n)],
    }
    out["totalLiabEq"] = [round(out["totalLiab"][i] + (eq[i] or 0), 2) for i in range(n)]
    out["identity"] = [round((bs["totalAssets"][i] or 0) - out["totalLiabEq"][i], 2) for i in range(n)]
    m = len(is_.get("ni", []))
    def g(k):
        return is_.get(k) or [0.0] * m
    out["totalIntInc"] = [round((g("loanInt")[i] if "loanInt" in is_ else g("intLoans")[i] or 0)
                                + (g("secInt")[i] if "secInt" in is_ else g("intSec")[i] or 0)
                                + (g("cashInt")[i] if "cashInt" in is_ else g("intCash")[i] or 0), 2)
                         for i in range(m)]
    out["totalIntExp"] = [round((g("depExp")[i] if "depExp" in is_ else g("intDep")[i] or 0)
                                + (g("borrExp")[i] if "borrExp" in is_ else g("intBorrow")[i] or 0), 2)
                          for i in range(m)]
    return out
