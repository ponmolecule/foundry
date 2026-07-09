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
    "loanConsumer": ("RC-C", "6.c/6.d", "RCONK137/K207", "Other consumer"),
    "Loans: Consumer": ("RC-C", "6.c/6.d", "RCONK137/K207", "Other consumer"),
    "loanCreditCard": ("RC-C", "6.a", "RCONB538", "Credit cards"),
    "Loans: Credit Cards": ("RC-C", "6.a", "RCONB538", "Credit cards"),
    "Loans: Lease Financing": ("RC-C", "10", "RCON2165", "Lease financing receivables"),
    "depDDA": ("RC-E", "1", "RCONB549", "Transaction accounts"),
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
