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


def managed_notional_series(mn, Q):
    """Roll an off-book notional stock (AUC/AUM) forward Q quarters.

    mn = {day1, target?, ramp_periods?, trajectory, growth_q?, schedule?}
    trajectory in {ramp_to_target, flat, proportional, explicit_schedule}.
    Returns (avg_by_q, end_by_q) — avg is what balance-basis fees charge against;
    end is the disclosed period-end AUC. Absent/empty => zeros (hash-safe).
    """
    if not mn:
        return [0.0] * Q, [0.0] * Q
    day1 = float(mn.get("day1") or 0.0)
    traj = mn.get("trajectory") or "flat"
    end = [0.0] * Q
    prev = day1
    if traj == "ramp_to_target":
        target = float(mn.get("target") or 0.0)
        ramp = int(mn.get("ramp_periods") or Q)
        for q in range(1, Q + 1):
            frac = min(1.0, q / ramp) if ramp > 0 else 1.0
            end[q - 1] = day1 + (target - day1) * frac
    elif traj == "proportional":
        g = float(mn.get("growth_q") or 0.0)
        for q in range(1, Q + 1):
            end[q - 1] = day1 * (1 + g) ** q
    elif traj == "explicit_schedule":
        sched = mn.get("schedule") or {}
        cur = day1
        for q in range(1, Q + 1):
            cur = cur + float(sched.get(str(q), 0.0))   # additive lumps (deltas)
            end[q - 1] = cur
    elif traj == "explicit_levels":
        # ABSOLUTE per-period levels (already net of adds/attrition) — used as-is, NOT
        # accumulated. This is the socket for an upstream feeder (e.g. the CAC AUC
        # roll-forward) that emits ending-AUC levels directly. Missing quarter carries
        # the prior level forward (hold), so a sparse schedule still yields a full series.
        sched = mn.get("schedule") or {}
        cur = day1
        for q in range(1, Q + 1):
            if str(q) in sched:
                cur = float(sched[str(q)])
            end[q - 1] = cur
    else:  # flat
        for q in range(1, Q + 1):
            end[q - 1] = day1
    avg = []
    prev = day1
    for q in range(1, Q + 1):
        avg.append((prev + end[q - 1]) / 2.0)
        prev = end[q - 1]
    return avg, end


def _fee_rate_q(rt, q, base_qty):
    """Axis 4 (rate behavior): flat | annual_change | scheduled | tiered.
    Returns an EFFECTIVE rate for quarter q. For tiered, returns None and the caller
    applies the tier schedule against base_qty directly (marginal breakpoints)."""
    behavior = (rt or {}).get("behavior") or "flat"
    rp = (rt or {}).get("params") or {}
    r0 = float(rp.get("rate") or 0.0)
    if behavior == "annual_change":
        yr = (q - 1) // 4                       # 0 in year 1, 1 in year 2, ...
        delta = float(rp.get("annual_delta") or 0.0)
        return r0 * ((1.0 + delta) ** yr)
    if behavior == "scheduled":
        sched = rp.get("schedule") or {}         # {quarter: rate}
        return float(sched.get(str(q), r0))
    if behavior == "tiered":
        return None                              # signal: apply tiers to base_qty
    return r0                                     # flat


def _apply_tiers(tiers, base_qty):
    """Marginal breakpoint pricing: [{up_to: X or null, rate: r}, ...] applied cumulatively.
    Returns the summed (portion * rate) across tiers. up_to=null/None means 'remainder'."""
    out = 0.0
    lo = 0.0
    for t in (tiers or []):
        up = t.get("up_to")
        r = float(t.get("rate") or 0.0)
        hi = base_qty if (up is None) else min(base_qty, float(up))
        if hi > lo:
            out += (hi - lo) * r
        lo = hi
        if up is not None and base_qty <= float(up):
            break
    return out


def fee_stream_q(stream, q, ctx):
    """One fee stream's NET income for quarter q ($). Full six-axis GUT evaluator.

    Axis 1 Basis:        balance | transaction | account | flat | event
    Axis 2 Driver source: constant | own_balance | managed_notional | stream_ref | bank_aggregate
    Axis 3 Trajectory:    flat | proportional | ramp_to_target | explicit_schedule | derived
    Axis 4 Rate:          flat | annual_change | scheduled | tiered
    Axis 5 Timing:        start_period | end_period | ramp_in_periods
    Axis 6 Cost:          none | per_unit | pct_of_revenue

    ctx supplies: own_balance, managed_notional (rolled AUC), stream_qty (map: name->driver
    quantity of already-evaluated streams, for stream_ref), and bank_aggregate (map: e.g.
    total_deposits/total_assets, prior-quarter to avoid circularity).
    Unknown basis/source/behavior degrade to 0/flat (extensible; never raises).
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

    # ---- Axis 2 + 3: driver quantity ----
    src = drv.get("source") or "constant"
    traj = drv.get("trajectory") or "flat"
    base = float(params.get("base") or 0.0)

    def _source_base():
        if src == "own_balance":
            return float((ctx or {}).get("own_balance") or 0.0)
        if src == "managed_notional":
            return float((ctx or {}).get("managed_notional") or 0.0)
        if src == "stream_ref":
            ref = drv.get("ref")
            return float(((ctx or {}).get("stream_qty") or {}).get(ref) or 0.0)
        if src == "bank_aggregate":
            ref = drv.get("ref")
            return float(((ctx or {}).get("bank_aggregate") or {}).get(ref) or 0.0)
        return base  # constant

    sb = _source_base()
    if src == "constant":
        if traj == "proportional":
            qty = _g(base, params.get("growth_q"), q)
        elif traj == "explicit_schedule":
            qty = float((params.get("schedule") or {}).get(str(q), base))
        else:
            qty = base
    else:
        # sourced quantity (own_balance/managed_notional/stream_ref/bank_aggregate)
        if traj == "derived":
            # a multiple or percentage of the source (settlement notional = turns x AUC)
            mult = params.get("multiple")
            pct = params.get("pct")
            if mult is not None:
                qty = sb * float(mult)
            elif pct is not None:
                qty = sb * float(pct)
            else:
                qty = sb
        elif traj == "proportional":
            qty = _g(sb, params.get("growth_q"), q)
        else:
            qty = sb  # flat/ramp_to_target already baked into the source stock

    # expose this stream's driver quantity for downstream stream_ref consumers
    nm = stream.get("name")
    if nm and isinstance(ctx, dict):
        ctx.setdefault("stream_qty", {})[nm] = qty

    # ---- Axis 1 + 4: basis application with rate behavior ----
    eff_rate = _fee_rate_q(rt, q, qty)
    gross = 0.0
    if basis == "balance":
        if eff_rate is None:  # tiered on balance
            gross = _apply_tiers(rate_params.get("tiers"), qty) / 4.0
        else:
            gross = qty * eff_rate / 4.0
    elif basis == "transaction":
        if eff_rate is None:
            gross = _apply_tiers(rate_params.get("tiers"), qty)
        else:
            per_unit = float(rate_params.get("per_unit") or 0.0)
            gross = qty * per_unit
    elif basis == "account":
        per_period = float(rate_params.get("fee_per_period") or 0.0)
        periods = float(rate_params.get("periods_per_q") or 1.0)
        gross = qty * per_period * periods
    elif basis == "flat":
        gross = float(rate_params.get("amount_per_period") or 0.0)
    elif basis == "event":
        at = params.get("at_period")
        amt = float(rate_params.get("amount") or params.get("amount") or 0.0)
        gross = amt if (at is not None and int(at) == q) else 0.0
    else:
        return 0.0  # unknown basis (extensible)

    # ---- Axis 5: ramp-in phase (revenue phases in over K periods after start) ----
    ramp_in = tm.get("ramp_in_periods")
    if ramp_in:
        k = int(ramp_in)
        if k > 0:
            gross *= min(1.0, (q - start + 1) / k)

    # ---- Axis 6: cost side ----
    cost = stream.get("cost") or {}
    ck = cost.get("kind") or "none"
    cp = cost.get("params") or {}
    if ck == "per_unit" and basis == "transaction":
        gross -= qty * float(cp.get("cost_per_unit") or 0.0)
    elif ck == "pct_of_revenue":
        gross -= gross * float(cp.get("pct") or 0.0)

    return gross


def fee_streams_order(streams):
    """Topologically sort streams by stream_ref dependency. Raises ValueError on a cycle
    (fail-closed, per the GUT's DAG requirement). Streams without a name or without
    stream_ref deps are independent and come first."""
    by_name = {}
    for i, st in enumerate(streams):
        nm = (st or {}).get("name")
        if nm:
            by_name[nm] = i
    # edges: stream i depends on stream j if i's driver.source==stream_ref and ref==name(j)
    deps = {i: set() for i in range(len(streams))}
    for i, st in enumerate(streams):
        drv = (st or {}).get("driver") or {}
        if drv.get("source") == "stream_ref":
            ref = drv.get("ref")
            if ref in by_name and by_name[ref] != i:
                deps[i].add(by_name[ref])
    order, visiting, done = [], set(), set()
    def visit(i):
        if i in done:
            return
        if i in visiting:
            raise ValueError("fee stream cycle detected (stream_ref forms a loop)")
        visiting.add(i)
        for j in deps[i]:
            visit(j)
        visiting.discard(i)
        done.add(i)
        order.append(i)
    for i in range(len(streams)):
        visit(i)
    return order


def product_fee_streams_q(p, q, ctx):
    """Sum a product's fee_streams for quarter q ($), evaluated in dependency order so
    stream_ref consumers see their source's quantity. Empty/absent => 0.0 (hash-safe)."""
    streams = p.get("fee_streams") or []
    if not streams:
        return 0.0
    ctx = dict(ctx or {})
    ctx.setdefault("stream_qty", {})
    try:
        order = fee_streams_order(streams)
    except ValueError:
        # fail-closed: a cyclic config contributes nothing rather than looping/guessing
        raise
    total = 0.0
    for i in order:
        total += fee_stream_q(streams[i], q, ctx)
    return total


def durbin_regulated_rate(avg_ticket, reg_params=None):
    """Axis-7 (conditional/threshold) — the regulated debit interchange rate that binds at/above
    the $10B Durbin asset threshold, expressed as a FRACTION of transaction value (comparable to
    the assumed unregulated interchange_rate). Regulated per-transaction cap =
    base + ad_valorem*avg_ticket + fraud_adjustment; dividing by avg_ticket yields the effective
    rate. Constants (and the pending Fed reduction) resolve from REG_PARAMS, never memory."""
    if not avg_ticket or avg_ticket <= 0:
        return 0.0
    if reg_params is None:
        from .regparams import REG_PARAMS as reg_params
    d = reg_params.get("durbin") or {}
    cap_per_tx = (float(d.get("cap_base_per_tx") or 0.0)
                  + float(d.get("cap_ad_valorem") or 0.0) * float(avg_ticket)
                  + float(d.get("cap_fraud_adjustment") or 0.0))
    return cap_per_tx / float(avg_ticket)


def durbin_effective_rate(assumed_rate, avg_ticket, prior_qtr_assets_000s, reg_params=None):
    """The interchange rate that actually applies for a quarter, given PRIOR-quarter assets
    (prior-quarter pricing sidesteps the circular dependency: interchange -> NI -> equity ->
    assets -> cap). Below the $10B threshold: the assumed (unregulated) rate. At/above: the
    LESSER of the assumed rate and the regulated cap (the cap only ever reduces, never raises).
    Option-B timing: the cap binds in each quarter where prior-quarter assets >= threshold."""
    if reg_params is None:
        from .regparams import REG_PARAMS as reg_params
    d = reg_params.get("durbin") or {}
    thr = float(d.get("asset_threshold_000s") or 1e18)
    a_rate = float(assumed_rate or 0.0)
    if (prior_qtr_assets_000s or 0.0) >= thr:
        cap_rate = durbin_regulated_rate(avg_ticket, reg_params)
        return min(a_rate, cap_rate)
    return a_rate


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
