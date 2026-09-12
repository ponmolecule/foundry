"""Calculation-audit workbook for Foundry v2.

This is intentionally an audit/reconciliation artifact, not a client exhibit.  It exposes
native-cadence calculated series in organized worksheets so a reviewer can line Foundry up
against a source model and identify the first period / subsystem where economics diverge.

The workbook is presentation-only: it consumes the same deterministic run/config contracts
as the UI and never feeds values back into the engine.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from .growth import growth_context_from_cfg
from .timebase import model_period_end_date

_DARK = "182640"
_DARK2 = "24334D"
_GOLD = "D8A85E"
_LIGHT = "EDF0F5"
_MUTED = "8A92A3"
_BLUE = "0000FF"
_GREEN = "008000"
_RED = "FF0000"

_MONEY_FMT = '#,##0.000;[Red](#,##0.000);-'
_NUM_FMT = '#,##0.000000;[Red](#,##0.000000);-'
_COUNT_FMT = '#,##0.000;[Red](#,##0.000);-'
_RATE_FMT = '0.000000;[Red](0.000000);-'


def _slug_label(path: str) -> str:
    return path.rsplit(".", 1)[-1].replace("_", " ")


def _period_labels(cfg: Mapping[str, Any], n: int, ppy: int) -> list[str]:
    prefix = "M" if ppy == 12 else ("Y" if ppy == 1 else "Q")
    out = []
    for p in range(1, n + 1):
        try:
            d = model_period_end_date(cfg, p, ppy)
            out.append(f"{prefix}{p}\n{d.isoformat()}")
        except Exception:
            out.append(f"{prefix}{p}")
    return out


def _sheet_title(ws, title: str, subtitle: str | None = None, width: int = 8) -> int:
    ws.sheet_view.showGridLines = False
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=max(4, width))
    c = ws.cell(1, 1, title)
    c.fill = PatternFill("solid", fgColor=_DARK)
    c.font = Font(color=_LIGHT, bold=True, size=13)
    c.alignment = Alignment(vertical="center")
    ws.row_dimensions[1].height = 24
    if subtitle:
        ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=max(4, width))
        c2 = ws.cell(2, 1, subtitle)
        c2.font = Font(color=_MUTED, italic=True, size=9)
        c2.alignment = Alignment(wrap_text=True, vertical="top")
        ws.row_dimensions[2].height = 28
        return 4
    return 3


def _style_header(ws, row: int, ncols: int) -> None:
    thin = Side(style="thin", color="3A4C6E")
    for c in ws[row][:ncols]:
        c.fill = PatternFill("solid", fgColor=_DARK2)
        c.font = Font(color=_LIGHT, bold=True, size=9)
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = Border(bottom=thin)
    ws.row_dimensions[row].height = 34


def _finish_wide(ws, header_row: int, n_period_cols: int, meta_cols: int = 4) -> None:
    ws.freeze_panes = ws.cell(header_row + 1, meta_cols + 1)
    widths = [18, 38, 34, 18]
    for i, w in enumerate(widths[:meta_cols], 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    for j in range(meta_cols + 1, meta_cols + 1 + n_period_cols):
        ws.column_dimensions[get_column_letter(j)].width = 15
    ws.auto_filter.ref = f"A{header_row}:{get_column_letter(meta_cols+n_period_cols)}{ws.max_row}"


def _write_wide_rows(ws, cfg, rows, *, title: str, subtitle: str, n: int, ppy: int,
                     include_open: bool = False) -> None:
    labels = _period_labels(cfg, n, ppy)
    pcols = (["Open"] if include_open else []) + labels
    hr = _sheet_title(ws, title, subtitle, 4 + len(pcols))
    ws.append([]) if ws.max_row < hr - 1 else None
    ws.cell(hr, 1, "Section")
    ws.cell(hr, 2, "Calculation / Series")
    ws.cell(hr, 3, "Key / Series ID")
    ws.cell(hr, 4, "Units")
    for j, x in enumerate(pcols, 5):
        ws.cell(hr, j, x)
    _style_header(ws, hr, 4 + len(pcols))
    for section, label, key, units, vals, fmt in rows:
        vals = list(vals or [])
        expected = n + (1 if include_open else 0)
        if len(vals) < expected:
            vals += [None] * (expected - len(vals))
        elif len(vals) > expected:
            vals = vals[:expected]
        ws.append([section, label, key, units] + vals)
        r = ws.max_row
        for c in range(5, 5 + expected):
            ws.cell(r, c).number_format = fmt or _NUM_FMT
            ws.cell(r, c).alignment = Alignment(horizontal="right")
        ws.cell(r, 2).alignment = Alignment(wrap_text=True)
        ws.cell(r, 3).font = Font(name="Consolas", size=8, color=_MUTED)
    _finish_wide(ws, hr, len(pcols), 4)


def _series_rows(fin: Mapping[str, Any], section: str, units: str, n: int,
                 *, include_open: bool = False, fmt: str = _MONEY_FMT):
    rows = []
    for key, arr in (fin or {}).items():
        if not isinstance(arr, list) or not all(x is None or isinstance(x, (int, float)) for x in arr):
            continue
        vals = list(arr)
        target = n + (1 if include_open else 0)
        if include_open and len(vals) == n:
            vals = [None] + vals
        elif not include_open and len(vals) == n + 1:
            vals = vals[1:]
        rows.append((section, _slug_label(key), key, units, vals[:target], fmt))
    return rows


def _raw_opex_context(cfg: Mapping[str, Any], results: Mapping[str, Any], n: int, ppy: int):
    """Rebuild only observational inputs needed to audit additive Opex components.

    These helpers are the same deterministic primitives used by the engine.  The audit workbook
    never changes model outputs; it resolves component amounts independently for traceability.
    """
    a = (cfg.get("assumptions") or {})
    gctx = growth_context_from_cfg(cfg, ppy)

    cac_monthly, cac_beginning = {}, {}
    if a.get("cac_feeds"):
        from .cac_feeder import cac_auc_rollforward
        for nm, feed in (a.get("cac_feeds") or {}).items():
            sid = str((feed or {}).get("series_id") or nm or "").strip()
            if not sid:
                continue
            rr = cac_auc_rollforward(feed or {}, n, ppy, assumptions=a, growth_context=gctx)
            cac_monthly[sid] = list(rr.get("auc_end_by_month") or [])
            cac_beginning[sid] = float((feed or {}).get("beginning_auc") or 0.0)

    qpub = (((results.get("fee_stream_quantities") or {}).get("series")) or {})
    qraw = {sid: [float(x or 0.0) * 1000.0 for x in vals] for sid, vals in qpub.items()}
    known_ids = set(qraw)
    try:
        from .opex_extensions import fee_stream_quantity_catalog, fee_stream_balance_quantity_catalog
        known_ids.update(x["series_id"] for x in fee_stream_quantity_catalog(a))
        known_ids.update(x["series_id"] for x in fee_stream_balance_quantity_catalog(a))
    except Exception:
        pass

    pools = {}
    if a.get("cost_pools"):
        from .cost_pools import cost_pool_series_map
        pools = cost_pool_series_map(a, n, ppy, growth_context=gctx)

    ta = [float(x or 0.0) * 1000.0 for x in (((results.get("financials") or {}).get("bs") or {}).get("totalAssets") or [])]
    is_ = ((results.get("financials") or {}).get("is") or {})
    return {
        "growth_context": gctx,
        "cac_monthly": cac_monthly,
        "cac_beginning": cac_beginning,
        "quantity_history": qraw,
        "known_quantity_ids": sorted(known_ids),
        "cost_pools": pools,
        "total_assets": ta,
        "fee_income": [float(x or 0.0) * 1000.0 for x in (is_.get("fees") or [0.0] * n)],
        "gain_on_sale": [float(x or 0.0) * 1000.0 for x in (is_.get("gos") or [0.0] * n)],
        "servicing_net": [float(x or 0.0) * 1000.0 for x in (is_.get("servNet") or [0.0] * n)],
    }


def _operating_expense_rows(cfg, results, n, ppy):
    is_ = ((results.get("financials") or {}).get("is") or {})
    rows = []
    for key, label in (
        ("prodOpex", "Product operating expense"),
        ("feeOpex", "Fee Product costs"),
        ("workforceComp", "Workforce compensation"),
        ("otherOpex", "Other operating expense"),
        ("depreciationExpense", "Depreciation expense"),
        ("overhead", "Corporate overhead"),
    ):
        if key in is_:
            rows.append(("Income Statement", label, key, "$000s / engine period", is_[key], _MONEY_FMT))
    if is_.get("overhead") is not None:
        total_nie = [float((is_.get("prodOpex") or [0]*n)[i] or 0)
                     + float((is_.get("feeOpex") or [0]*n)[i] or 0)
                     + float((is_.get("overhead") or [0]*n)[i] or 0) for i in range(n)]
        rows.append(("Income Statement", "Total NIE", "derived:total_nie", "$000s / engine period", total_nie, _MONEY_FMT))

    a = cfg.get("assumptions") or {}
    nd = a.get("nie_detail") or {}
    cats = nd.get("categories") or []
    if not cats:
        return rows

    from .income_modules import nie_category_series
    from .opex_extensions import (recognition_spec_for_category, resolve_recognition,
                                  resolve_settlement, normalize_settlement,
                                  resolve_linked_components, resolve_cost_pool_calculation,
                                  linked_component_amount)
    ctx = _raw_opex_context(cfg, results, n, ppy)
    component_sum = [0.0] * n

    for ci, cat in enumerate(cats):
        cname = str((cat or {}).get("name") or f"Category {ci+1}")
        sid = str((cat or {}).get("series_id") or "")
        econ = nie_category_series(cat, n, ppy, growth_context=ctx["growth_context"])
        recspec = recognition_spec_for_category(cat, ppy)
        recog = resolve_recognition(econ, recspec, ppy, context=ctx["growth_context"])
        econ_k = [float(x or 0.0) / 1000.0 for x in econ]
        recog_k = [float(x or 0.0) / 1000.0 for x in recog]
        rows.append((f"Recurring · {cname}", "Economic trajectory", sid, "$000s / engine period", econ_k, _MONEY_FMT))
        rows.append((f"Recurring · {cname}", "Recognized expense", sid, "$000s / engine period", recog_k, _MONEY_FMT))
        for i, v in enumerate(recog_k): component_sum[i] += v

        sett = resolve_settlement(recog, normalize_settlement((cat or {}).get("settlement"), ppy), ppy,
                                  context=ctx["growth_context"])
        rows.append((f"Recurring · {cname}", "Cash settlement", sid, "$000s / engine period",
                     [float(x or 0.0)/1000.0 for x in sett["cash"]], _MONEY_FMT))
        rows.append((f"Recurring · {cname}", "Prepaid balance", sid, "$000s EOP",
                     [float(x or 0.0)/1000.0 for x in sett["prepaid"]], _MONEY_FMT))
        rows.append((f"Recurring · {cname}", "Accrued balance", sid, "$000s EOP",
                     [float(x or 0.0)/1000.0 for x in sett["accrued"]], _MONEY_FMT))

        cp = resolve_cost_pool_calculation(cat, n, ppy, context=ctx["growth_context"], assumptions=a)
        comps = [cp] if cp is not None else resolve_linked_components(cat, n, ppy,
                                                                      context=ctx["growth_context"], assumptions=a)
        raw_comps = ([((cat or {}).get("calculation") or {})] if cp is not None else list((cat or {}).get("linked_components") or []))
        for j, comp in enumerate(comps):
            raw = raw_comps[j] if j < len(raw_comps) else {}
            drv = str((comp or {}).get("driver") or "component")
            nm = str((raw or {}).get("name") or (comp or {}).get("name") or drv.replace("_", " "))
            cid = str((raw or {}).get("component_id") or (raw or {}).get("series_id") or (comp or {}).get("series_id") or (comp or {}).get("ref") or "")
            vals = []
            for i in range(n):
                qmap = {sid0: (arr[i] if i < len(arr) else 0.0) for sid0, arr in ctx["quantity_history"].items()}
                pmap = {sid0: (arr[i] if i < len(arr) else 0.0) for sid0, arr in ctx["cost_pools"].items()}
                metrics = {
                    "fee_income": ctx["fee_income"][i] if i < len(ctx["fee_income"]) else 0.0,
                    "gain_on_sale": ctx["gain_on_sale"][i] if i < len(ctx["gain_on_sale"]) else 0.0,
                    "servicing_net": ctx["servicing_net"][i] if i < len(ctx["servicing_net"]) else 0.0,
                    "fee_stream_quantities": qmap,
                    "customer_acquisition_auc_monthly": ctx["cac_monthly"],
                    "customer_acquisition_auc_beginning": ctx["cac_beginning"],
                    "fee_stream_quantity_history": ctx["quantity_history"],
                    "fee_stream_quantity_known_ids": ctx["known_quantity_ids"],
                    "bank_total_assets_end_by_period": ctx["total_assets"],
                    "cost_pool": pmap,
                    "periods_per_year": ppy,
                }
                try:
                    amt = linked_component_amount(comp, i, metrics)
                except Exception:
                    amt = None
                vals.append(None if amt is None else float(amt) / 1000.0)
            rows.append((f"Additive · {cname}", nm, cid or drv, "$000s / engine period", vals, _MONEY_FMT))
            for i, v in enumerate(vals):
                if v is not None: component_sum[i] += v

    rows.append(("Reconciliation", "Recurring + additive components", "audit:component_sum",
                 "$000s / engine period", component_sum, _MONEY_FMT))
    other = list(is_.get("otherOpex") or [0.0] * n)
    residual = [float(other[i] or 0.0) - float(component_sum[i] or 0.0) for i in range(n)]
    rows.append(("Reconciliation", "Residual inside Other Opex (e.g. simplified assessments / gross-up)",
                 "audit:other_opex_residual", "$000s / engine period", residual, _MONEY_FMT))
    return rows


def _workforce_rows(cfg, results, n, ppy):
    wfout = results.get("workforce") or {}
    wfcfg = (((cfg.get("assumptions") or {}).get("nie_detail") or {}).get("workforce") or {})
    roles = list(wfcfg.get("roles") or [])
    rows = []
    if not roles and not wfout:
        return rows
    hires = list(wfout.get("resolved_hire_periods") or [])
    counts = list(wfout.get("counts") or [])
    gctx = growth_context_from_cfg(cfg, ppy)
    from .workforce import workforce_role_compensation_series
    default_load = float(wfcfg.get("default_payroll_load_rate") or 0.0)
    default_spec = wfcfg.get("default_salary_growth_spec")
    total = [0.0] * n
    for i, role in enumerate(roles):
        name = str((role or {}).get("role") or f"Role {i+1}")
        sid = str((role or {}).get("series_id") or "")
        cnt = list(counts[i]) if i < len(counts) else [0.0] * n
        hire = hires[i] if i < len(hires) else (role or {}).get("hire_period")
        start = int(hire or 1)
        annual = workforce_role_compensation_series(role, n, ppy, growth_context=gctx,
                                                     start_period=start, default_growth_spec=default_spec)
        load = float((role or {}).get("payroll_load_rate") if (role or {}).get("payroll_load_rate") is not None else default_load)
        exp = []
        for p in range(n):
            active_count = float(cnt[p] or 0.0) if p < len(cnt) else 0.0
            annual_now = float(annual[p] or 0.0) if p < len(annual) else 0.0
            e = annual_now * active_count * (1.0 + load) / float(ppy) / 1000.0
            exp.append(e)
            total[p] += e
        rows.append((name, "Active count", sid, "FTE / headcount", cnt, _COUNT_FMT))
        rows.append((name, "Annual compensation / FTE", sid, "$ / year", annual, _MONEY_FMT))
        rows.append((name, f"Payroll load ({load:.4%})", sid, "decimal", [load] * n, _RATE_FMT))
        rows.append((name, f"Payroll expense · resolved hire {hire or '—'}", sid, "$000s / engine period", exp, _MONEY_FMT))
    if wfout.get("comp"):
        rows.append(("Reconciliation", "Engine workforce compensation", "workforce.comp", "$000s / engine period",
                     wfout.get("comp"), _MONEY_FMT))
        rows.append(("Reconciliation", "Sum of role payroll expense", "audit:role_comp_sum", "$000s / engine period",
                     total, _MONEY_FMT))
    return rows


def _cac_rows(cfg, results, n, ppy):
    out = []
    a = cfg.get("assumptions") or {}
    pubs = results.get("customer_acquisition") or {}
    if not pubs:
        return out
    from .cac_feeder import cac_auc_rollforward
    from .balance_measures import monthly_balance_measure_series
    gctx = growth_context_from_cfg(cfg, ppy)
    months_per_period = 12 // ppy
    for nm, pub in pubs.items():
        feed = (a.get("cac_feeds") or {}).get(nm) or {}
        sid = str(feed.get("series_id") or nm)
        raw = cac_auc_rollforward(feed, n, ppy, assumptions=a, growth_context=gctx)
        mend = list(raw.get("auc_end_by_month") or [])
        beg = float(feed.get("beginning_auc") or 0.0)
        mavg = monthly_balance_measure_series(beg, mend, "period_average")
        avg_native = []
        for i in range(n):
            lo, hi = i * months_per_period, min(len(mavg), (i + 1) * months_per_period)
            avg_native.append((sum(float(x or 0.0) for x in mavg[lo:hi]) / max(1, hi - lo)) / 1000.0 if hi > lo else None)
        out.append((nm, "AUC period end", sid, "$000s EOP", pub.get("aucEndByPeriod") or [], _MONEY_FMT))
        out.append((nm, "AUC period average", sid, "$000s average", avg_native, _MONEY_FMT))
        out.append((nm, "Active customers period end", sid, "count", pub.get("customerEndByPeriod") or [], _COUNT_FMT))
        out.append((nm, "Active customers period average", sid, "count", pub.get("customerAverageByPeriod") or [], _COUNT_FMT))
        out.append((nm, "Annual-count measure by period", sid, "count", pub.get("customerAnnualCountByPeriod") or [], _COUNT_FMT))
    return out


def _product_rows(results, n):
    rows = []
    for p in results.get("products") or []:
        name = str(p.get("name") or "Product")
        fam = str(p.get("family") or "")
        for key, arr in p.items():
            if not isinstance(arr, list) or not all(x is None or isinstance(x, (int, float)) for x in arr):
                continue
            vals = list(arr)
            if len(vals) == n + 1:
                vals = vals[1:]
            if len(vals) != n:
                continue
            if key in ("rateQ", "ftp_rate"):
                units, fmt = ("%" if key == "rateQ" else "decimal annual rate"), _RATE_FMT
            else:
                units, fmt = "$000s / public run units", _MONEY_FMT
            rows.append((f"{fam} · {name}", _slug_label(key), key, units, vals, fmt))
    return rows


def _fee_cost_rows(cfg, results, n, ppy):
    rows = []
    for p in results.get("products") or []:
        name = str(p.get("name") or "Product")
        for key, label in (("fees", "Fee revenue"), ("passCost", "Fee Product cost"), ("opex", "Product operating expense")):
            arr = p.get(key)
            if isinstance(arr, list) and len(arr) == n:
                rows.append((name, label, key, "$000s / engine period", arr, _MONEY_FMT))

    # Authoring-level cost factors are economically important audit evidence.  r83+ keeps
    # the original scalar cost and a dimensionless multiplier as separate layers; expose both
    # paths so a reviewer can reconcile a product-cost difference without reverse-engineering
    # the stream JSON.  The short-lived r82 replacement factor_path remains visible as such.
    from .income_modules import _fee_cost_factor_value
    gctx = growth_context_from_cfg(cfg, ppy)
    for prod in ((cfg.get("assumptions") or {}).get("obs_exposures") or []):
        pname = str((prod or {}).get("name") or "Fee Product")
        for si, st in enumerate((prod or {}).get("fee_streams") or []):
            cost = (st or {}).get("cost") or {}
            kind = str(cost.get("kind") or "none")
            if kind == "none":
                continue
            params = cost.get("params") or {}
            sname = str((st or {}).get("name") or f"Stream {si+1}")
            section = f"{pname} › {sname}"
            sid = str((st or {}).get("quantity_series_id") or "")
            if kind == "per_unit":
                base = float(params.get("cost_per_unit") or 0.0)
                base_units = "$ / unit"
                base_fmt = _NUM_FMT
            else:
                base = float(params.get("pct") or 0.0)
                base_units = "decimal share of gross fee revenue"
                base_fmt = _RATE_FMT
            rows.append((section, "Base cost factor", sid or f"cost:{kind}", base_units, [base] * n, base_fmt))

            legacy_path = params.get("factor_path")
            mult_path = params.get("multiplier_path")
            ctx = {"growth_context": gctx}
            if legacy_path is not None:
                effective = [_fee_cost_factor_value(legacy_path, q, ppy, ctx, base) for q in range(1, n + 1)]
                rows.append((section, "Saved r82 replacement cost factor", sid or "legacy:factor_path",
                             base_units, effective, base_fmt))
            else:
                mult = ([_fee_cost_factor_value(mult_path, q, ppy, ctx, 1.0) for q in range(1, n + 1)]
                        if mult_path is not None else [1.0] * n)
                effective = [base * float(x or 0.0) for x in mult]
                rows.append((section, "Cost multiplier", sid or "cost:multiplier", "dimensionless", mult, _NUM_FMT))
                rows.append((section, "Effective cost factor", sid or "cost:effective", base_units, effective, base_fmt))
    return rows


def _quantity_rows(cfg, results, n):
    meta = {}
    try:
        from .opex_extensions import fee_stream_quantity_catalog, fee_stream_balance_quantity_catalog
        a = cfg.get("assumptions") or {}
        for item in fee_stream_quantity_catalog(a) + fee_stream_balance_quantity_catalog(a):
            meta[item["series_id"]] = item
    except Exception:
        pass
    rows = []
    qmap = (((results.get("fee_stream_quantities") or {}).get("series")) or {})
    for sid, vals in qmap.items():
        m = meta.get(sid) or {}
        label = " › ".join(x for x in (m.get("product"), m.get("stream")) if x) or sid
        sem = m.get("unit_semantic") or "native observation"
        rows.append((m.get("family") or "Fee stream", label, sid, f"$000s · {sem}", vals, _MONEY_FMT))
    return rows


def _pool_rows(results, n):
    cp = results.get("cost_pools") or {}
    names = cp.get("names") or {}
    rows = []
    for sid, vals in (cp.get("series") or {}).items():
        rows.append(("Cost pool", names.get(sid) or sid, sid, cp.get("units") or "$000s / engine period", vals, _MONEY_FMT))
    return rows


def _flatten_numeric_series(obj: Any, path: str = ""):
    if isinstance(obj, Mapping):
        for k, v in obj.items():
            np = f"{path}.{k}" if path else str(k)
            yield from _flatten_numeric_series(v, np)
        return
    if isinstance(obj, list):
        if obj and all(x is None or isinstance(x, (int, float)) for x in obj):
            yield path, list(obj)
            return
        for i, v in enumerate(obj):
            if isinstance(v, Mapping):
                ident = v.get("name") or v.get("role") or v.get("id") or i
                yield from _flatten_numeric_series(v, f"{path}[{ident}]")


def _all_series_rows(results, n):
    rows = []
    seen = set()
    for path, vals in _flatten_numeric_series(results):
        if path in seen or len(vals) not in (n, n + 1):
            continue
        seen.add(path)
        arr = vals[1:] if len(vals) == n + 1 else vals
        low = path.lower()
        if any(x in low for x in ("count", "customer")):
            units, fmt = "native / count", _COUNT_FMT
        elif any(x in low for x in ("rate", "ratio", "roa", "roe", "nim", "eff", "lev", "pct")):
            units, fmt = "native rate / ratio", _RATE_FMT
        else:
            units, fmt = "public run units", _MONEY_FMT
        section = path.split(".", 1)[0]
        rows.append((section, path, path, units, arr, fmt))
    return rows


def calculation_audit_workbook(cfg: Mapping[str, Any], results: Mapping[str, Any]) -> Workbook:
    """Build a multi-sheet reconciliation workbook from one validated Foundry run."""
    a = cfg.get("assumptions") or {}
    ppy = int(a.get("periods_per_year") or 4)
    n = int(a.get("n_periods") or 12)
    wb = Workbook()
    wb.remove(wb.active)

    idx = wb.create_sheet("Index")
    hr = _sheet_title(idx, "Foundry Calculation Audit Workbook",
                      "Native-cadence reconciliation output. Designed for model comparison and debugging; not a filing exhibit.", 8)
    meta = [
        ("Client", (results.get("engagement_echo") or {}).get("client") or cfg.get("proposed_bank")),
        ("Engagement ID", cfg.get("engagement_id")),
        ("Config hash", results.get("config_hash")),
        ("Run hash", results.get("run_hash")),
        ("Engine", results.get("engine_version")),
        ("Cadence", f"{ppy} periods/year"),
        ("Projection periods", n),
        ("Public monetary units", "$000s unless a sheet states otherwise"),
    ]
    for k, v in meta:
        idx.append([k, v])
    idx.append([])
    idx.append(["Worksheet", "Purpose"])
    sheet_notes = [
        ("Income Statement", "Every public native-cadence income-statement series."),
        ("Balance Sheet", "Every public balance-sheet series, including opening balances."),
        ("Ratios", "Native-cadence public ratios."),
        ("Operating Expense", "IS Opex decomposition plus recurring categories, additive components, settlement balances, and residual reconciliation."),
        ("Workforce", "Role-level count, compensation assumptions, resolved payroll expense, and engine total."),
        ("CAC - AUC", "Customer-acquisition AUC EOP / average and customer measures by native period."),
        ("Product Calculations", "Every native numeric product series surfaced by the run."),
        ("Fee Product Costs", "Fee revenue, Fee Product costs, and product Opex by product."),
        ("Fee Stream Quantities", "Stable observational quantity Series consumed by downstream calculations."),
        ("Cost Pools", "Resolved non-posting cost-pool Series."),
        ("All Series", "Catch-all inventory of numeric period Series surfaced by the public run."),
    ]
    for r in sheet_notes:
        idx.append(list(r))
    index_header_row = idx.max_row - len(sheet_notes)
    _style_header(idx, index_header_row, 2)
    idx.column_dimensions["A"].width = 28
    idx.column_dimensions["B"].width = 95
    idx.freeze_panes = "A4"

    bs = ((results.get("financials") or {}).get("bs") or {})
    is_ = ((results.get("financials") or {}).get("is") or {})
    rt = ((results.get("financials") or {}).get("ratios") or {})

    _write_wide_rows(wb.create_sheet("Income Statement"), cfg,
                     _series_rows(is_, "Income Statement", "$000s / engine period", n),
                     title="Income Statement · Calculation Audit", subtitle="All native-cadence public IS series.", n=n, ppy=ppy)
    _write_wide_rows(wb.create_sheet("Balance Sheet"), cfg,
                     _series_rows(bs, "Balance Sheet", "$000s EOP", n, include_open=True),
                     title="Balance Sheet · Calculation Audit", subtitle="Opening balance plus every native-cadence public BS series.", n=n, ppy=ppy, include_open=True)
    _write_wide_rows(wb.create_sheet("Ratios"), cfg,
                     _series_rows(rt, "Ratios", "% / public ratio units", n, fmt=_RATE_FMT),
                     title="Ratios · Calculation Audit", subtitle="Native-cadence ratios exactly as surfaced by the run.", n=n, ppy=ppy)

    _write_wide_rows(wb.create_sheet("Operating Expense"), cfg, _operating_expense_rows(cfg, results, n, ppy),
                     title="Operating Expense · Calculation Audit",
                     subtitle="Granular recurring and additive calculations. Residual line isolates Opex mechanics not represented by category/component rows.", n=n, ppy=ppy)
    _write_wide_rows(wb.create_sheet("Workforce"), cfg, _workforce_rows(cfg, results, n, ppy),
                     title="Workforce · Calculation Audit",
                     subtitle="Role-level headcount and payroll calculations, including resolved activation timing.", n=n, ppy=ppy)
    _write_wide_rows(wb.create_sheet("CAC - AUC"), cfg, _cac_rows(cfg, results, n, ppy),
                     title="Customer Acquisition / AUC · Calculation Audit",
                     subtitle="AUC period-end and canonical period-average paths plus customer-count measures.", n=n, ppy=ppy)
    _write_wide_rows(wb.create_sheet("Product Calculations"), cfg, _product_rows(results, n),
                     title="Product Calculations · Audit",
                     subtitle="Every native numeric product series surfaced by Foundry.", n=n, ppy=ppy)
    _write_wide_rows(wb.create_sheet("Fee Product Costs"), cfg, _fee_cost_rows(cfg, results, n, ppy),
                     title="Fee Product Costs · Audit",
                     subtitle="Product-level fee revenue, external Fee Product costs, and product operating expense.", n=n, ppy=ppy)
    _write_wide_rows(wb.create_sheet("Fee Stream Quantities"), cfg, _quantity_rows(cfg, results, n),
                     title="Fee Stream Quantities · Audit",
                     subtitle="Stable driver-quantity Series available to downstream model components.", n=n, ppy=ppy)
    _write_wide_rows(wb.create_sheet("Cost Pools"), cfg, _pool_rows(results, n),
                     title="Cost Pools · Audit",
                     subtitle="Resolved non-posting pricing/cost-recovery source Series.", n=n, ppy=ppy)
    _write_wide_rows(wb.create_sheet("All Series"), cfg, _all_series_rows(results, n),
                     title="All Public Run Series · Audit",
                     subtitle="Catch-all numeric Series inventory. Use subsystem sheets first; this sheet is the completeness backstop.", n=n, ppy=ppy)

    # Basic workbook-wide visual discipline: readable labels, consistent period widths.
    for ws in wb.worksheets:
        ws.sheet_view.showGridLines = False
        for row in ws.iter_rows():
            for cell in row:
                if cell.row > 2 and cell.column <= 4:
                    cell.alignment = Alignment(vertical="top", wrap_text=True)
    return wb
