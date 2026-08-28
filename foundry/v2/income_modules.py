"""Wave 3 (FLOOR F-036/070/071/072/141/142/143): income granularity.

Pure functions from config to quarterly series ($ dollars), consumed by BOTH
engines. Everything is additive and default-off: absent config => empty series.

NIE detail (F-071/072, fixing D-P14 and D-R8):
  assumptions.nie_detail = {
    "fte_by_year": [y1, y2, y3], "loaded_comp_annual": $,
    "categories": [{"name": str, "per_quarter": $}, ...],
    "other_gross_up_rate": r,           # Patrick's sub*r/(1-r) formulation, kept
  }
  Assessments are computed by the ENGINE (they need balances): FDIC on
  (avg consolidated assets - avg tangible equity) per 12 USC 1817(b)(2)(A),
  OCC on average assets; rates from REG_PARAMS.

Fee modules (F-036/070/141/142/143, fixing D-P10/11/13):
  assumptions.fee_modules = {
    "interchange": {"tx_count_q": n, "growth_q": g, "avg_ticket": $,
                     "interchange_rate": r, "network_fee_rate": r},
    "payments": [{"rail": str, "vol_q": n, "growth_q": g,
                   "fee_per_tx": $, "cost_per_tx": $}, ...],
    "service_charges": {"accounts": n, "growth_q": g, "fee_m": $},
    "trust": {"aum_open": $, "aum_growth_q": g, "fee_bp_ann": bp},
    "baas": {"programs": n, "accts_per_program": n, "growth_q": g,
              "rev_per_acct_m": $},
  }
  Every module carries a growth path (fixing D-P10's static-forever fees).
"""

Q = 12


def _g(base, growth, q):
    return base * (1 + (growth or 0.0)) ** (q - 1)


def nie_detail_series(a):
    """(comp_q, categories_q, gross_up_rate) or None when absent."""
    Q = int(a.get("n_periods") or 12)
    nd = a.get("nie_detail")
    if not nd:
        return None
    fte = list(nd.get("fte_by_year") or [0, 0, 0])
    loaded = float(nd.get("loaded_comp_annual") or 0.0)
    _lastyr = len(fte) - 1        # beyond the provided years, hold the final year's FTE
    comp = [fte[min((q - 1) // 4, _lastyr)] * loaded / 4.0 for q in range(1, Q + 1)]
    cats = [float(sum(c.get("per_quarter", 0.0) for c in (nd.get("categories") or [])))] * Q
    return {"comp": comp, "categories": cats,
             "gross_up_rate": float(nd.get("other_gross_up_rate") or 0.0),
             # Assessment-rate overrides (engagement assumptions). None -> engine falls back to
             # the REG_PARAMS default, so an untouched config's assessments are byte-identical.
             "fdic_bp_ann": (float(nd["fdic_bp_ann"]) if nd.get("fdic_bp_ann") is not None else None),
             "occ_bp_ann": (float(nd["occ_bp_ann"]) if nd.get("occ_bp_ann") is not None else None)}


def fee_stream_q(stream, q, ctx):
    """One fee stream's income for quarter q ($). Additive, per-product (six-axis model).

    stream = {basis, driver:{source,ref,trajectory,params}, rate:{behavior,params},
              timing:{start_period,end_period}, cost:{kind,params}}
    ctx supplies resolvable drivers: own_balance (this product's avg balance for q),
    and a map of already-computed stream outputs (for source=stream_ref) — kept minimal
    here; cross-reference (stream_ref) and managed_notional land in later increments.

    Closed basis set {balance, transaction, account, flat}; unknown basis => 0.0 (extensible:
    a future basis is addable without breaking existing streams). Timing gates start/end.
    """
    if not stream:
        return 0.0
    tm = stream.get("timing") or {}
    start = int(tm.get("start_period") or 1)
    end = tm.get("end_period")
    if q < start or (end is not None and q > int(end)):
        return 0.0
    basis = stream.get("basis")
    drv = stream.get("driver") or {}
    rt = stream.get("rate") or {}
    params = drv.get("params") or {}
    rate_params = rt.get("params") or {}

    # --- driver quantity for this quarter ---
    src = drv.get("source") or "constant"
    traj = drv.get("trajectory") or "flat"
    base = float(params.get("base") or 0.0)
    if src == "own_balance":
        qty = float((ctx or {}).get("own_balance") or 0.0)
    elif src == "constant":
        if traj == "proportional":
            qty = _g(base, params.get("growth_q"), q)
        elif traj == "explicit_schedule":
            sched = params.get("schedule") or {}
            qty = float(sched.get(str(q), base))
        else:  # flat
            qty = base
    else:
        qty = 0.0  # managed_notional / stream_ref resolved in a later increment

    # --- rate for this quarter (Axis 4: flat only in this increment) ---
    rate = float(rate_params.get("rate") or 0.0)

    # --- basis application (Axis 1) ---
    if basis == "balance":
        # rate is annual bps-or-fraction on avg balance, quarterly
        return qty * rate / 4.0
    if basis == "transaction":
        per_unit = float(rate_params.get("per_unit") or 0.0)
        return qty * per_unit
    if basis == "account":
        per_period = float(rate_params.get("fee_per_period") or 0.0)
        periods = float(rate_params.get("periods_per_q") or 1.0)
        return qty * per_period * periods
    if basis == "flat":
        return float(rate_params.get("amount_per_period") or 0.0)
    return 0.0  # unknown basis: extensible, never raises


def product_fee_streams_q(p, q, ctx):
    """Sum of a product's fee_streams for quarter q ($). Empty/absent => 0.0 (hash-safe)."""
    streams = p.get("fee_streams") or []
    if not streams:
        return 0.0
    return sum(fee_stream_q(s, q, ctx) for s in streams)


def fee_module_series(a):
    """{"income": [...Q], "cost": [...Q], "detail": {...}} — zeros when absent."""
    Q = int(a.get("n_periods") or 12)
    fm = a.get("fee_modules") or {}
    inc = [0.0] * Q
    cost = [0.0] * Q
    detail = {}
    ic = fm.get("interchange")
    if ic:
        s = []
        for q in range(1, Q + 1):
            vol = _g(float(ic.get("tx_count_q") or 0.0), ic.get("growth_q"), q)
            gross = vol * float(ic.get("avg_ticket") or 0.0) * float(ic.get("interchange_rate") or 0.0)
            net_fees = vol * float(ic.get("avg_ticket") or 0.0) * float(ic.get("network_fee_rate") or 0.0)
            s.append(gross - net_fees)
        detail["interchange"] = s
        inc = [inc[i] + s[i] for i in range(Q)]
    pays = fm.get("payments") or []
    if pays:
        si, sc = [0.0] * Q, [0.0] * Q
        for rail in pays:
            for q in range(1, Q + 1):
                vol = _g(float(rail.get("vol_q") or 0.0), rail.get("growth_q"), q)
                si[q - 1] += vol * float(rail.get("fee_per_tx") or 0.0)
                sc[q - 1] += vol * float(rail.get("cost_per_tx") or 0.0)
        detail["payments_income"], detail["payments_cost"] = si, sc
        inc = [inc[i] + si[i] for i in range(Q)]
        cost = [cost[i] + sc[i] for i in range(Q)]
    sv = fm.get("service_charges")
    if sv:
        s = [_g(float(sv.get("accounts") or 0.0), sv.get("growth_q"), q)
              * float(sv.get("fee_m") or 0.0) * 3.0 for q in range(1, Q + 1)]
        detail["service_charges"] = s
        inc = [inc[i] + s[i] for i in range(Q)]
    tr = fm.get("trust")
    if tr:
        s = []
        aum = float(tr.get("aum_open") or 0.0)
        for q in range(1, Q + 1):
            aum_end = aum * (1 + float(tr.get("aum_growth_q") or 0.0))
            s.append((aum + aum_end) / 2.0 * float(tr.get("fee_bp_ann") or 0.0) / 10000.0 / 4.0)
            aum = aum_end
        detail["trust"] = s
        detail["trust_aum_end"] = aum
        inc = [inc[i] + s[i] for i in range(Q)]
    bs_ = fm.get("baas")
    if bs_:
        s = [_g(float(bs_.get("programs") or 0.0) * float(bs_.get("accts_per_program") or 0.0),
                 bs_.get("growth_q"), q) * float(bs_.get("rev_per_acct_m") or 0.0) * 3.0
              for q in range(1, Q + 1)]
        detail["baas"] = s
        inc = [inc[i] + s[i] for i in range(Q)]
    return {"income": inc, "cost": cost, "detail": detail}
