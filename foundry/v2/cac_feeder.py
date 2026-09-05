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
  pool_conversion : new_customers = pool x conversion_rate         (affiliate / addressable base)
  spend_cac       : new_customers = spend / CAC                    (direct/BD; spend links to opex)
  fte_productivity: new_customers = FTEs x new_accounts_per_FTE    (sales-force-driven)
  explicit        : new_customers = a per-year list you enter      (manual override)

ROLL-FORWARD (annual; converted to the engine's quarterly clock at the end):
  Beginning AUC (0 in Year 1; prior-year ending thereafter)
  + New AUC   (sum over channels: new_customers x avg_auc_per_customer)
  - AUC lost to attrition (customers_lost x avg ticket of existing book)
  = Ending AUC   -> feeds managed_notional.explicit_levels

All functions are pure (config -> series). Nothing here is wired into the engine yet; importing
this module changes no existing behavior.
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


def channel_new_customers(ch, year):
    """New customers acquired by one channel in a given year (1-indexed). Method-dispatched.
    Unknown method => 0.0 (extensible; never raises)."""
    if not ch:
        return 0.0
    method = ch.get("method")
    p = ch.get("params") or {}
    if method == "pool_conversion":
        pool = _grow(p.get("pool"), p.get("pool_growth"), year)
        conv = _grow(p.get("conversion_rate"), p.get("conversion_growth"), year)
        return pool * conv
    if method == "spend_cac":
        spend = _grow(p.get("spend"), p.get("spend_growth"), year)
        cac = _grow(p.get("cac"), p.get("cac_growth"), year)
        return spend / cac if cac > 0 else 0.0
    if method == "fte_productivity":
        ftes = _grow(p.get("ftes"), p.get("ftes_growth"), year)
        per = _grow(p.get("per_fte"), p.get("per_fte_growth"), year)
        return ftes * per
    if method == "explicit":
        arr = p.get("new_customers_by_year") or []
        i = year - 1
        return float(arr[i]) if 0 <= i < len(arr) else 0.0
    return 0.0


def channel_avg_auc(ch, year):
    """Average AUC per customer acquired by this channel in the given year (may grow)."""
    if not ch:
        return 0.0
    return _grow(ch.get("avg_auc_per_customer"), ch.get("avg_auc_growth"), year)


def channel_spend(ch, year):
    """Acquisition SPEND attributed to this channel in the given year, for CAC computation.
    spend_cac: the spend itself. fte_productivity: FTEs x comp. pool_conversion: optional
    cost_per_customer x new customers. explicit: optional flat spend. 0 if none applies."""
    if not ch:
        return 0.0
    method = ch.get("method")
    p = ch.get("params") or {}
    if method == "spend_cac":
        return _grow(p.get("spend"), p.get("spend_growth"), year)
    if method == "fte_productivity":
        ftes = _grow(p.get("ftes"), p.get("ftes_growth"), year)
        comp = _grow(p.get("comp_per_fte"), p.get("comp_growth"), year)
        return ftes * comp
    if method == "pool_conversion":
        cpc = float(p.get("cost_per_customer") or 0.0)
        return channel_new_customers(ch, year) * cpc if cpc else 0.0
    return float(p.get("spend") or 0.0)  # explicit: optional flat spend


def cac_auc_rollforward(cac_cfg, Q, ppy=4):
    """Annual customer/AUC roll-forward over ceil(Q/4) years, returned with a quarterly
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
      auc_levels_q: [ ... len Q ... ],   # ABSOLUTE quarter-end AUC -> explicit_levels socket
      year_end_auc: [ ... per year ... ],
      annual: [ per-year records with channel detail, CAC, attrition ],
    }
    """
    channels = (cac_cfg or {}).get("channels") or []
    attr = float((cac_cfg or {}).get("attrition_rate") or 0.0)
    ticket_override = (cac_cfg or {}).get("attrition_avg_ticket")
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
        # attrition on the existing book (beginning), not on this year's new adds
        cust_lost = beg_cust * attr
        if ticket_override is not None:
            avg_ticket = float(ticket_override)
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
            "total_spend": total_spend,
            "blended_cac": (total_spend / new_cust if new_cust > 0 else None),
            "channels": ch_detail,
        })
        year_end_auc.append(end_auc)
        beg_auc, beg_cust = end_auc, end_cust

    # annual ending levels -> quarterly ABSOLUTE levels (intra-year interpolation)
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

    return {"auc_levels_q": auc_levels_q, "year_end_auc": year_end_auc, "annual": annual}


def cac_managed_notional(cac_cfg, Q, ppy=4):
    """Convenience: package the feeder's quarterly AUC levels as a managed_notional the fee
    engine consumes directly (trajectory=explicit_levels). This is the seam."""
    r = cac_auc_rollforward(cac_cfg, Q, ppy)
    return {
        "day1": 0.0,
        "trajectory": "explicit_levels",
        "schedule": {str(q + 1): r["auc_levels_q"][q] for q in range(int(Q))},
    }
