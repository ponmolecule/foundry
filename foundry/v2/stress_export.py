"""r498: stress run records as workbook sheets. Exports stored records; it never re-runs or creates evidence."""
from __future__ import annotations

_MET = [("cum_ni", "Cumulative net income, full horizon", "$000s"),
        ("peak_cum_loss", "Peak cumulative loss, from M1", "$000s"),
        ("peak_cum_loss_period", "Peak cumulative loss period", ""),
        ("first_profitable", "First profitable period", ""),
        ("sustained_profitable", "Profitable in every period from", ""),
        ("max_unfunded_shortfall", "Peak negative cash (unfunded)", "$000s"),
        ("max_requirement_shortfall", "Peak shortfall to required cash", "$000s"),
        ("first_shortfall", "First shortfall period", ""),
        ("peak_replacement_borrowing", "Peak automatic (replacement) borrowing", "$000s"),
        ("borrowing_expense", "Borrowing expense, full horizon", "$000s"),
        ("cum_provision", "Provision, full horizon", "$000s"),
        ("cum_nii", "Net interest income, full horizon", "$000s"),
        ("min_tier1_leverage", "Minimum Tier 1 leverage", "fraction"),
        ("min_tier1_leverage_period", "Minimum Tier 1 leverage period", ""),
        ("leverage_floor", "Configured leverage floor", "fraction"),
        ("capital_shortfall_diagnostic", "Diagnostic shortfall to floor (not a modeled raise)", "$000s"),
        ("funding_policy", "Funding policy applied", "")]

SERIES = [("ni", "Net income", "$000s"), ("cum_ni", "Cumulative net income", "$000s"),
          ("nii", "Net interest income", "$000s"), ("prov", "Provision", "$000s"),
          ("borrExp", "Borrowing expense", "$000s"), ("cash", "Cash", "$000s"),
          ("unfunded", "Unfunded cash shortfall", "$000s"), ("auto_borrowing", "Automatic borrowing", "$000s"),
          ("deposits", "Deposits", "$000s"), ("grossLoans", "Gross loans", "$000s"),
          ("equity", "Equity", "$000s"), ("lev", "Tier 1 leverage", "%")]


def add_stress_sheets(wb, records, state_of=None):
    from openpyxl.styles import Font
    bold = Font(bold=True)
    ws = wb.create_sheet("Stress Runs")
    ws.append(["Scenario", "Severity", "Kind", "Status", "State", "Run ID", "Started (UTC)", "Base fingerprint",
               "Engine", "Scenario fingerprint", "Funding setting", "Funding policy applied", "Structural check",
               "Zero-shock check", "Errors"])
    for c in ws[1]:
        c.font = bold
    for r in records:
        ws.append([r.get("scenario_name"), r.get("severity_label"), r.get("kind"), r.get("status"),
                   (state_of(r) if state_of else ""), r.get("run_id"), r.get("started_at"), r.get("base_fingerprint"),
                   r.get("engine"), r.get("scenario_fingerprint"), r.get("funding_setting"), r.get("funding_policy"),
                   (r.get("checks") or {}).get("structural"), (r.get("checks") or {}).get("zero_shock"),
                   "; ".join(r.get("errors") or [])])
    ov = wb.create_sheet("Stress Overrides")
    ov.append(["Run ID", "Scenario", "Severity", "Input", "Target (stable ID)", "Operation", "Value (engine units)",
               "From period", "To period", "Resolution", "Base at start", "Stressed at start"])
    for c in ov[1]:
        c.font = bold
    for r in records:
        for o in r.get("resolved_overrides") or []:
            ov.append([r.get("run_id"), r.get("scenario_name"), r.get("severity_label"), o.get("label"), o.get("target"),
                       o.get("op"), o.get("value"), o.get("start"), o.get("end") or "horizon", o.get("mode"),
                       o.get("base_at_start"), o.get("stressed_at_start")])
    me = wb.create_sheet("Stress Metrics")
    done = [r for r in records if r.get("status") == "completed"]
    me.append(["Measure", "Units"] + sum(([f"{r.get('scenario_name')} · {r.get('severity_label')} · base",
                                           f"{r.get('scenario_name')} · {r.get('severity_label')} · stress"] for r in done), []))
    for c in me[1]:
        c.font = bold
    for key, label, unit in _MET:
        me.append([label, unit] + sum(([(r["base"]["metrics"] or {}).get(key), (r["stress"]["metrics"] or {}).get(key)] for r in done), []))
    at = wb.create_sheet("Stress Attribution")
    at.append(["Run ID", "Scenario", "Severity", "Method", "Metric", "Override run alone", "Effect ($000s)", "No effect"])
    for c in at[1]:
        c.font = bold
    for r in done:
        a = r.get("attribution")
        if not a:
            continue
        for row in a.get("rows") or []:
            at.append([r.get("run_id"), r.get("scenario_name"), r.get("severity_label"), a.get("method"), a.get("metric"),
                       row.get("label"), row.get("effect"), "yes" if row.get("no_effect") else ""])
        at.append([r.get("run_id"), r.get("scenario_name"), r.get("severity_label"), a.get("method"), a.get("metric"),
                   "Interaction", a.get("interaction"), ""])
        at.append([r.get("run_id"), r.get("scenario_name"), r.get("severity_label"), a.get("method"), a.get("metric"),
                   "Total change", a.get("total"), ""])
    se = wb.create_sheet("Stress Series")
    n = max((len((r["base"]["series"] or {}).get("ni") or []) for r in done), default=0)
    se.append(["Run ID", "Scenario", "Severity", "Series", "Units", "Case"] + [f"P{i + 1}" for i in range(n)])
    for c in se[1]:
        c.font = bold
    for r in done:
        for key, label, unit in SERIES:
            for case in ("base", "stress"):
                se.append([r.get("run_id"), r.get("scenario_name"), r.get("severity_label"), label, unit, case]
                          + list((r[case]["series"] or {}).get(key) or []))
    return wb


def stress_workbook(records, state_of=None):
    from openpyxl import Workbook
    wb = Workbook()
    wb.remove(wb.active)
    return add_stress_sheets(wb, records, state_of)
