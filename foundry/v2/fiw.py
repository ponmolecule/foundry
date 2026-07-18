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
    wb.save(buf)
    return buf.getvalue(), gh


# ---------------------------------------------------------------- snapshots
import os


def _snap_dir():
    base = os.environ.get("FOUNDRY_DATA_DIR", os.path.join(os.getcwd(), "data"))
    d = os.path.join(base, "fiw")
    os.makedirs(d, exist_ok=True)
    return d


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
    "Pre-opening organizational costs ($)": ("assumptions", "org_costs_pre_open"),
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
    snap = load_snapshot(str(gh))
    if snap is None:
        raise ValueError(f"generation state {gh} not found on this workspace — "
                          "the workbook came from an older run, another instance, or a redeploy "
                          "cleared the workspace disk (snapshots live under FOUNDRY_DATA_DIR). "
                          "Regenerate the input workbook from the current configuration and "
                          "reapply your edits; nothing was changed.")
    merged = json.loads(json.dumps(current_cfg))
    edits = []

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
    return merged, {"generation_hash": str(gh), "edits": edits, "edit_count": len(edits)}
