"""r240: Peer Cohort workbook.

Built from what the Peer Cohort page already holds (corridor bands and the vintage corridor), so an export never
re-queries the substrate. Two shapes, chosen by cohort size:

* Curated cohorts (per-bank series available, up to CURATED_MAX banks): one column per peer per age quarter,
  with min / P10 / P25 / median / P75 / P90 / max, n and placement as live formulas over those columns.
* Larger cohorts: the distribution itself (n, min, P10-P90, max per age quarter) as published by the
  substrate, with placement as a live formula; a Members sheet lists the cohort.

Peer data are inputs (blue); every aggregate and placement is a formula (black). Arial throughout.
"""
from __future__ import annotations

import io
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.chart import LineChart, Reference
from openpyxl.chart.shapes import GraphicalProperties
from openpyxl.chart.marker import Marker
from openpyxl.drawing.line import LineProperties

METRIC_LABEL = {"roa": "ROA", "nim": "NIM", "efficiency_ratio": "Efficiency ratio", "tier1_ratio": "Tier 1 ratio",
                "cet1_ratio": "CET1 ratio", "leverage_ratio": "Leverage ratio", "total_rbc_ratio": "Total capital ratio",
                "net_charge_off_rate": "Net charge-off rate", "noninterest_share": "Noninterest revenue share"}

_SERIES_STYLE = {"Min": ("C9C2B3", 12000, "dash"), "P25": ("D9C499", 15000, None), "Median": ("343434", 22000, None),
                 "P75": ("D9C499", 15000, None), "Max": ("C9C2B3", 12000, "dash"), "Modeled": ("A3772A", 28000, None)}


def _corridor_chart(ws, title, cat_col, cols, first_row, last_row):
    """Line chart of the corridor: peer min/P25/median/P75/max plus the modeled bank. Blank cells plot as gaps."""
    ch = LineChart()
    ch.title = title; ch.height = 7.5; ch.width = 15
    ch.legend.position = "b"; ch.display_blanks = "span"
    ch.y_axis.majorGridlines.spPr = GraphicalProperties(ln=LineProperties(solidFill="EFEFEF"))
    ch.x_axis.title = "Age (quarters since opening)"
    for col in cols:
        ch.add_data(Reference(ws, min_col=col, min_row=first_row - 1, max_row=last_row), titles_from_data=True)
    ch.set_categories(Reference(ws, min_col=cat_col, min_row=first_row, max_row=last_row))
    for idx, srs in enumerate(ch.series):   # by position: series objects compare equal by content
        name = ws.cell(row=first_row - 1, column=cols[idx]).value
        color, width, dash = _SERIES_STYLE.get(name, ("8F6B30", 15000, None))
        srs.graphicalProperties = GraphicalProperties(ln=LineProperties(solidFill=color, w=width, prstDash=dash))
        srs.smooth = False
        if name == "Modeled":
            srs.marker = Marker(symbol="circle", size=6)
            srs.marker.graphicalProperties = GraphicalProperties(solidFill=color, ln=LineProperties(solidFill=color))
        else:
            srs.marker = Marker(symbol="none")
    return ch

CURATED_MAX = 25
FONT = "Arial"
F_TITLE = Font(name=FONT, size=13, bold=True)
F_NOTE = Font(name=FONT, size=9, italic=True, color="666666")
F_HEAD = Font(name=FONT, size=10, bold=True, color="343434")
F_BODY = Font(name=FONT, size=10, color="000000")
F_INPUT = Font(name=FONT, size=10, color="0000FF")
F_MODEL = Font(name=FONT, size=10, bold=True, color="8F6B30")
FILL_HEAD = PatternFill("solid", fgColor="EFEFEF")
THIN = Border(bottom=Side(style="thin", color="C4C4C4"))
NUM = "#,##0.00;-#,##0.00;-"
STATS = ("min", "p10", "p25", "p50", "p75", "p90", "max")
STAT_LABEL = {"min": "Min", "p10": "P10", "p25": "P25", "p50": "Median", "p75": "P75", "p90": "P90", "max": "Max"}


def _placement_formula(mod, mn, p10, p25, p50, p75, p90, mx, n):
    """Where the modeled value sits against the comparison set; blank when either side is missing."""
    return (f'=IF(OR({mod}="",{n}=0,{mn}=""),"",IF({mod}<{mn},"below min",IF({mod}<{p10},"min-p10",'
            f'IF({mod}<{p25},"p10-p25",IF({mod}<{p50},"p25-p50",IF({mod}<{p75},"p50-p75",'
            f'IF({mod}<{p90},"p75-p90",IF({mod}<={mx},"p90-max","above max"))))))))')


def _header(ws, row, labels, widths=None):
    for i, lab in enumerate(labels, start=1):
        c = ws.cell(row=row, column=i, value=lab)
        c.font, c.fill, c.border = F_HEAD, FILL_HEAD, THIN
        c.alignment = Alignment(horizontal="left" if i == 1 else "right", vertical="center")
    if widths:
        for i, w in enumerate(widths, start=1):
            ws.column_dimensions[get_column_letter(i)].width = w


def _num(v):
    try:
        return None if v is None or v == "" else float(v)
    except (TypeError, ValueError):
        return None


def _safe_sheet(name, used):
    base = "".join(ch for ch in str(name) if ch not in '[]:*?/\\')[:28] or "Metric"
    out, k = base, 2
    while out.lower() in used:
        out, k = f"{base[:25]} {k}", k + 1
    used.add(out.lower())
    return out


def build_workbook(payload: dict) -> bytes:
    wb = Workbook()
    used = set()
    corridor = payload.get("corridor") or []
    vintage = payload.get("vintage") or {}
    vin_modeled = payload.get("vintage_modeled") or {}
    cohort_label = str(payload.get("cohort_label") or "selected cohort")
    quarter = str(payload.get("quarter") or "")
    asof = str(payload.get("as_of") or "")

    # ---------------- Summary: modeled bank vs the comparison set at the horizon quarter ----------------
    ws = wb.active; ws.title = _safe_sheet("Summary", used)
    ws["A1"] = f"Peer corridor: modeled bank vs {cohort_label}" + (f", {quarter}" if quarter else "")
    ws["A1"].font = F_TITLE
    ws["A2"] = ("Peer values are real filed data from the CharterIQ Call Report substrate (inputs, blue). "
                "Placement is a formula comparing the modeled value with the comparison set; it is a factual "
                "position, not a verdict." + (f" Exported {asof}." if asof else ""))
    ws["A2"].font = F_NOTE
    labels = ["Metric", "Basis", "Modeled", "Q12 standalone", "n"] + [STAT_LABEL[s] for s in STATS] + ["Placement"]
    _header(ws, 4, labels, [26, 8, 12, 14, 6] + [11] * len(STATS) + [13])
    r = 5
    for it in corridor:
        ws.cell(row=r, column=1, value=str(it.get("label") or it.get("metric") or "")).font = F_BODY
        ws.cell(row=r, column=2, value=str(it.get("basis") or "")).font = F_BODY
        if it.get("error"):
            c = ws.cell(row=r, column=3, value=f"No peer data: {it.get('error')}"); c.font = F_NOTE
            r += 1; continue
        for col, key, font in ((3, "modeled", F_MODEL), (4, "standalone", F_BODY), (5, "n", F_INPUT)):
            v = _num(it.get(key))
            if v is not None:
                c = ws.cell(row=r, column=col, value=v); c.font = font
                c.number_format = "0" if key == "n" else NUM
        for k, s in enumerate(STATS):
            v = _num(it.get(s))
            if v is not None:
                c = ws.cell(row=r, column=6 + k, value=v); c.font = F_INPUT; c.number_format = NUM
        L = {s: f"{get_column_letter(6 + k)}{r}" for k, s in enumerate(STATS)}
        ws.cell(row=r, column=6 + len(STATS), value=_placement_formula(
            f"C{r}", L["min"], L["p10"], L["p25"], L["p50"], L["p75"], L["p90"], L["max"], f"E{r}")).font = F_BODY
        r += 1
    ws.cell(row=r + 1, column=1, value=("Flow metrics follow the Q12 year-to-date filing convention; Q12 standalone "
                                        "is the three-month result. Stock ratios use the Q12 quarter-end value.")).font = F_NOTE
    ws.freeze_panes = "B5"

    # ---------------- Vintage corridor: de novos at the same age ----------------
    vcorr = (vintage.get("corridor") or {})
    chart_specs = []
    series = vintage.get("series_by_cert") or {}
    names = {str(b.get("cert")): str(b.get("name") or b.get("cert")) for b in (vintage.get("bank_coverage") or [])}
    for metric, block in vcorr.items():
        ages = block.get("ages") or []
        if not ages:
            continue
        mlabel = METRIC_LABEL.get(metric, metric)
        ws = wb.create_sheet(_safe_sheet(mlabel, used))
        per_bank = series.get(metric) or {}
        curated = bool(per_bank) and len(per_bank) <= CURATED_MAX
        mod = vin_modeled.get(metric) or {}
        ws["A1"] = f"{mlabel}: vintage corridor, ages Q1-Q12 ({'each peer shown' if curated else 'cohort distribution'})"
        ws["A1"].font = F_TITLE
        ws["A2"] = ("Peers re-clocked to their opening quarter (age Q1 = first quarter of operation). "
                    + ("Aggregates and placement are formulas over the peer columns." if curated else
                       "Distribution as published by the substrate; ages with too few banks are left blank."))
        ws["A2"].font = F_NOTE
        if curated:
            certs = sorted(per_bank.keys(), key=lambda c: names.get(c, c))
            pc = len(certs)
            labels = ["Age (Q)"] + [names.get(c, c) for c in certs] + [STAT_LABEL[s] for s in STATS] + ["n", "Modeled", "Placement"]
            _header(ws, 4, labels, [9] + [14] * pc + [11] * len(STATS) + [6, 12, 13])
            first, last = get_column_letter(2), get_column_letter(1 + pc)
            for i, a in enumerate(ages):
                r = 5 + i; age = int(a.get("age_q") or i + 1)
                ws.cell(row=r, column=1, value=age).font = F_BODY
                for j, cert in enumerate(certs):
                    v = _num((per_bank.get(cert) or {}).get(str(age), (per_bank.get(cert) or {}).get(age)))
                    if v is not None:
                        c = ws.cell(row=r, column=2 + j, value=v); c.font = F_INPUT; c.number_format = NUM
                rng = f"{first}{r}:{last}{r}"
                base = 2 + pc
                has_obs = any(_num((per_bank.get(c) or {}).get(str(age), (per_bank.get(c) or {}).get(age))) is not None for c in certs)
                fx = {"min": f"MIN({rng})", "p10": f"PERCENTILE({rng},0.1)", "p25": f"PERCENTILE({rng},0.25)",
                      "p50": f"MEDIAN({rng})", "p75": f"PERCENTILE({rng},0.75)", "p90": f"PERCENTILE({rng},0.9)",
                      "max": f"MAX({rng})"}
                for k, s in enumerate(STATS):
                    if not has_obs:
                        continue
                    c = ws.cell(row=r, column=base + k, value=f'=IF(COUNT({rng})=0,"",{fx[s]})')
                    c.font = F_BODY; c.number_format = NUM
                ncol = base + len(STATS)
                ws.cell(row=r, column=ncol, value=f"=COUNT({rng})").font = F_BODY
                mv = _num(mod.get(str(age), mod.get(age)))
                if mv is not None:
                    c = ws.cell(row=r, column=ncol + 1, value=mv); c.font = F_MODEL; c.number_format = NUM
                L = {s: f"{get_column_letter(base + k)}{r}" for k, s in enumerate(STATS)}
                ws.cell(row=r, column=ncol + 2, value=_placement_formula(
                    f"{get_column_letter(ncol + 1)}{r}", L["min"], L["p10"], L["p25"], L["p50"], L["p75"], L["p90"], L["max"],
                    f"{get_column_letter(ncol)}{r}")).font = F_BODY
        else:
            labels = ["Age (Q)", "n"] + [STAT_LABEL[s] for s in STATS] + ["Modeled", "Placement"]
            _header(ws, 4, labels, [9, 6] + [11] * len(STATS) + [12, 13])
            for i, a in enumerate(ages):
                r = 5 + i; age = int(a.get("age_q") or i + 1)
                ws.cell(row=r, column=1, value=age).font = F_BODY
                c = ws.cell(row=r, column=2, value=int(a.get("n") or 0)); c.font = F_INPUT
                if not a.get("suppressed"):
                    for k, s in enumerate(STATS):
                        v = _num(a.get(s))
                        if v is not None:
                            c = ws.cell(row=r, column=3 + k, value=v); c.font = F_INPUT; c.number_format = NUM
                mv = _num(mod.get(str(age), mod.get(age)))
                mcol = 3 + len(STATS)
                if mv is not None:
                    c = ws.cell(row=r, column=mcol, value=mv); c.font = F_MODEL; c.number_format = NUM
                L = {s: f"{get_column_letter(3 + k)}{r}" for k, s in enumerate(STATS)}
                ws.cell(row=r, column=mcol + 1, value=_placement_formula(
                    f"{get_column_letter(mcol)}{r}", L["min"], L["p10"], L["p25"], L["p50"], L["p75"], L["p90"], L["max"],
                    f"B{r}")).font = F_BODY
        ws.freeze_panes = "B5"
        n_rows = len(ages)
        head = [ws.cell(row=4, column=c).value for c in range(1, ws.max_column + 1)]
        cols = [head.index(h) + 1 for h in ("Min", "P25", "Median", "P75", "Max", "Modeled") if h in head]
        if cols and n_rows >= 2:
            ttl = f"{mlabel}: modeled vs peers by age"
            ws.add_chart(_corridor_chart(ws, ttl, 1, cols, 5, 4 + n_rows), f"{get_column_letter(ws.max_column + 2)}4")
            chart_specs.append((ws, ttl, cols, n_rows))

    if chart_specs:
        cs = wb.create_sheet(_safe_sheet("Charts", used))
        cs["A1"] = "Vintage corridor: modeled bank vs peers at the same age"; cs["A1"].font = F_TITLE
        for k, (src, ttl, cols, n_rows) in enumerate(chart_specs):
            cs.add_chart(_corridor_chart(src, ttl, 1, cols, 5, 4 + n_rows), f"{'A' if k % 2 == 0 else 'K'}{3 + (k // 2) * 16}")

    # ---------------- Members ----------------
    cov = vintage.get("bank_coverage") or []
    mem = vintage.get("members") or []
    if cov or mem:
        ws = wb.create_sheet(_safe_sheet("Members", used))
        ws["A1"] = "Comparison set members"; ws["A1"].font = F_TITLE
        if cov:
            _header(ws, 3, ["Cert", "Name", "Age Q1 (anchor)", "Latest filing", "Status"], [10, 38, 16, 14, 48])
            for i, b in enumerate(cov):
                for j, k in enumerate(("cert", "name", "vintage_anchor_q", "latest_filing_q", "status")):
                    ws.cell(row=4 + i, column=1 + j, value=b.get(k)).font = F_BODY
        else:
            _header(ws, 3, ["Cert", "Established", "Ended", "Failure date"], [10, 12, 10, 14])
            for i, b in enumerate(mem):
                for j, k in enumerate(("cert", "est_year", "end_year", "fail_date")):
                    ws.cell(row=4 + i, column=1 + j, value=b.get(k)).font = F_BODY

    # ---------------- Notes ----------------
    ws = wb.create_sheet(_safe_sheet("Notes", used))
    ws.column_dimensions["A"].width = 110
    lines = ["Notes",
             "Source: CharterIQ Call Report substrate (FDIC / FFIEC filings). Peer values are inputs, shown in blue.",
             "Modeled values: Foundry projection; Y1/Y2/Y3 correspond to age quarters 4/8/12 in the vintage sheets.",
             "Percentiles use PERCENTILE (inclusive), the same definition as the substrate's percentile_cont.",
             "Small sets: with few banks, percentiles approach the members' own values; read them as a range.",
             f"Cohort: {cohort_label}." + (f" Vintage fingerprint {vintage.get('fingerprint')}." if vintage.get("fingerprint") else "")]
    for i, t in enumerate(lines, start=1):
        ws.cell(row=i, column=1, value=t).font = F_TITLE if i == 1 else F_BODY
    for wsx in wb.worksheets:
        for row in wsx.iter_rows():
            for c in row:
                if c.font is None or c.font.name != FONT:
                    c.font = Font(name=FONT, size=(c.font.size if c.font else 10), bold=(c.font.bold if c.font else False))
    bio = io.BytesIO(); wb.save(bio)
    return bio.getvalue()
