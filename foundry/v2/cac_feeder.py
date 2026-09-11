"""Customer-Acquisition AUC feeder (upstream of the fee engine).

Foundry models causal equations, not a source workbook's grid. A feed contains any number of
user-named acquisition channels; the engine knows only a small closed set of acquisition
equations (Pool × Conversion, Spend ÷ CAC, FTE Count × Productivity, Explicit Customers).
Channel names are presentation-only.

Every equation operand may use the generic Foundry Series contract: enter a Flat / Growth /
Explicit trajectory, or Link to a compatible series owned elsewhere. Links use stable series IDs,
so CAC may consume (for example) Operating Expense spend or Workforce Count without duplicating
the source trajectory. Source cadence is independent of projection cadence.

The annual customer/AUC roll-forward is a domain equation and audit view, not an authoring
spreadsheet. Its resolved AUC path is emitted as managed-notional explicit levels for downstream
Fee Products. Unsupported methods/links and circular dependencies fail closed.
"""


def _grow(base, rate, year):
    """Compound a base by an annual growth rate. year is 1-indexed (year 1 => base)."""
    # CAC remains explicitly annual and stepped by model year. Route that existing
    # semantic through the shared resolver so annual growth has one canonical meaning
    # across Foundry without changing any CAC economics or UI.
    from .growth import growth_multiplier
    spec = {"rate": float(rate or 0.0), "period": "year",
            "method": "step", "anchor": "model_year"}
    return float(base or 0.0) * growth_multiplier(
        spec, current_period=int(year), start_period=1, ppy=1,
        base_position="period1")



def resolve_driver_spec(spec, year, *, assumptions=None, Q=None, ppy=4, growth_context=None):
    """Resolve one generic Foundry-series operand at an annual CAC equation point.

    Legacy ``mode`` specs remain valid.  New specs may instead link to a compatible
    Foundry series owned by another module; the link declares how the native series is
    reduced to an annual operand (sum/average/end/start).
    """
    if spec is None:
        return None
    from .series import resolve_series_value_for_year
    return resolve_series_value_for_year(
        spec, int(year), assumptions or {}, n_periods=Q, ppy=int(ppy),
        context=growth_context, default_value=0.0)


def _driver(owner, key, year, *, legacy_base=0.0, legacy_growth=0.0, series_context=None):
    """Resolve a named operand from ``owner.driver_specs`` or legacy scalar+growth fields."""
    specs = (owner or {}).get("driver_specs") or {}
    if key in specs:
        sc = series_context or {}
        return resolve_driver_spec(specs.get(key), year,
                                   assumptions=sc.get("assumptions"), Q=sc.get("Q"),
                                   ppy=sc.get("ppy", 4), growth_context=sc.get("growth_context"))
    return _grow(legacy_base, legacy_growth, year)


def _channel_param(ch, key, year, growth_key=None, series_context=None):
    p = (ch or {}).get("params") or {}
    return _driver(ch, key, year, legacy_base=p.get(key),
                   legacy_growth=p.get(growth_key or (key + "_growth")),
                   series_context=series_context)


def channel_new_customers(ch, year, series_context=None):
    """New customers acquired by one user-named channel in a model year.

    The engine knows acquisition equations, never channel names.  Every equation operand
    may be entered locally or linked to a compatible Foundry series owned elsewhere.
    """
    if not ch:
        return 0.0
    method = ch.get("method")
    p = ch.get("params") or {}
    specs = ch.get("driver_specs") or {}
    if method == "pool_conversion":
        pool = _channel_param(ch, "pool", year, "pool_growth", series_context)
        conv = _channel_param(ch, "conversion_rate", year, "conversion_growth", series_context)
        return pool * conv
    if method == "spend_cac":
        spend = _channel_param(ch, "spend", year, "spend_growth", series_context)
        cac = _channel_param(ch, "cac", year, "cac_growth", series_context)
        return spend / cac if cac > 0 else 0.0
    if method == "fte_productivity":
        ftes = _channel_param(ch, "ftes", year, "ftes_growth", series_context)
        per = _channel_param(ch, "per_fte", year, "per_fte_growth", series_context)
        return ftes * per
    if method == "explicit":
        if "new_customers" in specs:
            return float(_driver(ch, "new_customers", year, series_context=series_context) or 0.0)
        arr = p.get("new_customers_by_year") or []
        i = year - 1
        return float(arr[i]) if 0 <= i < len(arr) else 0.0
    raise ValueError(f"unsupported customer-acquisition method {method!r}")


def channel_avg_auc(ch, year, series_context=None):
    """Average AUC per customer acquired by this channel in the given year."""
    if not ch:
        return 0.0
    return _driver(ch, "avg_auc_per_customer", year,
                   legacy_base=ch.get("avg_auc_per_customer"),
                   legacy_growth=ch.get("avg_auc_growth"), series_context=series_context)


def channel_spend(ch, year, series_context=None):
    """Acquisition spend attributed to this channel in the given year, for CAC audit."""
    if not ch:
        return 0.0
    method = ch.get("method")
    p = ch.get("params") or {}
    specs = ch.get("driver_specs") or {}
    if method == "spend_cac":
        return _channel_param(ch, "spend", year, "spend_growth", series_context)
    if method == "fte_productivity":
        ftes = _channel_param(ch, "ftes", year, "ftes_growth", series_context)
        comp = _channel_param(ch, "comp_per_fte", year, "comp_growth", series_context)
        return ftes * comp
    if method == "pool_conversion":
        cpc = (_driver(ch, "cost_per_customer", year,
                       legacy_base=p.get("cost_per_customer"), legacy_growth=0.0,
                       series_context=series_context)
               if ("cost_per_customer" in specs or p.get("cost_per_customer") is not None) else 0.0)
        return channel_new_customers(ch, year, series_context) * cpc if cpc else 0.0
    if method == "explicit":
        if "spend" in specs:
            return float(_driver(ch, "spend", year, series_context=series_context) or 0.0)
        return float(p.get("spend") or 0.0)
    raise ValueError(f"unsupported customer-acquisition method {method!r}")


def cac_auc_rollforward(cac_cfg, Q, ppy=4, *, assumptions=None, growth_context=None):
    """Annual customer/AUC roll-forward over ceil(Q/ppy) years.

    AUC is always resolved first on Foundry's canonical monthly grid, then sampled to the
    selected engine cadence for native balance consumers.  This preserves the intra-year
    exposure path in quarterly models instead of manufacturing it from quarter-end points.
    The native-cadence series remains available for existing downstream consumers, while
    ``auc_end_by_month`` is the canonical balance path for cadence-sensitive calculations.

    cac_cfg = {
      channels: [ {name, method, params, avg_auc_per_customer, avg_auc_growth}, ... ],
      attrition_rate: r,                 # fraction of existing BOOK (customers) lost per year
      attrition_avg_ticket: $ | None,    # override; default = beginning AUC / beginning customers
      beginning_auc: $,                  # usually 0 (no Day-1 pre-commitment)
      beginning_customers: n,            # usually 0
      intra_year_shape: "linear"|"stepped",  # how a year's net change spreads across its 4 quarters
    }

    Returns {
      auc_end_by_month: [ ... 12 * model years ... ], # canonical monthly period-end AUC
      auc_end_by_period: [ ... len Q ... ],           # native engine-cadence period-end AUC
      auc_levels_q: [ ... len Q ... ],                # legacy alias retained for compatibility
      year_end_auc: [ ... per year ... ],
      annual: [ per-year records with channel detail, CAC, attrition ],
    }
    """
    channels = (cac_cfg or {}).get("channels") or []
    series_context = {"assumptions": assumptions or {}, "Q": int(Q), "ppy": int(ppy),
                      "growth_context": growth_context}
    legacy_attr = float((cac_cfg or {}).get("attrition_rate") or 0.0)
    legacy_ticket_override = (cac_cfg or {}).get("attrition_avg_ticket")
    beg_auc = float((cac_cfg or {}).get("beginning_auc") or 0.0)
    beg_cust = float((cac_cfg or {}).get("beginning_customers") or 0.0)
    shape = (cac_cfg or {}).get("intra_year_shape") or "linear"
    years = -(-int(Q) // ppy)  # ceil (periods/year = ppy)

    annual = []
    year_end_auc = []
    for y in range(1, years + 1):
        new_cust = 0.0
        new_auc = 0.0
        ch_detail = []
        for ch in channels:
            nc = channel_new_customers(ch, y, series_context)
            na = nc * channel_avg_auc(ch, y, series_context)
            sp = channel_spend(ch, y, series_context)
            new_cust += nc
            new_auc += na
            ch_detail.append({
                "name": ch.get("name"), "new_customers": nc, "new_auc": na,
                "spend": sp, "cac": (sp / nc if nc > 0 else None),
            })
        # Attrition on the existing book (beginning), not on this year's new adds.
        # Attrition itself may be an explicit annual source-model driver.
        attr = _driver(cac_cfg or {}, "attrition_rate", y, legacy_base=legacy_attr, legacy_growth=0.0, series_context=series_context)
        cust_lost = beg_cust * attr
        _ticket_specs = ((cac_cfg or {}).get("driver_specs") or {})
        if "attrition_avg_ticket" in _ticket_specs:
            avg_ticket = float(resolve_driver_spec(_ticket_specs.get("attrition_avg_ticket"), y, assumptions=assumptions, Q=Q, ppy=ppy, growth_context=growth_context) or 0.0)
        elif legacy_ticket_override is not None:
            avg_ticket = float(legacy_ticket_override)
        else:
            avg_ticket = (beg_auc / beg_cust) if beg_cust > 0 else 0.0
        auc_lost = cust_lost * avg_ticket
        end_cust = beg_cust + new_cust - cust_lost
        end_auc = beg_auc + new_auc - auc_lost
        total_spend = sum(c["spend"] for c in ch_detail)
        annual.append({
            "year": y,
            "beg_auc": beg_auc, "new_auc": new_auc, "auc_lost": auc_lost, "end_auc": end_auc,
            "beg_cust": beg_cust, "new_cust": new_cust, "cust_lost": cust_lost, "end_cust": end_cust,
            "attrition_rate": attr,
            "total_spend": total_spend,
            "blended_cac": (total_spend / new_cust if new_cust > 0 else None),
            "channels": ch_detail,
        })
        year_end_auc.append(end_auc)
        beg_auc, beg_cust = end_auc, end_cust

    # Annual ending levels -> canonical MONTHLY ABSOLUTE levels first.  The canonical grid is
    # deliberately independent of presentation/engine cadence.  Quarterly models therefore
    # retain M1/M2/M3 information and only sample M3/M6/M9/M12 for native quarter-end balances.
    # A downstream flow based on monthly AUC can consume/aggregate ``auc_end_by_month`` instead
    # of incorrectly applying a quarterly rate to the quarter-end stock.
    auc_end_by_month = [0.0] * (years * 12)
    prev_end = float((cac_cfg or {}).get("beginning_auc") or 0.0)
    for y in range(1, years + 1):
        ye = year_end_auc[y - 1]
        for mi in range(1, 13):
            m = (y - 1) * 12 + mi
            if shape == "stepped":
                auc_end_by_month[m - 1] = ye
            else:  # linear: ramp from prior year-end to this year-end across 12 canonical months
                auc_end_by_month[m - 1] = prev_end + (ye - prev_end) * mi / 12.0
        prev_end = ye

    if int(ppy) == 12:
        auc_levels_q = list(auc_end_by_month[:int(Q)])
    elif int(ppy) == 4:
        # Q1/Q2/Q3/Q4 period-end balances are canonical M3/M6/M9/M12.
        auc_levels_q = [auc_end_by_month[(q + 1) * 3 - 1] for q in range(int(Q))]
    else:
        raise ValueError(f"unsupported CAC cadence periods_per_year={ppy}")

    # Materialize module-owned Derived Series metadata.  The Series layer never evaluates
    # these equations; CAC owns the closed acquisition/roll-forward equations above and
    # publishes their resolved values with stable IDs when the authoring layer supplied them.
    derived_series = {}
    for ci, ch in enumerate(channels):
        ids = (ch or {}).get("derived_series_ids") or {}
        for semantic, field in (("new_customers", "new_customers"), ("new_auc", "new_auc")):
            sid = str(ids.get(semantic) or "").strip()
            if not sid:
                continue
            vals = [float((yr.get("channels") or [])[ci].get(field) or 0.0) for yr in annual]
            derived_series[sid] = {
                "source": "derived", "series_id": sid, "owner_module": "customer_acquisition",
                "semantic_type": semantic, "cadence": "year", "values": vals,
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

    return {"auc_end_by_month": auc_end_by_month,
            "auc_end_by_period": auc_levels_q, "auc_levels_q": auc_levels_q,
            "year_end_auc": year_end_auc, "annual": annual, "derived_series": derived_series}


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
