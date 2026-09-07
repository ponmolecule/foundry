"""Customer-Acquisition AUC Feeder (upstream of the fee engine).

Computes a bottom-up, customer-driven AUC roll-forward and emits it as an
`explicit_levels` managed_notional (absolute per-period levels) that the fee engine's
Grand Unified Theory consumes — so every fee stream inherits a driver traceable to
marketing/BD spend and productivity.

ARCHITECTURE (per FOUNDRY_CAC_AUC_FEEDER_SPEC.md): this module sits UPSTREAM of the GUT and
does NOT live inside it. It produces an AUC schedule; the GUT consumes that schedule. The seam
is `managed_notional` with trajectory `explicit_levels` (absolute levels, NOT the additive
`explicit_schedule`). Verified in-session: feeding a feeder's levels into the additive socket
inflates AUC cumulatively — hence the dedicated `explicit_levels` socket, which this module
targets.

ANTI-SPRAWL DESIGN (mirrors the GUT's shapes-not-products): the feeder knows a small closed set
of acquisition METHODS, not a fixed list of named channels. A channel is a user-named bundle:
{name, method, params, avg_auc_per_customer}. New channel types are new configurations, not new
code — exactly as new fee businesses are new bundles of stream shapes.

Acquisition methods (closed, extensible set):
  pool_conversion : new_customers = pool x conversion_rate
  spend_cac       : new_customers = spend / CAC
  fte_productivity: new_customers = FTEs x new_accounts_per_FTE
  explicit        : new_customers = an explicit customer schedule

Channel names are presentation only.  Each economic driver can use the generic ``driver_specs``
contract (flat / growth / explicit annual schedule), so a source model with one annual column or
seven annual columns is configuration, not a new channel type.

ROLL-FORWARD (annual source states; resolved to the engine's selected cadence at the end):
  Beginning AUC (0 in Year 1; prior-year ending thereafter)
  + New AUC   (sum over channels: new_customers x avg_auc_per_customer)
  - AUC lost to attrition (customers_lost x avg ticket of existing book)
  = Ending AUC   -> feeds managed_notional.explicit_levels

All functions are pure (config -> series).  ``engine_q_a`` consumes named feeds through
``managed_notional_source``; ``run_q`` also surfaces the annual roll-forward as an audit view.
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



_VALID_DRIVER_MODES = {"flat", "growth", "explicit"}
_VALID_DRIVER_CADENCES = {"year"}

def resolve_driver_spec(spec, year):
    """Resolve one generic customer-base driver at an annual source point.

    New authoring is opt-in and versioned by presence of ``driver_specs``.  Legacy scalar
    fields + ``*_growth`` retain their exact historical meaning when no spec is present.

    Supported shapes today:
      flat     {mode: flat, value: x}
      growth   {mode: growth, base: x, growth_spec: {...}}
      explicit {mode: explicit, cadence: year, values: [...], extend: hold|zero|error}

    ``cadence`` is explicit in the schema even though the current customer-base roll-forward
    consumes annual source states.  That keeps the authoring contract extensible to future
    monthly/quarterly source models without baking engagement-specific year counts into it.
    """
    if spec is None:
        return None
    if not isinstance(spec, dict):
        raise ValueError("customer-base driver spec must be an object")
    mode = str(spec.get("mode") or "flat").lower()
    if mode not in _VALID_DRIVER_MODES:
        raise ValueError(f"unsupported customer-base driver mode {mode!r}")
    cadence = str(spec.get("cadence") or "year").lower()
    if cadence not in _VALID_DRIVER_CADENCES:
        raise ValueError(f"unsupported customer-base driver cadence {cadence!r}")
    y = int(year)
    if y < 1:
        raise ValueError("customer-base driver year must be >= 1")

    if mode == "flat":
        return float(spec.get("value") or 0.0)

    if mode == "growth":
        from .growth import growth_multiplier
        base = float(spec.get("base") or 0.0)
        gs = spec.get("growth_spec") or {"rate": 0.0, "period": "year",
                                         "method": "step", "anchor": "model_year"}
        return base * growth_multiplier(gs, current_period=y, start_period=1, ppy=1,
                                        base_position="period1")

    vals = spec.get("values") or []
    if not isinstance(vals, (list, tuple)):
        raise ValueError("explicit customer-base driver values must be a list")
    i = y - 1
    if i < len(vals):
        v = vals[i]
        if v is None:
            raise ValueError(f"explicit customer-base driver has a blank value in year {y}")
        return float(v)
    extend = str(spec.get("extend") or "hold").lower()
    if extend == "hold":
        return float(vals[-1]) if vals else 0.0
    if extend == "zero":
        return 0.0
    if extend == "error":
        raise ValueError(f"explicit customer-base driver has no value for year {y}")
    raise ValueError(f"unsupported explicit driver extension {extend!r}")


def _driver(owner, key, year, *, legacy_base=0.0, legacy_growth=0.0):
    """Resolve a named driver from ``owner.driver_specs`` or legacy scalar+growth fields."""
    specs = (owner or {}).get("driver_specs") or {}
    if key in specs:
        return resolve_driver_spec(specs.get(key), year)
    return _grow(legacy_base, legacy_growth, year)


def _channel_param(ch, key, year, growth_key=None):
    p = (ch or {}).get("params") or {}
    return _driver(ch, key, year, legacy_base=p.get(key),
                   legacy_growth=p.get(growth_key or (key + "_growth")))

def channel_new_customers(ch, year):
    """New customers acquired by one channel in a given year (1-indexed). Method-dispatched.

    Channel *names* are never interpreted by the engine.  A generic ``driver_specs`` map may
    override any method driver with flat/growth/explicit annual source values.
    """
    if not ch:
        return 0.0
    method = ch.get("method")
    p = ch.get("params") or {}
    specs = ch.get("driver_specs") or {}
    if method == "pool_conversion":
        pool = _channel_param(ch, "pool", year, "pool_growth")
        conv = _channel_param(ch, "conversion_rate", year, "conversion_growth")
        return pool * conv
    if method == "spend_cac":
        spend = _channel_param(ch, "spend", year, "spend_growth")
        cac = _channel_param(ch, "cac", year, "cac_growth")
        return spend / cac if cac > 0 else 0.0
    if method == "fte_productivity":
        ftes = _channel_param(ch, "ftes", year, "ftes_growth")
        per = _channel_param(ch, "per_fte", year, "per_fte_growth")
        return ftes * per
    if method == "explicit":
        if "new_customers" in specs:
            return float(resolve_driver_spec(specs.get("new_customers"), year) or 0.0)
        arr = p.get("new_customers_by_year") or []
        i = year - 1
        return float(arr[i]) if 0 <= i < len(arr) else 0.0
    raise ValueError(f"unsupported customer-acquisition method {method!r}")


def channel_avg_auc(ch, year):
    """Average AUC per customer acquired by this channel in the given year."""
    if not ch:
        return 0.0
    return _driver(ch, "avg_auc_per_customer", year,
                   legacy_base=ch.get("avg_auc_per_customer"),
                   legacy_growth=ch.get("avg_auc_growth"))


def channel_spend(ch, year):
    """Acquisition spend attributed to this channel in the given year, for CAC computation."""
    if not ch:
        return 0.0
    method = ch.get("method")
    p = ch.get("params") or {}
    specs = ch.get("driver_specs") or {}
    if method == "spend_cac":
        return _channel_param(ch, "spend", year, "spend_growth")
    if method == "fte_productivity":
        ftes = _channel_param(ch, "ftes", year, "ftes_growth")
        comp = _channel_param(ch, "comp_per_fte", year, "comp_growth")
        return ftes * comp
    if method == "pool_conversion":
        cpc = (_driver(ch, "cost_per_customer", year,
                       legacy_base=p.get("cost_per_customer"), legacy_growth=0.0)
               if ("cost_per_customer" in specs or p.get("cost_per_customer") is not None) else 0.0)
        return channel_new_customers(ch, year) * cpc if cpc else 0.0
    if method == "explicit":
        if "spend" in specs:
            return float(resolve_driver_spec(specs.get("spend"), year) or 0.0)
        return float(p.get("spend") or 0.0)
    raise ValueError(f"unsupported customer-acquisition method {method!r}")


def cac_auc_rollforward(cac_cfg, Q, ppy=4):
    """Annual customer/AUC roll-forward over ceil(Q/ppy) years, returned with a native-cadence
    explicit-levels AUC series plus a per-year audit trail for defensibility.

    cac_cfg = {
      channels: [ {name, method, params, avg_auc_per_customer, avg_auc_growth}, ... ],
      attrition_rate: r,                 # fraction of existing BOOK (customers) lost per year
      attrition_avg_ticket: $ | None,    # override; default = beginning AUC / beginning customers
      beginning_auc: $,                  # usually 0 (no Day-1 pre-commitment)
      beginning_customers: n,            # usually 0
      intra_year_shape: "linear"|"stepped",  # how a year's net change spreads across its 4 quarters
    }

    Returns {
      auc_end_by_period: [ ... len Q ... ], # cadence-neutral ABSOLUTE period-end AUC
      auc_levels_q: [ ... len Q ... ],        # legacy alias retained for compatibility
      year_end_auc: [ ... per year ... ],
      annual: [ per-year records with channel detail, CAC, attrition ],
    }
    """
    channels = (cac_cfg or {}).get("channels") or []
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
            nc = channel_new_customers(ch, y)
            na = nc * channel_avg_auc(ch, y)
            sp = channel_spend(ch, y)
            new_cust += nc
            new_auc += na
            ch_detail.append({
                "name": ch.get("name"), "new_customers": nc, "new_auc": na,
                "spend": sp, "cac": (sp / nc if nc > 0 else None),
            })
        # Attrition on the existing book (beginning), not on this year's new adds.
        # Attrition itself may be an explicit annual source-model driver.
        attr = _driver(cac_cfg or {}, "attrition_rate", y, legacy_base=legacy_attr, legacy_growth=0.0)
        cust_lost = beg_cust * attr
        _ticket_specs = ((cac_cfg or {}).get("driver_specs") or {})
        if "attrition_avg_ticket" in _ticket_specs:
            avg_ticket = float(resolve_driver_spec(_ticket_specs.get("attrition_avg_ticket"), y) or 0.0)
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

    # Annual ending levels -> native-cadence ABSOLUTE levels (intra-year resolution).
    auc_levels_q = [0.0] * int(Q)
    prev_end = float((cac_cfg or {}).get("beginning_auc") or 0.0)
    for y in range(1, years + 1):
        ye = year_end_auc[y - 1]
        for qi in range(1, ppy + 1):
            q = (y - 1) * ppy + qi
            if q > Q:
                break
            if shape == "stepped":
                auc_levels_q[q - 1] = ye
            else:  # linear: ramp from prior year-end to this year-end across the 4 quarters
                auc_levels_q[q - 1] = prev_end + (ye - prev_end) * qi / float(ppy)
        prev_end = ye

    return {"auc_end_by_period": auc_levels_q, "auc_levels_q": auc_levels_q,
            "year_end_auc": year_end_auc, "annual": annual}


def cac_managed_notional(cac_cfg, Q, ppy=4):
    """Convenience: package the feeder's native-cadence AUC levels as a managed_notional the fee
    engine consumes directly (trajectory=explicit_levels). This is the seam."""
    r = cac_auc_rollforward(cac_cfg, Q, ppy)
    return {
        "day1": 0.0,
        "trajectory": "explicit_levels",
        "schedule": {str(q + 1): r["auc_end_by_period"][q] for q in range(int(Q))},
    }
