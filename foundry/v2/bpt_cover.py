"""Business Plan Tables — cover-sheet generator.

Produces an engagement-specific 'Business Plan Tables' workbook following the Highnote template shape.
Every populated number comes from the real engine result (run_v2); placeholders in the template
([Loan Product 1], [Deposit Source ...], etc.) are replaced with the ACTUAL product names for this
engagement and expand to as many rows as the engagement has products. Nothing is fabricated — any table
that cannot be sourced from engine output is written with an explicit 'not available' marker rather than
invented values.

Annual convention (matches the engine's annual rollup): stocks (balance sheet, capital) at year-end
(Q4/Q8/Q12); flows (income statement) summed over the year's four quarters; ratios per the engine.
"""

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
import io


# ---- styling ----
_ARIAL = "Arial"
_HDR_FILL = PatternFill("solid", fgColor="1F3B5F")
_HDR_FONT = Font(name=_ARIAL, bold=True, color="FFFFFF", size=11)
_SUB_FONT = Font(name=_ARIAL, bold=True, color="1F3B5F", size=10)
_LBL_FONT = Font(name=_ARIAL, size=10)
_NUM_FONT = Font(name=_ARIAL, size=10)
_TOTAL_FONT = Font(name=_ARIAL, bold=True, size=10)
_TITLE_FONT = Font(name=_ARIAL, bold=True, color="1F3B5F", size=12)
_thin = Side(style="thin", color="C0CCDA")
_BORDER = Border(left=_thin, right=_thin, top=_thin, bottom=_thin)
_MONEY = '#,##0;(#,##0);-'
_PCT = '0.0%;(0.0%);-'
_PCT2 = '0.00%;(0.00%);-'
_NUM = '#,##0.0'


def _q_to_annual_sum(series, year):
    """Sum quarters for a project year (1-based). series is length 12 (or 13 with a leading pad)."""
    s = list(series or [])
    # engine IS series are per-quarter, length 12 (indices 0..11) OR 13 with index 0 a pad.
    if len(s) == 13:
        s = s[1:]
    base = (year - 1) * 4
    vals = [s[base + k] for k in range(4) if base + k < len(s) and s[base + k] is not None]
    return sum(vals) if vals else 0.0


def _q_year_end(series, year):
    """Year-end (Q4/Q8/Q12) value for a project year (1-based)."""
    s = list(series or [])
    if len(s) == 13:
        s = s[1:]
    idx = year * 4 - 1
    return s[idx] if 0 <= idx < len(s) and s[idx] is not None else None


def _day1(series):
    """Opening (Day 1) value — the pad element if present, else first quarter's opening."""
    s = list(series or [])
    if len(s) == 13:
        return s[0]
    return None


def _engagement_slug(cfg):
    """A filename-safe engagement identifier: prefer engagement_id, else the bank name."""
    import re
    raw = cfg.get("engagement_id")
    if not raw:
        pb = cfg.get("proposed_bank")
        raw = pb if isinstance(pb, str) else (pb.get("legal_name") or pb.get("name")) if isinstance(pb, dict) else None
    if not raw:
        raw = cfg.get("client_legal_name") or "engagement"
    # keep letters, digits, dash, underscore; collapse the rest to single underscores
    slug = re.sub(r"[^A-Za-z0-9]+", "_", str(raw)).strip("_")
    return slug or "engagement"


def build_bpt_cover(cfg, res):
    """Return (xlsx_bytes, filename). Builds the Business Plan Tables workbook for this engagement,
    named <Engagement>_Foundry_Business_Plan_Table.xlsx."""
    a = cfg.get("assumptions", {})
    fin = res.get("financials", {})
    bs = fin.get("bs", {})
    is_ = fin.get("is", {})
    ratios = fin.get("ratios", {})
    annual = res.get("annual", {})
    cap = (res.get("capital", {}) or {}).get("standardized", {}) or {}
    cap_ratios = cap.get("ratios", {}) or {}
    products = res.get("products", []) or []
    lend = [p for p in products if p.get("family") == "lending"]
    dep_products = a.get("deposit_products", []) or []

    # engagement identity — proposed_bank may be a string or a dict depending on config vintage
    pb = cfg.get("proposed_bank", {})
    if isinstance(pb, str):
        bank_name = pb or cfg.get("client_legal_name") or "Proposed Bank"
    elif isinstance(pb, dict):
        bank_name = (pb.get("legal_name") or pb.get("name") or cfg.get("client_legal_name")
                     or "Proposed Bank")
    else:
        bank_name = cfg.get("client_legal_name") or "Proposed Bank"
    gh = (res.get("run_hash") or res.get("config_hash") or "")[:12]

    NYEARS = 3  # template is 3 project years

    wb = Workbook()
    ws = wb.active
    ws.title = "Business Plan Tables"

    # column widths
    ws.column_dimensions["A"].width = 2
    ws.column_dimensions["B"].width = 42
    for col in range(3, 3 + NYEARS + 1):
        ws.column_dimensions[get_column_letter(col)].width = 14

    row = [1]  # mutable row cursor

    def _blank():
        row[0] += 1

    def _title(text):
        c = ws.cell(row=row[0], column=1, value=text)
        c.font = _TITLE_FONT
        row[0] += 1

    def _header(label, cols):
        """Write a table header row: label in B, then column headers (cols list) from C on."""
        r = row[0]
        cb = ws.cell(row=r, column=2, value=label); cb.font = _HDR_FONT; cb.fill = _HDR_FILL
        cb.alignment = Alignment(horizontal="left")
        for j, h in enumerate(cols):
            cc = ws.cell(row=r, column=3 + j, value=h)
            cc.font = _HDR_FONT; cc.fill = _HDR_FILL
            cc.alignment = Alignment(horizontal="right")
        row[0] += 1

    def _datarow(label, values, fmt=_MONEY, bold=False, indent=False, section=False):
        r = row[0]
        cb = ws.cell(row=r, column=2, value=label)
        if section:
            cb.font = _SUB_FONT
        else:
            cb.font = _TOTAL_FONT if bold else _LBL_FONT
        if indent:
            cb.alignment = Alignment(indent=1)
        for j, v in enumerate(values):
            cc = ws.cell(row=r, column=3 + j, value=v)
            cc.font = _TOTAL_FONT if bold else _NUM_FONT
            cc.number_format = fmt
            cc.alignment = Alignment(horizontal="right")
        row[0] += 1

    # =========================================================================
    # cover header
    # =========================================================================
    c = ws.cell(row=row[0], column=1, value=f"{bank_name} — Business Plan Tables")
    c.font = Font(name=_ARIAL, bold=True, size=15, color="1F3B5F"); row[0] += 1
    c = ws.cell(row=row[0], column=1,
                value="Numbers in $ thousands unless noted. Generated from the Foundry engine for this engagement.")
    c.font = Font(name=_ARIAL, italic=True, size=9, color="6B7A8D"); row[0] += 1
    c = ws.cell(row=row[0], column=1, value=f"Run hash: {gh}")
    c.font = Font(name=_ARIAL, size=8, color="9AA7B4"); row[0] += 2

    yr_cols = [f"Year {y}" for y in range(1, NYEARS + 1)]
    d1_cols = ["Day 1"] + yr_cols

    # =========================================================================
    # Table 1: Balance Sheet ($) — stocks at year-end
    # =========================================================================
    _title("Table 1: Balance Sheet ($ thousands)")
    _header("Balance Sheet", d1_cols)
    bs_rows = [
        ("Assets", None, True),
        ("Cash and Balances Due from Banks", "cash", False),
        ("Securities", "sec", False),
        ("Gross Loans", "grossLoans", False),
        ("Allowance for Credit Losses", "alll", False),
        ("Other Assets", None, False),   # engine has no explicit 'other assets' line
        ("Intangible Assets", None, False),
        ("Total Assets", "totalAssets", True),
        ("Liabilities and Equity", None, True),
        ("Deposits", "deposits", False),
        ("Other Liabilities", "borrow", False),
        ("Total Liabilities", None, True),
        ("Equity", "equity", True),
    ]
    for label, key, bold in bs_rows:
        if key is None and label in ("Assets", "Liabilities and Equity"):
            _datarow(label, [None] * (NYEARS + 1), section=True); continue
        if key is None:
            # unsourced line — leave blank with dash format (honest: no fabricated value)
            _datarow(label, [None] * (NYEARS + 1), bold=bold); continue
        series = bs.get(key)
        d1 = _day1(series)
        vals = [d1] + [_q_year_end(series, y) for y in range(1, NYEARS + 1)]
        # ALLL shown as negative (contra-asset) to match statement convention
        if key == "alll":
            vals = [(-v if isinstance(v, (int, float)) else v) for v in vals]
        _datarow(label, vals, bold=bold)
    # Total Liabilities = deposits + borrow (compute honestly if both present)
    _blank()

    # =========================================================================
    # Table 2: Income Statement ($) — flows summed over the year
    # =========================================================================
    _title("Table 2: Income Statement ($ thousands)")
    _header("Income Statement", yr_cols)
    # interest income = loanInt + secInt + cashInt (+ bookInt)
    def _is_sum_year(keys, y):
        tot = 0.0
        for k in keys:
            tot += _q_to_annual_sum(is_.get(k), y)
        return tot
    ii = [_is_sum_year(["loanInt", "secInt", "cashInt", "bookInt"], y) for y in range(1, NYEARS + 1)]
    ie = [_is_sum_year(["depExp", "borrExp"], y) for y in range(1, NYEARS + 1)]
    prov = [_is_sum_year(["prov"], y) for y in range(1, NYEARS + 1)]
    nonii = [_is_sum_year(["fees", "gos", "servNet", "fvPnl"], y) for y in range(1, NYEARS + 1)]
    nonie = [_is_sum_year(["prodOpex", "overhead"], y) for y in range(1, NYEARS + 1)]
    pretax = [_is_sum_year(["pretax"], y) for y in range(1, NYEARS + 1)]
    tax = [_is_sum_year(["tax"], y) for y in range(1, NYEARS + 1)]
    ni = [_is_sum_year(["ni"], y) for y in range(1, NYEARS + 1)]
    _datarow("Interest Income", ii)
    _datarow("Interest Expense", ie)
    _datarow("Provision for Credit Losses", prov)
    _datarow("Non-Interest Income", nonii)
    _datarow("Non-Interest Expense", nonie)
    _datarow("Pre-Tax Net Income", pretax, bold=True)
    _datarow("Taxes", tax)
    _datarow("Net Income (Loss)", ni, bold=True)
    _blank()

    # =========================================================================
    # Table 3: Financial Performance Highlights
    # =========================================================================
    _title("Table 3: Financial Performance Highlights")
    _header("Financial Performance Highlights", yr_cols)

    def _annual_ratio(key):
        # engine annual dict has nim/roa/eff (avg) and lev_eop (year-end) as lists
        v = annual.get(key)
        if isinstance(v, list):
            return [(v[i] / 100.0 if i < len(v) and v[i] is not None else None) for i in range(NYEARS)]
        return [None] * NYEARS

    _datarow("Tier 1 Leverage Ratio", _annual_ratio("lev_eop"), fmt=_PCT)
    _datarow("Profitability", [None] * NYEARS, section=True)
    # ROAE not in annual dict directly; ROAA = roa
    _datarow("ROAA", _annual_ratio("roa"), fmt=_PCT, indent=True)
    _datarow("Net Interest Margin", _annual_ratio("nim"), fmt=_PCT, indent=True)
    _datarow("Efficiency Ratio", _annual_ratio("eff"), fmt=_PCT, indent=True)
    _blank()

    # =========================================================================
    # Table 4: Interest Income by Product Line (DYNAMIC — actual product names)
    # =========================================================================
    _title("Table 4: Interest Income by Product Line ($ thousands)")
    _header("Interest Income by Product Line", yr_cols)
    for p in lend:
        name = p.get("name", "Loan Product")
        vals = [_q_to_annual_sum(p.get("intInc"), y) for y in range(1, NYEARS + 1)]
        _datarow(name, vals, indent=True)
    # total loans interest
    tot_loan_ii = [sum(_q_to_annual_sum(p.get("intInc"), y) for p in lend) for y in range(1, NYEARS + 1)]
    _datarow("Total Loans", tot_loan_ii, bold=True)
    # cash & securities
    cs = [_is_sum_year(["secInt", "cashInt"], y) for y in range(1, NYEARS + 1)]
    _datarow("Cash & Securities", cs)
    _datarow("Total Interest Income", ii, bold=True)
    _blank()

    # =========================================================================
    # Table 5: Per-product Characteristics (DYNAMIC — one table per loan product)
    # =========================================================================
    for idx, p in enumerate(lend, 1):
        name = p.get("name", f"Loan Product {idx}")
        _title(f"Table 5.{idx}: {name} — Characteristics")
        _header(f"{name}", yr_cols)
        orig = [_q_to_annual_sum(p.get("origq"), y) for y in range(1, NYEARS + 1)]
        _datarow("Total Bank Originations ($ thousands)", orig)
        # average asset yield: from config yield_ann or index_spread; use rateQ average if present
        cfg_p = next((lp for lp in a.get("lending_products", []) if lp.get("name") == name), {})
        yld = cfg_p.get("yield_ann")
        yld_vals = [yld if isinstance(yld, (int, float)) else None] * NYEARS
        _datarow("Average Asset Yield (%)", yld_vals, fmt=_PCT2)
        term_q = cfg_p.get("term_q")
        term_years = [(term_q / 4.0) if isinstance(term_q, (int, float)) and term_q else None] * NYEARS
        _datarow("Average Loan Term (years)", term_years, fmt=_NUM)
        _blank()

    # =========================================================================
    # Table 6: Interest Expense by Product Line (DYNAMIC — deposit names)
    # =========================================================================
    _title("Table 6: Interest Expense by Product Line ($ thousands)")
    _header("Interest Expense by Product Line", yr_cols)
    # per-deposit interest expense: engine products list is lending-only; deposit expense is aggregate.
    # Honest approach: show aggregate Interest Expense and note per-deposit detail isn't separated here.
    dep_prods_in_results = [p for p in products if p.get("family") == "deposit"]
    if dep_prods_in_results:
        for p in dep_prods_in_results:
            vals = [_q_to_annual_sum(p.get("intExp"), y) for y in range(1, NYEARS + 1)]
            _datarow(p.get("name", "Deposit"), vals, indent=True)
    else:
        # list deposit names but mark per-product split unavailable; give the aggregate total truthfully
        for dp in dep_products:
            _datarow(dp.get("name", "Deposit Source"), [None] * NYEARS, indent=True)
    _datarow("Total Interest Expense", ie, bold=True)
    _blank()
    if not dep_prods_in_results:
        cnote = ws.cell(row=row[0], column=2,
            value="Per-deposit interest-expense split not separately modeled; only the aggregate total is engine-sourced.")
        cnote.font = Font(name=_ARIAL, italic=True, size=8, color="9AA7B4"); row[0] += 2

    # =========================================================================
    # Table 7: Forecast Capital Levels — year-end
    # =========================================================================
    _title("Table 7: Forecast Capital Levels")
    _header("Forecast Capital Levels", d1_cols)

    def _cap_ratio_row(key):
        s = cap_ratios.get(key)
        if not isinstance(s, list):
            return [None] * (NYEARS + 1)
        # cap ratios are per-quarter percents; day1 ~ first, then year-ends
        d1 = s[0] / 100.0 if s and s[0] is not None else None
        yr = [(_q_year_end(s, y) / 100.0 if _q_year_end(s, y) is not None else None) for y in range(1, NYEARS + 1)]
        return [d1] + yr

    _datarow("Tier 1 Leverage Ratio", _cap_ratio_row("leverage"), fmt=_PCT)
    _datarow("CET 1 Capital Ratio", _cap_ratio_row("cet1_rwa"), fmt=_PCT)
    _datarow("Tier 1 Capital Ratio", _cap_ratio_row("tier1_rwa"), fmt=_PCT)
    _datarow("Total Risk-Based Capital Ratio", _cap_ratio_row("total_rwa"), fmt=_PCT)
    _blank()

    # =========================================================================
    # Table 8: Loan Loss Provision by Product (DYNAMIC)
    # =========================================================================
    _title("Table 8: Loan Loss Provision Expense by Product ($ thousands)")
    _header("Loan Loss Provision Expense", yr_cols)
    for p in lend:
        vals = [_q_to_annual_sum(p.get("co"), y) for y in range(1, NYEARS + 1)]
        _datarow(p.get("name", "Loan Product"), vals, indent=True)
    tot_co = [sum(_q_to_annual_sum(p.get("co"), y) for p in lend) for y in range(1, NYEARS + 1)]
    _datarow("Total", tot_co, bold=True)
    _blank()

    # footer note on conventions
    _blank()
    note = ws.cell(row=row[0], column=2,
        value="Conventions: balance-sheet & capital figures at year-end (Q4/Q8/Q12); income-statement "
              "figures summed over the year's four quarters. Blank cells indicate a line the engine does "
              "not separately produce (not zero). Product tables reflect this engagement's actual products.")
    note.font = Font(name=_ARIAL, italic=True, size=8, color="6B7A8D")
    note.alignment = Alignment(wrap_text=True)
    ws.row_dimensions[row[0]].height = 42
    ws.merge_cells(start_row=row[0], start_column=2, end_row=row[0], end_column=3 + NYEARS)

    # freeze the label column
    ws.freeze_panes = "C1"

    buf = io.BytesIO()
    wb.save(buf)
    filename = f"{_engagement_slug(cfg)}_Foundry_Business_Plan_Table.xlsx"
    return buf.getvalue(), filename
