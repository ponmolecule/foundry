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
    ("new_deposits_q", "New deposits", "$/quarter (monthly x3)"),
    ("avg_maturity_m", "Average maturity", "months; 0 = no term roll-off"),
    ("runoff_q", "Runoff / prepayment", "rate/qtr (annual / 4)"),
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
        if isinstance(value, (int, float)) and abs(value) >= 1000:
            ws.cell(ws.max_row, 2).number_format = "#,##0"
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
            if isinstance(val, (int, float)) and abs(val) >= 1000:
                ws.cell(ws.max_row, 4).number_format = "#,##0"
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
        ("Scenario name", cfg.get("scenario_name", ""), "", True),
    ] + [(f"Staged raise {i+1} — quarter", r.get("quarter", ""), "1..12", True)
          for i, r in enumerate(a.get("capital_raises") or [])]
      + [(f"Staged raise {i+1} — amount ($)", r.get("amount", ""), "", True)
          for i, r in enumerate(a.get("capital_raises") or [])])

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
    _settings_sheet(wb, cfg)   # human-readable review of every in-app-configured input
    _embed_state(wb, cfg)      # the workbook carries its own generation state
    wb.save(buf)
    return buf.getvalue(), gh


# ---------------------------------------------------------------- snapshots
import os


def _snap_dir():
    base = os.environ.get("FOUNDRY_DATA_DIR", os.path.join(os.getcwd(), "data"))
    d = os.path.join(base, "fiw")
    os.makedirs(d, exist_ok=True)
    return d


STATE_SHEET = "STATE"
_CHUNK = 30000

def _settings_sheet(wb, cfg):
    """SETTINGS: read-only statement of everything configured in-app — the
    inputs that have no editable cells elsewhere in this workbook. A reviewer
    sees every entered value; the import deliberately ignores this sheet."""
    a = cfg.get("assumptions") or {}
    ws = wb.create_sheet("SETTINGS")
    ws.append(["SETTINGS — configured in-app (read-only)"])
    ws["A1"].font = Font(bold=True, size=12)
    ws.append(["Edits on this sheet are NOT imported. These inputs are configured in the app; "
               "they are stated here so the workbook is a complete record of the engagement."])
    ws.append([])
    def sec(title): ws.append([title]); ws[f"A{ws.max_row}"].font = Font(bold=True)
    def row(label, val, unit=""):
        ws.append([f"  {label}", "" if val is None else val, unit])
        if isinstance(val, (int, float)) and abs(val) >= 1000:
            ws.cell(row=ws.max_row, column=2).number_format = "#,##0"
    sec("Treasury (funding waterfall)")
    row("Cash floor (% of deposits)", a.get("cash_target_pct_deposits"), "rate")
    row("Yield on cash", a.get("cash_yield"), "annual rate")
    row("Yield on securities", a.get("securities_yield"), "annual rate")
    row("Borrowing rate", a.get("borrow_rate_ann"), "annual rate")
    sec("Overhead & other balance sheet")
    row("Corporate overhead", a.get("overhead_q"), "$/quarter")
    row("Overhead growth", a.get("overhead_growth_q"), "rate/qtr")
    row("Premises & equipment", a.get("premises_equipment"), "$")
    row("Premises depreciation", a.get("premises_depreciation_annual"), "$/year")
    row("Intangibles", a.get("intangibles"), "$")
    row("Other assets", a.get("other_assets"), "$")
    row("Other liabilities", a.get("other_liabilities"), "$")
    sec("Scheduled borrowings")
    for i, b in enumerate(a.get("scheduled_borrowings") or [], 1):
        row(b.get("name") or f"Borrowing {i}",
            f"draws Q{b.get('quarter', b.get('start_q'))} \u00b7 {float(b.get('amount') or 0):,.0f} \u00b7 "
            f"{b.get('term_q')}q amortizing at {b.get('rate_ann')}", "")
    if not (a.get("scheduled_borrowings") or []): row("(none)", "")
    sec("Pre-opening expenses")
    _po_ex = (cfg.get("pre_opening") or {}).get("expenses") or []
    for e in _po_ex:
        row(e.get("category") or e.get("label") or "expense",
            e.get("total") if e.get("total") is not None else e.get("amount"), "$")
    if _po_ex:
        row("Total pre-opening burn", sum(float(e.get("total", e.get("amount", 0)) or 0) for e in _po_ex), "$ (reduces Day-1 capital)")
    else:
        row("(none)", "")
    sec("Securities books")
    for p in (a.get("securities_afs") or []): row(f"AFS — {p.get('name')}", p.get("opening"), f"yield {p.get('yield_ann')}")
    for p in (a.get("securities_htm") or []): row(f"HTM — {p.get('name')}", p.get("opening"), f"yield {p.get('yield_ann')}")
    if not ((a.get("securities_afs") or []) + (a.get("securities_htm") or [])): row("(none)", "")
    row("AOCI sensitivity", a.get("aoci_sensitivity_annual"), "% of AFS/yr")
    sec("NIE detail")
    nd = a.get("nie_detail") or {}
    if nd:
        if nd.get("fte_by_year") is not None:
            row("FTE by year (Y1/Y2/Y3)", " / ".join(str(x) for x in nd.get("fte_by_year") or []), "headcount")
        if nd.get("loaded_comp_annual") is not None:
            row("Loaded comp per FTE", nd.get("loaded_comp_annual"), "$/year")
        for cat in (nd.get("categories") or []):
            row(cat.get("name") or "category",
                cat.get("per_quarter") if cat.get("per_quarter") is not None else cat.get("amount_q"), "$/quarter")
        if nd.get("other_gross_up_rate") is not None:
            row("Other gross-up rate", nd.get("other_gross_up_rate"), "rate")
    else:
        row("(not active)", "")
    sec("Fee modules")
    fm = a.get("fee_modules") or {}
    for k, v in fm.items():
        if v: row(k, str(v)[:120], "")
    if not any(fm.values()) if fm else True: row("(none active)", "")
    sec("SOFR rate path (Q1..Q12)")
    row("Path", ", ".join(str(x) for x in (a.get("rate_path_q") or [])), "annual")
    row("Longer run", a.get("rate_path_longer_run"), "annual")
    sec("Stress parameters")
    for k, v in (cfg.get("stress_params") or {}).items(): row(k, v, "")
    ws.column_dimensions["A"].width = 44
    ws.column_dimensions["B"].width = 40


def _embed_state(wb, cfg):
    ws = wb.create_sheet(STATE_SHEET)
    ws.sheet_state = "veryHidden"
    blob = json.dumps(cfg, sort_keys=True)
    for i in range(0, len(blob), _CHUNK):
        ws.cell(row=i // _CHUNK + 1, column=1, value=blob[i:i + _CHUNK])

def _read_embedded_state(wb):
    if STATE_SHEET not in wb.sheetnames:
        return None
    parts = []
    for r in wb[STATE_SHEET].iter_rows(min_col=1, max_col=1):
        if r[0].value is None:
            break
        parts.append(str(r[0].value))
    try:
        return json.loads("".join(parts))
    except Exception:
        return None

def persist_snapshot(cfg, gh):
    with open(os.path.join(_snap_dir(), gh + ".json"), "w", encoding="utf-8") as fh:
        json.dump(cfg, fh)


def load_snapshot(gh):
    p = os.path.join(_snap_dir(), gh + ".json")
    if not os.path.exists(p):
        return None
    return json.load(open(p, encoding="utf-8"))


# ---------------------------------------------------------------- diff import
CONTROL_PATHS = {
    "Institution": ("proposed_bank",),
    "Legal name": ("client_legal_name",),
    "Home state / market": ("hq",),
    "Charter type": ("charter_profile", "charter_type"),
    "Target opening": ("charter_profile", "target_opening"),
    "Pre-opening period (months)": ("charter_profile", "pre_open_months"),
    "CBLR election": ("charter_profile", "cblr_election"),
    "Initial capital ($)": ("target_state", "initial_capital"),
    "Scenario name": ("scenario_name",),
}
import re as _re
_RAISE_ROW = _re.compile(r"^Staged raise (\d+) \u2014 (quarter|amount)", 0)


def _raise_row_match(label):
    m = _re.match(r"^Staged raise (\d+) — (quarter|amount)", str(label))
    return (int(m.group(1)) - 1, m.group(2)) if m else None
FAM_ARR = {"lending": "lending_products", "deposit": "deposit_products"}


def _get(cfg, path):
    o = cfg
    for k in path:
        if o is None:
            return None
        o = o.get(k) if isinstance(o, dict) else None
    return o


def _set(cfg, path, val):
    o = cfg
    for k in path[:-1]:
        o = o.setdefault(k, {})
    o[path[-1]] = val


def diff_import(data, current_cfg):
    """Filled FIW -> (merged cfg, edits report). Fail-closed on unknown
    generation state; only cells that DIFFER from the snapshot are applied,
    so untouched defaults keep their provenance and in-app edits made since
    generation survive unless the workbook explicitly changed that cell."""
    from openpyxl import load_workbook
    wb = load_workbook(io.BytesIO(data), data_only=True)
    if "README" not in wb.sheetnames:
        raise ValueError("not a Foundry Input Workbook (no README sheet)")
    gh = None
    for r in wb["README"].iter_rows():
        if r[0].value == "Generation hash":
            gh = r[1].value
    if not gh:
        raise ValueError("no generation hash on README — cannot diff-import")
    snap = _read_embedded_state(wb)
    base_src = "embedded"
    if snap is None:                      # legacy workbook (pre self-contained format)
        snap = load_snapshot(str(gh))
        base_src = "workspace snapshot"
    if snap is None:
        raise ValueError(f"generation state {gh} not found — this workbook predates the "
                          "self-contained format and its workspace snapshot is gone (older run, "
                          "another instance, or a redeploy). Regenerate the input workbook from "
                          "the current configuration and reapply your edits; nothing was changed. "
                          "Workbooks generated from now on carry their own state and never hit this.")
    # THE WORKBOOK IS THE DOCUMENT: import rebases onto the workbook's own
    # generation state (the bank it describes), with the human's edits on top.
    # The open session never silently supplies the base — uploading a workbook
    # from another engagement reconstitutes THAT bank, and the report says so.
    merged = json.loads(json.dumps(snap))
    edits = []
    session_differed = json.dumps(current_cfg, sort_keys=True) != json.dumps(snap, sort_keys=True)

    if "CONTROL" in wb.sheetnames:
        for r in wb["CONTROL"].iter_rows(min_row=2):
            label, val = r[0].value, r[1].value
            rr = _raise_row_match(label)
            if rr is not None:
                idx, field = rr
                arr = (snap["assumptions"].get("capital_raises") or [])
                old_v = arr[idx].get(field) if idx < len(arr) else None
                new_v = int(val) if field == "quarter" and val not in ("", None) else (
                          float(val) if val not in ("", None) else None)
                if new_v != old_v and new_v is not None:
                    tgt = merged["assumptions"].setdefault("capital_raises", [])
                    while len(tgt) <= idx:
                        tgt.append({"quarter": 1, "amount": 0})
                    tgt[idx][field] = new_v
                    edits.append({"key": f"capital_raises.{idx}.{field}",
                                   "from": old_v, "to": new_v})
                continue
            path = CONTROL_PATHS.get(label)
            if not path:
                continue
            old = _get(snap, path)
            if label == "CBLR election":
                val = str(val).strip().lower() in ("yes", "y", "true", "1")
                if bool(val) == bool(old):
                    continue
            if val != old and not (val in ("", None) and old in ("", None)):
                edits.append({"key": ".".join(str(x) for x in path), "from": old, "to": val})
                _set(merged, path, val)

    # identity follow-through: renaming the bank renames a scenario label that
    # carried the old bank's name — derived, and logged like any other edit.
    _old_pb = str(snap.get("proposed_bank") or "")
    _new_pb = str(merged.get("proposed_bank") or "")
    _sn = str(merged.get("scenario_name") or "")
    if _new_pb and _new_pb != _old_pb and _old_pb and _sn.startswith(_old_pb):
        _renamed = _new_pb + _sn[len(_old_pb):]
        edits.append({"key": "scenario_name", "from": _sn, "to": _renamed,
                       "note": "derived — scenario label followed the bank rename"})
        merged["scenario_name"] = _renamed

    for sheet, fam in (("ASSM_LOANS", "lending"), ("ASSM_DEPOSITS", "deposit")):
        if sheet not in wb.sheetnames:
            continue
        for r in wb[sheet].iter_rows(min_row=2):
            key, val, units = r[0].value, r[3].value, (r[4].value or "")
            if not key or "fact" in str(units):
                continue
            _, idx, field = key.split(".", 2)
            idx = int(idx)
            arr = snap["assumptions"].get(FAM_ARR[fam], [])
            if idx >= len(arr):
                continue
            if "." in field:
                a, b = field.split(".", 1)
                old = (arr[idx].get(a) or {}).get(b)
            else:
                old = arr[idx].get(field)
            newv = None if val in ("", None) else (float(val) if isinstance(val, (int, float)) else val)
            if isinstance(old, (int, float)) and isinstance(newv, (int, float)):
                changed = abs(float(old) - float(newv)) > 1e-12
            else:
                changed = (old or None) != (newv or None)
            if changed:
                tgt = merged["assumptions"].setdefault(FAM_ARR[fam], [])
                if idx >= len(tgt):
                    continue
                if "." in field:
                    a, b = field.split(".", 1)
                    tgt[idx].setdefault(a, {})[b] = newv
                else:
                    tgt[idx][field] = newv
                edits.append({"key": f"{fam}.{idx}.{field}", "from": old, "to": newv})
    rep = {"generation_hash": str(gh), "edits": edits, "edit_count": len(edits),
            "base": base_src}
    if session_differed:
        rep["session_note"] = ("the open session differed from this workbook's engagement — "
                                "the workbook's state now governs (the session's unsaved "
                                "differences were replaced, not merged)")
    return merged, rep
