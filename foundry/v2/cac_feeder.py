"""Customer-Acquisition AUC feeder (upstream of the fee engine).

Customer Acquisition is calculated on Foundry's canonical monthly grid.  Source assumptions may
be authored at Month / Quarter / Year cadence (or linked to another module-owned Series); CAC
resolves each operand to monthly economics first, evaluates the acquisition equation each month,
and only then aggregates to annual presentation.  The annual roll-forward is therefore a summary,
not the computational cadence.

The engine knows only a closed set of equations (Pool × Conversion, Spend ÷ CAC, FTE Count ×
Productivity, Explicit Customers).  Channel names are presentation-only and cross-module links use
stable Series IDs.
"""

from __future__ import annotations

import math


_FREQ = {"year": 1, "quarter": 4, "month": 12}
_FLOW_KEYS = {"pool", "spend", "per_fte", "comp_per_fte", "new_customers"}


def _grow(base, rate, year):
    """Legacy helper: annual stepped growth, retained for old scalar fields."""
    from .growth import growth_multiplier
    spec = {"rate": float(rate or 0.0), "period": "year",
            "method": "step", "anchor": "model_year"}
    return float(base or 0.0) * growth_multiplier(
        spec, current_period=int(year), start_period=1, ppy=1,
        base_position="period1")


def _period_width_months(period: str, *, engine_ppy: int = 12) -> int:
    p = str(period or "year").lower()
    if p == "model_period":
        if int(engine_ppy) not in (4, 12):
            raise ValueError(f"unsupported CAC model cadence periods_per_year={engine_ppy}")
        return 12 // int(engine_ppy)
    if p not in _FREQ:
        raise ValueError(f"unsupported CAC source cadence {p!r}")
    return 12 // _FREQ[p]


def _legacy_spec(owner, key, *, is_feed=False):
    """Translate legacy CAC scalar/growth vocabulary into an entered Series spec."""
    if is_feed:
        if key == "attrition_rate":
            return {"source": "entered", "trajectory": "flat",
                    "value": float((owner or {}).get("attrition_rate") or 0.0), "period": "year"}
        if key == "attrition_avg_ticket":
            v = (owner or {}).get("attrition_avg_ticket")
            return None if v is None else {"source": "entered", "trajectory": "flat", "value": float(v)}
        return None

    ch = owner or {}
    p = ch.get("params") or {}
    if key == "avg_auc_per_customer":
        base = float(ch.get("avg_auc_per_customer") or 0.0)
        g = float(ch.get("avg_auc_growth") or 0.0)
        if g:
            return {"source": "entered", "trajectory": "growth", "base": base,
                    "growth_spec": {"rate": g, "period": "year", "method": "step", "anchor": "model_year"}}
        return {"source": "entered", "trajectory": "flat", "value": base}
    if key == "new_customers":
        vals = list(p.get("new_customers_by_year") or [])
        # Historical ``new_customers_by_year`` returned zero beyond the supplied list.
        # Preserve that exact legacy extension semantic while resolving each supplied annual
        # flow onto the monthly causal grid.
        return {"source": "entered", "trajectory": "explicit", "cadence": "year",
                "values": vals, "extend": "zero", "resolution": "step"}
    growth_keys = {
        "pool": "pool_growth", "conversion_rate": "conversion_growth",
        "spend": "spend_growth", "cac": "cac_growth", "ftes": "ftes_growth",
        "per_fte": "per_fte_growth", "comp_per_fte": "comp_growth",
    }
    if key in growth_keys:
        base = float(p.get(key) or 0.0)
        g = float(p.get(growth_keys[key]) or 0.0)
        out = ({"source": "entered", "trajectory": "growth", "base": base,
                "growth_spec": {"rate": g, "period": "year", "method": "step", "anchor": "model_year"}}
               if g else {"source": "entered", "trajectory": "flat", "value": base})
        if key in _FLOW_KEYS:
            out["period"] = "year"
        return out
    if key == "cost_per_customer":
        if p.get(key) is None:
            return None
        return {"source": "entered", "trajectory": "flat", "value": float(p.get(key) or 0.0)}
    return None


def _spec_for(owner, key, *, is_feed=False):
    specs = (owner or {}).get("driver_specs") or {}
    if key in specs:
        return dict(specs.get(key) or {})
    return _legacy_spec(owner, key, is_feed=is_feed)


def _explicit_source_values(spec, months, *, engine_ppy=12):
    vals = list(spec.get("values") or [])
    extend = str(spec.get("extend") or "hold").lower()
    cad = str(spec.get("cadence") or "year").lower()
    width = _period_width_months(cad, engine_ppy=engine_ppy)
    out = []
    for mi in range(int(months)):
        idx = mi // width
        if idx < len(vals):
            v = vals[idx]
            if v is None:
                raise ValueError(f"explicit CAC series has a blank value at source period {idx + 1}")
            out.append(float(v))
        elif extend == "hold":
            out.append(float(vals[-1]) if vals else 0.0)
        elif extend == "zero":
            out.append(0.0)
        else:
            raise ValueError(f"explicit CAC series has no value for source period {idx + 1}")
    return out, width


def _resolve_operand_monthly(spec, months, semantic, *, assumptions=None, growth_context=None,
                             engine_ppy=12, default_value=0.0):
    """Resolve one CAC operand to the canonical monthly grid.

    ``semantic='flow'`` means the entered amount is a total for its natural/source period and is
    spread evenly across the constituent months.  ``level`` and ``share`` are repeated as levels.
    Cross-module links already arrive as monthly owner-resolved values and are never periodized a
    second time.
    """
    from .series import normalize_series_spec, resolve_series_spec, resolve_entered_series
    raw = dict(spec or {})
    if not raw:
        raw = {"source": "entered", "trajectory": "flat", "value": float(default_value or 0.0)}
    s = normalize_series_spec(raw, default_value=default_value)
    if s["source"] == "link":
        return [float(x or 0.0) for x in resolve_series_spec(
            s, assumptions or {}, int(months), 12, context=growth_context,
            default_value=default_value)]
    if s["source"] != "entered":
        raise ValueError("CAC operands may be entered or linked; derived operands are owned by CAC outputs")

    if s["trajectory"] == "explicit":
        arr, width = _explicit_source_values(raw, months, engine_ppy=engine_ppy)
        if semantic == "flow":
            return [v / float(width) for v in arr]
        return arr

    arr = [float(x or 0.0) for x in resolve_entered_series(
        s, int(months), 12, context=growth_context, default_value=default_value)]
    if semantic != "flow":
        return arr
    natural = str(raw.get("period") or "year").lower()
    width = _period_width_months(natural, engine_ppy=engine_ppy)
    return [v / float(width) for v in arr]


def _channel_operand_specs(ch):
    method = str((ch or {}).get("method") or "")
    if method == "pool_conversion":
        return {"pool": "flow", "conversion_rate": "share", "avg_auc_per_customer": "level"}
    if method == "spend_cac":
        return {"spend": "flow", "cac": "level", "avg_auc_per_customer": "level"}
    if method == "fte_productivity":
        return {"ftes": "level", "per_fte": "flow", "comp_per_fte": "flow",
                "avg_auc_per_customer": "level"}
    if method == "explicit":
        return {"new_customers": "flow", "spend": "flow", "avg_auc_per_customer": "level"}
    raise ValueError(f"unsupported customer-acquisition method {method!r}")


def _channel_monthly_operands(ch, months, *, assumptions=None, growth_context=None, engine_ppy=12):
    out = {}
    for key, semantic in _channel_operand_specs(ch).items():
        spec = _spec_for(ch, key)
        if spec is None:
            out[key] = [0.0] * int(months)
            continue
        out[key] = _resolve_operand_monthly(
            spec, months, semantic, assumptions=assumptions,
            growth_context=growth_context, engine_ppy=engine_ppy)
    # Optional pool-conversion audit spend.
    if str((ch or {}).get("method") or "") == "pool_conversion":
        cps = _spec_for(ch, "cost_per_customer")
        out["cost_per_customer"] = (_resolve_operand_monthly(
            cps, months, "level", assumptions=assumptions, growth_context=growth_context,
            engine_ppy=engine_ppy) if cps is not None else [0.0] * int(months))
    return out


def _channel_monthly(ch, months, *, assumptions=None, growth_context=None, engine_ppy=12):
    op = _channel_monthly_operands(ch, months, assumptions=assumptions,
                                   growth_context=growth_context, engine_ppy=engine_ppy)
    method = str((ch or {}).get("method") or "")
    rows = []
    for mi in range(int(months)):
        if method == "pool_conversion":
            nc = op["pool"][mi] * op["conversion_rate"][mi]
            spend = nc * op["cost_per_customer"][mi] if op["cost_per_customer"][mi] else 0.0
        elif method == "spend_cac":
            spend = op["spend"][mi]
            c = op["cac"][mi]
            nc = spend / c if c > 0 else 0.0
        elif method == "fte_productivity":
            nc = op["ftes"][mi] * op["per_fte"][mi]
            spend = op["ftes"][mi] * op["comp_per_fte"][mi]
        elif method == "explicit":
            nc = op["new_customers"][mi]
            spend = op["spend"][mi]
        else:
            raise ValueError(f"unsupported customer-acquisition method {method!r}")
        ticket = op["avg_auc_per_customer"][mi]
        rows.append({"month": mi + 1, "new_customers": nc, "new_auc": nc * ticket,
                     "spend": spend, "cac": (spend / nc if nc > 0 else None),
                     "avg_auc_per_customer": ticket,
                     "operands": {k: v[mi] for k, v in op.items()}})
    return rows


def _annual_slice(rows, year):
    lo, hi = (int(year) - 1) * 12, int(year) * 12
    return rows[lo:hi]


def _series_context_args(series_context):
    sc = series_context or {}
    q = int(sc.get("Q") or 12)
    ppy = int(sc.get("ppy") or 12)
    years = max(int(math.ceil(q / float(ppy))), 1)
    return years * 12, sc.get("assumptions") or {}, sc.get("growth_context"), ppy


def channel_new_customers(ch, year, series_context=None):
    months, assumptions, gctx, ppy = _series_context_args(series_context)
    months = max(months, int(year) * 12)
    rows = _channel_monthly(ch, months, assumptions=assumptions, growth_context=gctx, engine_ppy=ppy)
    return sum(float(r.get("new_customers") or 0.0) for r in _annual_slice(rows, year))


def channel_avg_auc(ch, year, series_context=None):
    months, assumptions, gctx, ppy = _series_context_args(series_context)
    months = max(months, int(year) * 12)
    op = _channel_monthly_operands(ch, months, assumptions=assumptions, growth_context=gctx, engine_ppy=ppy)
    vals = _annual_slice(op.get("avg_auc_per_customer") or [], year)
    return sum(vals) / len(vals) if vals else 0.0


def channel_spend(ch, year, series_context=None):
    months, assumptions, gctx, ppy = _series_context_args(series_context)
    months = max(months, int(year) * 12)
    rows = _channel_monthly(ch, months, assumptions=assumptions, growth_context=gctx, engine_ppy=ppy)
    return sum(float(r.get("spend") or 0.0) for r in _annual_slice(rows, year))


def resolve_driver_spec(spec, year, *, assumptions=None, Q=None, ppy=4, growth_context=None):
    """Backward-compatible annual reduction helper for audit callers."""
    from .series import resolve_series_value_for_year
    return resolve_series_value_for_year(
        spec, int(year), assumptions or {}, n_periods=Q, ppy=int(ppy),
        context=growth_context, default_value=0.0)


def _driver(owner, key, year, *, legacy_base=0.0, legacy_growth=0.0, series_context=None):
    specs = (owner or {}).get("driver_specs") or {}
    if key in specs:
        sc = series_context or {}
        return resolve_driver_spec(specs.get(key), year,
                                   assumptions=sc.get("assumptions"), Q=sc.get("Q"),
                                   ppy=sc.get("ppy", 4), growth_context=sc.get("growth_context"))
    return _grow(legacy_base, legacy_growth, year)


def _channel_param(ch, key, year, growth_key=None, series_context=None):
    # Annual helper retained for workbook/backward API.  The CAC engine itself does not use it.
    p = (ch or {}).get("params") or {}
    return _driver(ch, key, year, legacy_base=p.get(key),
                   legacy_growth=p.get(growth_key or (key + "_growth")),
                   series_context=series_context)


def _attrition_period(feed):
    spec = _spec_for(feed, "attrition_rate", is_feed=True) or {}
    from .series import normalize_series_spec
    s = normalize_series_spec(spec, default_value=0.0)
    if s.get("trajectory") == "explicit":
        return str(spec.get("cadence") or "year").lower()
    return str(spec.get("period") or "year").lower()


def _attrition_monthly_rate_path(feed, months, *, assumptions=None, growth_context=None, engine_ppy=12):
    spec = _spec_for(feed, "attrition_rate", is_feed=True)
    return _resolve_operand_monthly(spec, months, "share", assumptions=assumptions,
                                    growth_context=growth_context, engine_ppy=engine_ppy)


def cac_auc_rollforward(cac_cfg, Q, ppy=4, *, assumptions=None, growth_context=None):
    """Canonical-monthly customer/AUC calculation with annual summary presentation.

    Month/Quarter/Year source cadence belongs to each operand.  Flow operands are spread across
    the months in their authored source period; levels/rates hold as levels.  Cross-module links
    are resolved directly to the same monthly grid.  Acquisition equations are evaluated monthly,
    so sub-year variation is preserved instead of being reduced to an annual average first.

    Existing-book attrition is applied at the end of each authored attrition source period to the
    book that existed at the beginning of that source period.  Thus an annual 10% attrition input
    preserves the historical "10% of beginning-year book" semantic, while quarterly/monthly inputs
    can express genuinely sub-year churn without being averaged into a year.
    """
    ppy = int(ppy)
    if ppy not in (4, 12):
        raise ValueError(f"unsupported CAC cadence periods_per_year={ppy}")
    years = max(int(math.ceil(int(Q) / float(ppy))), 1)
    months = years * 12
    channels = list((cac_cfg or {}).get("channels") or [])
    channel_monthly = [_channel_monthly(ch, months, assumptions=assumptions or {},
                                        growth_context=growth_context, engine_ppy=ppy)
                       for ch in channels]

    attr_rates = _attrition_monthly_rate_path(cac_cfg or {}, months, assumptions=assumptions or {},
                                               growth_context=growth_context, engine_ppy=ppy)
    attr_period = _attrition_period(cac_cfg or {})
    attr_width = _period_width_months(attr_period, engine_ppy=ppy)
    ticket_spec = _spec_for(cac_cfg or {}, "attrition_avg_ticket", is_feed=True)
    ticket_path = (_resolve_operand_monthly(ticket_spec, months, "level", assumptions=assumptions or {},
                                            growth_context=growth_context, engine_ppy=ppy)
                   if ticket_spec is not None else None)

    beg_auc = float((cac_cfg or {}).get("beginning_auc") or 0.0)
    beg_cust = float((cac_cfg or {}).get("beginning_customers") or 0.0)
    if not math.isfinite(beg_auc) or beg_auc < 0.0:
        raise ValueError("CAC opening AUC must be a finite non-negative amount")
    if not math.isfinite(beg_cust) or beg_cust < 0.0:
        raise ValueError("CAC opening customers must be a finite non-negative count")
    source_open_auc, source_open_cust = beg_auc, beg_cust
    monthly = []
    auc_end_by_month, customer_end_by_month = [], []

    for mi in range(months):
        if mi % attr_width == 0:
            source_open_auc, source_open_cust = beg_auc, beg_cust
        ch_rows = [rows[mi] for rows in channel_monthly]
        new_cust = sum(float(r.get("new_customers") or 0.0) for r in ch_rows)
        new_auc = sum(float(r.get("new_auc") or 0.0) for r in ch_rows)
        event = ((mi + 1) % attr_width == 0)
        rate = float(attr_rates[mi] or 0.0) if event else 0.0
        if rate < 0.0 or rate > 1.0:
            raise ValueError("CAC attrition rate must be between 0% and 100% per source period")
        cust_lost = source_open_cust * rate if event else 0.0
        avg_ticket = (float(ticket_path[mi]) if ticket_path is not None
                      else ((source_open_auc / source_open_cust) if source_open_cust > 0 else 0.0))
        auc_lost = cust_lost * avg_ticket
        end_cust = beg_cust + new_cust - cust_lost
        end_auc = beg_auc + new_auc - auc_lost
        total_spend = sum(float(r.get("spend") or 0.0) for r in ch_rows)
        monthly.append({
            "month": mi + 1, "year": mi // 12 + 1, "month_in_year": mi % 12 + 1,
            "beg_auc": beg_auc, "new_auc": new_auc, "auc_lost": auc_lost, "end_auc": end_auc,
            "beg_cust": beg_cust, "new_cust": new_cust, "cust_lost": cust_lost, "end_cust": end_cust,
            "attrition_event": event, "attrition_rate": rate, "attrition_period": attr_period,
            "attrition_basis_customers": source_open_cust if event else None,
            "attrition_basis_auc": source_open_auc if event else None,
            "total_spend": total_spend,
            "blended_cac": (total_spend / new_cust if new_cust > 0 else None),
            "channels": ch_rows,
        })
        beg_auc, beg_cust = end_auc, end_cust
        auc_end_by_month.append(end_auc)
        customer_end_by_month.append(end_cust)

    annual, year_end_auc, year_end_customers = [], [], []
    for y in range(1, years + 1):
        rows = monthly[(y - 1) * 12:y * 12]
        ch_detail = []
        for ci, ch in enumerate(channels):
            cr = [r["channels"][ci] for r in rows]
            nc = sum(float(x.get("new_customers") or 0.0) for x in cr)
            na = sum(float(x.get("new_auc") or 0.0) for x in cr)
            sp = sum(float(x.get("spend") or 0.0) for x in cr)
            ch_detail.append({"name": ch.get("name"), "new_customers": nc, "new_auc": na,
                              "spend": sp, "cac": (sp / nc if nc > 0 else None)})
        attr_events = [float(r.get("attrition_rate") or 0.0) for r in rows if r.get("attrition_event")]
        eff_attr = 1.0 - math.prod(1.0 - x for x in attr_events) if attr_events else 0.0
        total_spend = sum(float(r.get("total_spend") or 0.0) for r in rows)
        new_cust = sum(float(r.get("new_cust") or 0.0) for r in rows)
        rec = {
            "year": y,
            "beg_auc": rows[0]["beg_auc"], "new_auc": sum(r["new_auc"] for r in rows),
            "auc_lost": sum(r["auc_lost"] for r in rows), "end_auc": rows[-1]["end_auc"],
            "beg_cust": rows[0]["beg_cust"], "new_cust": new_cust,
            "cust_lost": sum(r["cust_lost"] for r in rows), "end_cust": rows[-1]["end_cust"],
            "attrition_rate": eff_attr, "attrition_period": attr_period,
            "total_spend": total_spend,
            "blended_cac": (total_spend / new_cust if new_cust > 0 else None),
            "channels": ch_detail,
        }
        annual.append(rec); year_end_auc.append(rec["end_auc"]); year_end_customers.append(rec["end_cust"])

    if ppy == 12:
        auc_levels_q = list(auc_end_by_month[:int(Q)])
    else:
        auc_levels_q = [auc_end_by_month[(q + 1) * 3 - 1] for q in range(int(Q))]

    from .balance_measures import native_balance_measure_series, monthly_balance_measure_series
    customer_end_by_period = native_balance_measure_series(
        float((cac_cfg or {}).get("beginning_customers") or 0.0),
        customer_end_by_month, int(Q), ppy, "period_end")
    customer_average_by_period = native_balance_measure_series(
        float((cac_cfg or {}).get("beginning_customers") or 0.0),
        customer_end_by_month, int(Q), ppy, "period_average")
    if ppy == 12:
        customer_level_by_period = list(customer_end_by_month[:int(Q)])
    else:
        customer_level_by_period = [
            sum(customer_end_by_month[q * 3:(q + 1) * 3]) / 3.0 for q in range(int(Q))]
    # Canonical monthly forms of every customer-count measure are retained for downstream
    # authoring/audit surfaces.  Consumers should not have to reconstruct these semantics in
    # the browser from a prior run's EOP path.
    customer_average_by_month = monthly_balance_measure_series(
        float((cac_cfg or {}).get("beginning_customers") or 0.0), customer_end_by_month, "period_average")
    customer_annual_count_by_month = [
        float(year_end_customers[min(len(year_end_customers) - 1, i // 12)] or 0.0)
        for i in range(len(customer_end_by_month))
    ] if year_end_customers else [0.0] * len(customer_end_by_month)
    customer_annual_count_by_period = [
        float(year_end_customers[min(len(year_end_customers) - 1, i // ppy)] or 0.0)
        for i in range(int(Q))] if year_end_customers else [0.0] * int(Q)

    derived_series = {}
    for ci, ch in enumerate(channels):
        ids = (ch or {}).get("derived_series_ids") or {}
        for semantic, field in (("new_customers", "new_customers"), ("new_auc", "new_auc")):
            sid = str(ids.get(semantic) or "").strip()
            if not sid:
                continue
            canonical = [float(channel_monthly[ci][mi].get(field) or 0.0) for mi in range(months)]
            if ppy == 12:
                native = canonical[:int(Q)]
            else:
                native = [sum(canonical[q * 3:(q + 1) * 3]) for q in range(int(Q))]
            derived_series[sid] = {
                "source": "derived", "series_id": sid, "owner_module": "customer_acquisition",
                "semantic_type": semantic, "cadence": "model_period", "values": native,
                "canonical_cadence": "month", "canonical_values": canonical,
                "derived": {"kind": f"cac.{(ch or {}).get('method')}.{semantic}"},
            }
    feed_sid = str((cac_cfg or {}).get("series_id") or "").strip()
    if feed_sid:
        derived_series[feed_sid] = {
            "source": "derived", "series_id": feed_sid, "owner_module": "customer_acquisition",
            "semantic_type": "auc_end", "cadence": "model_period", "values": list(auc_levels_q),
            "canonical_cadence": "month", "canonical_values": list(auc_end_by_month),
            "derived": {"kind": "cac.customer_auc_rollforward"},
        }
    count_sid = str((cac_cfg or {}).get("customer_count_series_id") or "").strip()
    if count_sid:
        derived_series[count_sid] = {
            "source": "derived", "series_id": count_sid, "owner_module": "customer_acquisition",
            "semantic_type": "customer_count_level", "cadence": "model_period",
            "values": list(customer_level_by_period), "canonical_cadence": "month",
            "canonical_values": list(customer_end_by_month),
            "available_measures": ["annual_count", "period_end", "period_average"],
            "derived": {"kind": "cac.customer_count_rollforward"},
        }

    return {"auc_end_by_month": auc_end_by_month,
            "auc_end_by_period": auc_levels_q, "auc_levels_q": auc_levels_q,
            "year_end_auc": year_end_auc,
            "customer_end_by_month": customer_end_by_month,
            "customer_end_by_period": customer_end_by_period,
            "customer_level_by_period": customer_level_by_period,
            "customer_average_by_month": customer_average_by_month,
            "customer_average_by_period": customer_average_by_period,
            "customer_annual_count_by_month": customer_annual_count_by_month,
            "customer_annual_count_by_period": customer_annual_count_by_period,
            "year_end_customers": year_end_customers,
            "monthly": monthly, "annual": annual, "derived_series": derived_series,
            "calculation_cadence": "month"}
def cac_customer_count_catalog(assumptions):
    """Catalog CAC-owned customer-count Series by stable Series ID."""
    out = []
    for name, raw in ((assumptions or {}).get("cac_feeds") or {}).items():
        feed = raw or {}
        sid = str(feed.get("customer_count_series_id") or "").strip()
        if not sid:
            continue
        out.append({"series_id": sid, "feed": str(name or sid),
                    "unit_semantic": "customer_count_level", "canonical_cadence": "month"})
    ids = [x["series_id"] for x in out]
    if len(ids) != len(set(ids)):
        raise ValueError("CAC customer_count_series_id values must be unique")
    return out


def cac_customer_count_series_map(assumptions, Q, ppy=4, *, growth_context=None):
    """Resolve each CAC feed's customer-book level for downstream Account Fee streams."""
    out = {}
    for meta in cac_customer_count_catalog(assumptions):
        feed = ((assumptions or {}).get("cac_feeds") or {}).get(meta["feed"]) or {}
        r = cac_auc_rollforward(feed, Q, ppy, assumptions=assumptions, growth_context=growth_context)
        out[meta["series_id"]] = [float(x or 0.0) for x in r.get("customer_level_by_period") or []]
    return out


CUSTOMER_COUNT_MEASURES = {"annual_count", "period_end", "period_average"}


def normalize_customer_count_measure(value, *, default="period_end"):
    """Normalize the explicit semantic consumed by an Account Fee stream.

    ``period_end`` is the r68-compatible default so saved streams retain their exact outputs.
    New authoring surfaces always write a measure explicitly.
    """
    measure = str(value or default).strip().lower()
    if measure not in CUSTOMER_COUNT_MEASURES:
        raise ValueError("CAC customer-count measure must be annual_count, period_end, or period_average")
    return measure


def cac_customer_count_measure_series_map(assumptions, Q, ppy=4, *, growth_context=None):
    """Resolve every CAC customer-count measure by stable Series ID.

    The returned shape is ``{series_id: {measure: [native-period values]}}``.  This keeps the
    CAC feed as the sole owner of the customer-book forecast while forcing downstream Account
    Fee streams to state which customer semantic they consume.
    """
    out = {}
    for meta in cac_customer_count_catalog(assumptions):
        feed = ((assumptions or {}).get("cac_feeds") or {}).get(meta["feed"]) or {}
        r = cac_auc_rollforward(feed, Q, ppy, assumptions=assumptions, growth_context=growth_context)
        out[meta["series_id"]] = {
            "annual_count": [float(x or 0.0) for x in r.get("customer_annual_count_by_period") or []],
            "period_end": [float(x or 0.0) for x in r.get("customer_level_by_period") or []],
            "period_average": [float(x or 0.0) for x in r.get("customer_average_by_period") or []],
        }
    return out


def cac_managed_notional(cac_cfg, Q, ppy=4, *, assumptions=None, growth_context=None):
    """Package a CAC-owned AUC path for the Fee Product engine.

    The managed-notional consumer needs both the true opening stock and the canonical monthly
    period-end path.  Retaining those observations lets downstream Fee Products derive period-
    average exposure without reconstructing a quarter from two quarter-end points.
    """
    r = cac_auc_rollforward(cac_cfg, Q, ppy, assumptions=assumptions, growth_context=growth_context)
    return {
        "day1": float((cac_cfg or {}).get("beginning_auc") or 0.0),
        "trajectory": "explicit_levels",
        "schedule": {str(q + 1): r["auc_end_by_period"][q] for q in range(int(Q))},
        "canonical_monthly_end": list(r.get("auc_end_by_month") or []),
    }
