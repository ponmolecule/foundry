"""Foundry Input Workbook (FIW) — the per-engagement Excel (INPUT_SPEC §7).

Unlike the full config workbook (excel_q.py, every field always), the FIW is
generated from one engagement's state: CONTROL from identity and capital, one
ASSM sheet per product family actually present, LIMITS, and a README carrying
the generation hash that makes the diff-import (build step 3) possible.
Progressive disclosure extends into the paper: a deposits-only bank gets no
loan sheet; a product without originate-to-sell shows no mb_ rows.

Sheet grammar (stable for the diff-import): column A holds a machine key
(family.index.field) — hidden; columns B..D are Product | Field | Value with
units in E. Fact rows (Call Report line) are marked read-only in E.
"""
import io
import json
import hashlib

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

GOLD = PatternFill("solid", fgColor="FFF3D9")
HDR = Font(bold=True)

LOAN_FIELDS = [
    ("call_report_line", "Call Report line", "fact — resolved, do not edit"),
    ("opening_balance", "Opening balance (Day 1)", "$"),
    ("originations_q", "New originations", "$/quarter (monthly x3)"),
    ("orig_growth_q", "Origination growth", "rate/qtr"),
    ("runoff_q", "Prepayment / paydown", "rate/qtr (annual /4)"),
    ("yield_ann", "Average yield", "annual rate"),
    ("charge_off_ann", "Net charge-offs", "annual rate"),
    ("provision_rate_ann", "Provision rate (blank = NCO)", "annual rate"),
    ("reserve_rate_pct_bal", "ALLL reserve", "% of balance"),
    ("fee_yield_ann", "Fees", "annual % of avg balance"),
]
MB_FIELDS = [
    ("mortgage_banking.sale_pct_of_orig", "Originations sold", "share [0,1]"),
    ("mortgage_banking.gain_on_sale_margin", "Gain-on-sale margin", "share"),
    ("mortgage_banking.servicing_retained_pct", "Servicing retained", "share of sold"),
    ("mortgage_banking.servicing_fee_bp_ann", "Servicing fee", "bp/yr"),
    ("mortgage_banking.msr_cap_rate_pct_upb", "MSR cap rate", "% of UPB"),
]
DEP_FIELDS = [
    ("call_report_line", "Call Report line", "fact — resolved, do not edit"),
    ("opening_balance", "Opening balance", "$"),
    ("growth_q", "Balance growth", "rate/qtr"),
    ("runoff_q", "Runoff", "rate/qtr"),
    ("rate_paid_ann", "Rate paid", "annual rate"),
    ("fee_yield_ann", "Fees", "annual % of avg balance"),
]
LINE_LABELS = {
    "loanCommercial": "Loans: Commercial & Industrial", "loanConsumer": "Loans: Consumer",
    "loanCreditCard": "Loans: Credit Card", "loanMortgage": "Loans: 1-4 Family Residential",
    "loanOther": "Loans: Other", "loanCRE": "Loans: Commercial Real Estate",
    "depDDA": "Deposits: Transaction (DDA)", "depSavings": "Deposits: Savings & MMDA",
    "depTime": "Deposits: Time",
}


def cfg_hash(cfg):
    return hashlib.sha256(json.dumps(cfg, sort_keys=True, default=str).encode()).hexdigest()[:12]


def _kv_sheet(ws, rows):
    ws.append(["Item", "Value", "Note"])
    for c in ws[1]:
        c.font = HDR
    for label, value, note, editable in rows:
        ws.append([label, value, note])
        if editable:
            ws.cell(ws.max_row, 2).fill = GOLD
    ws.column_dimensions["A"].width = 34
    ws.column_dimensions["B"].width = 26
    ws.column_dimensions["C"].width = 46


def _family_sheet(ws, fam, products, fields):
    ws.append(["key", "Product", "Field", "Value", "Units / note"])
    for c in ws[1]:
        c.font = HDR
    for i, p in enumerate(products):
        for fkey, flabel, funits in fields:
            if fkey.startswith("mortgage_banking.") and not p.get("mortgage_banking"):
                continue
            if "." in fkey:
                a, b = fkey.split(".", 1)
                val = (p.get(a) or {}).get(b)
            else:
                val = p.get(fkey)
            if fkey == "call_report_line":
                val = LINE_LABELS.get(val, val)
            ws.append([f"{fam}.{i}.{fkey}", p.get("name", ""), flabel,
                       val if val is not None else "", funits])
            if "fact" not in funits:
                ws.cell(ws.max_row, 4).fill = GOLD
    ws.column_dimensions["A"].hidden = True
    ws.column_dimensions["B"].width = 24
    ws.column_dimensions["C"].width = 30
    ws.column_dimensions["D"].width = 18
    ws.column_dimensions["E"].width = 34


def build_fiw(cfg):
    a = cfg["assumptions"]
    ch = cfg.get("charter_profile") or {}
    gh = cfg_hash(cfg)
    wb = Workbook()

    rd = wb.active
    rd.title = "README"
    rd.append(["FOUNDRY INPUT WORKBOOK"]); rd["A1"].font = Font(bold=True, size=14)
    rd.append([f"Engagement: {cfg.get('proposed_bank', '')}"])
    rd.append([f"Scenario: {cfg.get('scenario_name', '')}"])
    rd.append(["Generation hash", gh])
    rd.append([])
    rd.append(["How to use this workbook"])
    rd.append(["Gold cells are yours to edit. Plain cells are facts or context — the app"])
    rd.append(["resolves them and the import will not read edits to them."])
    rd.append(["This workbook contains only the sheets your products require. Upload it"])
    rd.append(["back through the same door it came from; the import validates everything"])
    rd.append(["and lists open questions rather than guessing."])
    rd.column_dimensions["A"].width = 74

    ct = wb.create_sheet("CONTROL")
    _kv_sheet(ct, [
        ("Institution", cfg.get("proposed_bank", ""), "", True),
        ("Legal name", cfg.get("client_legal_name", ""), "", True),
        ("Home state / market", cfg.get("hq", ""), "", True),
        ("Charter type", ch.get("charter_type", ""), "national | state_member | state_nonmember | thrift", True),
        ("Primary federal regulator", ch.get("regulator", ""), "fact — resolved from charter type", False),
        ("Target opening", ch.get("target_opening", ""), "", True),
        ("Pre-opening period (months)", ch.get("pre_open_months", ""), "", True),
        ("CBLR election", "yes" if ch.get("cblr_election") else "no", "community bank leverage framework", True),
        ("Initial capital ($)", (cfg.get("target_state") or {}).get("initial_capital", ""), "", True),
        ("Pre-opening organizational costs ($)", a.get("org_costs_pre_open", ""), "", True),
        ("Scenario name", cfg.get("scenario_name", ""), "", True),
    ])

    if a.get("lending_products"):
        _family_sheet(wb.create_sheet("ASSM_LOANS"), "lending", a["lending_products"], LOAN_FIELDS + MB_FIELDS)
    if a.get("deposit_products"):
        _family_sheet(wb.create_sheet("ASSM_DEPOSITS"), "deposit", a["deposit_products"], DEP_FIELDS)

    lm = wb.create_sheet("LIMITS")
    rows = []
    for con in (cfg.get("constraints") or []):
        rows.append((con.get("name", con.get("metric", "constraint")), con.get("value", ""),
                      con.get("source", ""), True))
    rows.append(("Regulatory thresholds", "resolved from REG_PARAMS", "versioned, cited — never typed", False))
    _kv_sheet(lm, rows)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue(), gh
