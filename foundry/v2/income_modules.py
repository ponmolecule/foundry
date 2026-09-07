"""Wave 3 (FLOOR F-036/070/071/072/141/142/143): income granularity.

Pure functions from config to engine-period series ($ dollars), consumed by BOTH
engines. Everything is additive and default-off: absent config => empty series.

NIE detail (F-071/072, fixing D-P14 and D-R8):
  assumptions.nie_detail = {
    "fte_by_year": [y1, y2, y3], "loaded_comp_annual": $,
    "categories": [{"name": str, "per_period": $}, ...],  # legacy per_quarter accepted
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


def nie_detail_series(a, ppy=4, growth_context=None, *, defer_workforce=False, workforce_metric_series=None):
    """(comp_q, categories_q, gross_up_rate) or None when absent.

    ``defer_workforce`` lets the main engine evaluate role activation period-by-period
    against completed financial metrics.  Standalone callers can instead supply
    ``workforce_metric_series`` for deterministic metric-triggered resolution.
    """
    Q = int(a.get("n_periods") or 12)
    nd = a.get("nie_detail")
    if not nd:
        return None
    # New workforce authoring supersedes the legacy FTE Y1/Y2/Y3 ladder when roles
    # are present. Legacy configs remain byte-identical because the old path is used
    # unchanged when workforce is absent/empty.
    _wf = nd.get("workforce") or {}
    if _wf.get("mode") == "roles" or _wf.get("roles"):
        if defer_workforce:
            comp = [0.0] * Q
        else:
            from .workforce import workforce_comp_series
            comp = workforce_comp_series(_wf, Q, ppy, growth_context=growth_context,
                                          metric_series=workforce_metric_series)
    else:
        fte = list(nd.get("fte_by_year") or [0, 0, 0])
        loaded = float(nd.get("loaded_comp_annual") or 0.0)
        _lastyr = len(fte) - 1        # beyond the provided years, hold the final year's FTE
        comp = [fte[min((q - 1) // ppy, _lastyr)] * loaded / float(ppy) for q in range(1, Q + 1)]
    # Per-category ENGINE-period series. Canonical UI fields are per_period and
    # growth_per_period. Legacy per_quarter/growth_q retain their calendar-quarter
    # meaning and are converted to the selected cadence.
    _catlist = nd.get("categories") or []
    cats = [float(sum(nie_category_series(c, Q, ppy, growth_context=growth_context)[i]
                      for c in _catlist)) for i in range(Q)]
    return {"comp": comp, "categories": cats,
             "gross_up_rate": float(nd.get("other_gross_up_rate") or 0.0),
             # Assessment-rate overrides (engagement assumptions). None -> engine falls back to
             # the REG_PARAMS default, so an untouched config's assessments are byte-identical.
             "fdic_bp_ann": (float(nd["fdic_bp_ann"]) if nd.get("fdic_bp_ann") is not None else None),
             "occ_bp_ann": (float(nd["occ_bp_ann"]) if nd.get("occ_bp_ann") is not None else None)}



def nie_category_series(c, Q, ppy=4, growth_context=None):
    """Resolve one Operating Expense category to its native-period dollar flow.

    Public helper for safe cross-module Foundry-series links.  It is intentionally the
    same resolver used by ``nie_detail_series`` so a linked CAC spend path cannot drift
    from the expense actually modeled on the income statement.
    """
    from .timebase import quarterly_value_to_period
    Q, ppy = int(Q), int(ppy)
    c = c or {}
    traj = c.get("trajectory") or "flat"
    if c.get("per_period") is not None:
        base = float(c.get("per_period") or 0.0)
    else:
        base = quarterly_value_to_period("opex_fixed", float(c.get("per_quarter", 0.0) or 0.0), ppy)
    if traj == "explicit":
        sched = list(c.get("schedule") or [])
        return [float(sched[i]) if i < len(sched) and sched[i] is not None else 0.0
                for i in range(Q)]
    if traj in ("linear", "growth"):
        if c.get("growth_spec"):
            from .growth import resolve_growth_series
            return resolve_growth_series(base, c.get("growth_spec"), Q, ppy,
                                         context=growth_context)
        if c.get("growth_per_period") is not None:
            g = float(c.get("growth_per_period") or 0.0)
        else:
            g = quarterly_value_to_period("growth", float(c.get("growth_q") or 0.0), ppy)
        return [base * ((1.0 + g) ** (q - 1)) for q in range(1, Q + 1)]
    return [base] * Q

def managed_notional_series(mn, Q, ppy=4, growth_context=None):
    """Roll an off-book notional stock (AUC/AUM) forward Q engine periods.

    Canonical duration/growth fields are ramp_periods and growth_per_period. Legacy
    ramp_quarters/growth_q retain calendar-quarter semantics and are cadence-converted.
    trajectory in {ramp_to_target, flat, proportional, explicit_schedule}.
    Returns (avg_by_period, end_by_period). Absent/empty => zeros (hash-safe).
    """
    if not mn:
        return [0.0] * Q, [0.0] * Q
    day1 = float(mn.get("day1") or 0.0)
    traj = mn.get("trajectory") or "flat"
    end = [0.0] * Q
    prev = day1
    if traj == "ramp_to_target":
        target = float(mn.get("target") or 0.0)
        from .timebase import quarters_to_periods
        if mn.get("ramp_periods") is not None:
            ramp = int(mn.get("ramp_periods") or Q)
        elif mn.get("ramp_quarters") is not None:
            ramp = quarters_to_periods(int(mn.get("ramp_quarters") or 0), ppy)
        else:
            ramp = Q
        for q in range(1, Q + 1):
            frac = min(1.0, q / ramp) if ramp > 0 else 1.0
            end[q - 1] = day1 + (target - day1) * frac
    elif traj == "proportional":
        if mn.get("growth_spec"):
            from .growth import resolve_growth_series
            # day1 is an opening stock immediately before P1. Smooth growth therefore
            # earns one native period by P1; stepped annual growth remains flat until
            # its first selected boundary.
            end = resolve_growth_series(day1, mn.get("growth_spec"), Q, ppy,
                                        context=growth_context, base_position="opening")
            prev = day1
        else:
            from .timebase import quarterly_value_to_period
            g = (float(mn.get("growth_per_period") or 0.0) if mn.get("growth_per_period") is not None
                 else quarterly_value_to_period("growth", float(mn.get("growth_q") or 0.0), ppy))
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


def _fee_rate_q(rt, q, base_qty, ppy=4):
    """Axis 4 (rate behavior): flat | annual_change | scheduled | tiered.
    Returns an EFFECTIVE rate for quarter q. For tiered, returns None and the caller
    applies the tier schedule against base_qty directly (marginal breakpoints)."""
    behavior = (rt or {}).get("behavior") or "flat"
    rp = (rt or {}).get("params") or {}
    r0 = float(rp.get("rate") or 0.0)
    if behavior == "annual_change":
        yr = (q - 1) // ppy                      # 0 in year 1, 1 in year 2, ...
        delta = float(rp.get("annual_delta") or 0.0)
        return r0 * ((1.0 + delta) ** yr)
    if behavior == "scheduled":
        sched = rp.get("schedule") or {}         # {quarter: rate}
        return float(sched.get(str(q), r0))
    if behavior == "tiered":
        return None                              # signal: apply tiers to base_qty
    # durbin_capped: normal income uses the stream's net per_unit (set at config time);
    # the threshold overage on the GROSS rate is applied in the engine P&L loop where
    # prior-quarter assets exist. Here it behaves like flat for the income path.
    return r0                                     # flat / durbin_capped passthrough


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


_FEE_BASES = {"balance", "transaction", "account", "flat", "event"}
_FEE_SOURCES = {"constant", "own_balance", "managed_notional", "stream_ref", "bank_aggregate"}
_FEE_TRAJECTORIES = {"flat", "proportional", "ramp_to_target", "explicit_schedule", "derived"}
_FEE_RATE_BEHAVIORS = {"flat", "annual_change", "scheduled", "tiered", "durbin_capped"}
_FEE_COST_KINDS = {"none", "per_unit", "pct_of_revenue"}
_FEE_NATURAL_PERIODS = {"month", "quarter", "year", "model_period"}


def _fee_amount_per_engine_period(value, period, ppy):
    """Convert a value stated per natural Month/Quarter/Year to one engine period.

    Legacy fields deliberately bypass this helper so absence of the new explicit marker
    preserves their historic meaning.
    """
    v = float(value or 0.0)
    per = str(period or "").strip().lower()
    if per == "year":
        return v / float(ppy)
    if per == "quarter":
        return v * 4.0 / float(ppy)
    if per == "month":
        return v * 12.0 / float(ppy)
    if per == "model_period":
        return v
    raise ValueError(f"unsupported natural period: {period!r}")


def _fee_natural_period_index(q, period, ppy):
    """1-based natural-period index containing engine period q.

    Explicit coefficient schedules are keyed in their stated natural period, e.g. a
    Year schedule {1: 1.5, 2: 2.4, ...} means Year 1 / Year 2 regardless of engine cadence.
    """
    per = str(period or "").strip().lower()
    if per == "year":
        return (int(q) - 1) // int(ppy) + 1
    if per == "quarter":
        # Quarterly/monthly are the supported model cadences. Annual is tolerated for
        # internal evaluation by treating one engine period as four quarters.
        if int(ppy) == 12:
            return (int(q) - 1) // 3 + 1
        if int(ppy) == 4:
            return int(q)
        if int(ppy) == 1:
            return (int(q) - 1) * 4 + 1
    if per == "month":
        if int(ppy) == 12:
            return int(q)
        # A quarter cannot faithfully distinguish three different monthly schedule
        # values. Fail closed rather than silently choosing one.
        if int(ppy) == 4:
            raise ValueError("monthly coefficient schedule is not representable in quarterly cadence")
        if int(ppy) == 1:
            raise ValueError("monthly coefficient schedule is not representable in annual cadence")
    if per == "model_period":
        return int(q)
    raise ValueError(f"unsupported natural period: {period!r}")


def _fee_schedule_value(schedule, idx, default):
    """Carry the most recent explicit natural-period coefficient level forward."""
    cur = float(default or 0.0)
    points = []
    for k, v in (schedule or {}).items():
        try:
            points.append((int(k), float(v)))
        except (TypeError, ValueError):
            continue
    for k, v in sorted(points):
        if k > int(idx):
            break
        cur = v
    return cur


def _fee_coefficient_value(spec, q, ppy, ctx=None):
    """Resolve an explicit derived-flow coefficient into one engine-period coefficient.

    `spec.period` states the coefficient's natural flow unit (e.g. 4 turns / Year).
    This path is opt-in. Legacy `multiple` / `pct` fields remain raw per engine period.
    """
    spec = dict(spec or {})
    kind = str(spec.get("kind") or "").strip().lower()
    if kind not in {"multiple", "pct"}:
        raise ValueError(f"unsupported fee coefficient kind: {kind!r}")
    period = str(spec.get("period") or "").strip().lower()
    if period not in _FEE_NATURAL_PERIODS:
        raise ValueError(f"unsupported fee coefficient period: {period!r}")
    traj = str(spec.get("trajectory") or "flat").strip().lower()
    if traj not in {"flat", "growth", "explicit_schedule"}:
        raise ValueError(f"unsupported fee coefficient trajectory: {traj!r}")
    val = float(spec.get("value") or 0.0)
    if traj == "growth":
        gs = spec.get("growth_spec")
        if not gs:
            raise ValueError("fee coefficient growth trajectory requires growth_spec")
        from .growth import growth_multiplier
        val *= growth_multiplier(gs, current_period=int(q), start_period=1, ppy=int(ppy),
                                 context=(ctx or {}).get("growth_context"), base_position="period1")
    elif traj == "explicit_schedule":
        idx = _fee_natural_period_index(q, period, ppy)
        val = _fee_schedule_value(spec.get("schedule") or {}, idx, val)
    return _fee_amount_per_engine_period(val, period, ppy)


def _validate_fee_stream_shape(stream):
    """Fail closed on unsupported GUT vocabulary at the evaluator boundary."""
    st = stream or {}
    basis = st.get("basis")
    if basis not in _FEE_BASES:
        raise ValueError(f"unsupported fee basis: {basis!r}")
    drv = st.get("driver") or {}
    src = drv.get("source") or "constant"
    traj = drv.get("trajectory") or "flat"
    if src not in _FEE_SOURCES:
        raise ValueError(f"unsupported fee driver source: {src!r}")
    if traj not in _FEE_TRAJECTORIES:
        raise ValueError(f"unsupported fee driver trajectory: {traj!r}")
    rt = st.get("rate") or {}
    rb = rt.get("behavior") or "flat"
    if rb not in _FEE_RATE_BEHAVIORS:
        raise ValueError(f"unsupported fee rate behavior: {rb!r}")
    # Fail closed on basis/rate combinations the evaluator does not actually apply.
    # Without this guard, e.g. annual_change on an account/flat stream would be accepted
    # but silently ignored by the basis-specific calculation below.
    allowed_rate_behaviors = {
        "balance": {"flat", "annual_change", "scheduled", "tiered"},
        "transaction": {"flat", "tiered", "durbin_capped"},
        "account": {"flat"},
        "flat": {"flat"},
        "event": {"flat"},
    }
    if rb not in allowed_rate_behaviors[basis]:
        raise ValueError(f"fee rate behavior {rb!r} is unsupported for basis {basis!r}")
    cost = st.get("cost") or {}
    ck = cost.get("kind") or "none"
    if ck not in _FEE_COST_KINDS:
        raise ValueError(f"unsupported fee cost kind: {ck!r}")
    if ck == "per_unit" and basis != "transaction":
        raise ValueError("fee cost kind 'per_unit' is supported only on transaction basis")
    coef = (drv.get("params") or {}).get("coefficient")
    if coef is not None:
        if traj != "derived":
            raise ValueError("fee coefficient requires driver.trajectory='derived'")
        # Natural-period coefficients describe flows. Feeding them to balance basis would
        # divide once in the coefficient and again in the stock-rate basis (/ppy^2).
        if basis != "transaction":
            raise ValueError("natural-period fee coefficient is supported only on transaction basis")
        c = dict(coef or {})
        if str(c.get("kind") or "").strip().lower() not in {"multiple", "pct"}:
            raise ValueError(f"unsupported fee coefficient kind: {c.get('kind')!r}")
        if str(c.get("period") or "").strip().lower() not in _FEE_NATURAL_PERIODS:
            raise ValueError(f"unsupported fee coefficient period: {c.get('period')!r}")
        if str(c.get("trajectory") or "flat").strip().lower() not in {"flat", "growth", "explicit_schedule"}:
            raise ValueError(f"unsupported fee coefficient trajectory: {c.get('trajectory')!r}")
        if str(c.get("trajectory") or "flat").strip().lower() == "growth" and not c.get("growth_spec"):
            raise ValueError("fee coefficient growth trajectory requires growth_spec")
        if str(c.get("trajectory") or "flat").strip().lower() == "explicit_schedule" and not isinstance(c.get("schedule") or {}, dict):
            raise ValueError("fee coefficient explicit_schedule requires a mapping")
        try:
            float(c.get("value") or 0.0)
        except (TypeError, ValueError):
            raise ValueError("fee coefficient value must be numeric")
    rp = (rt.get("params") or {})
    if basis == "account" and rp.get("unit_fee") is not None:
        uf = rp.get("unit_fee") or {}
        if str(uf.get("period") or "").strip().lower() not in _FEE_NATURAL_PERIODS - {"model_period"}:
            raise ValueError(f"unsupported account fee period: {uf.get('period')!r}")
        try:
            float(uf.get("value") or 0.0)
        except (TypeError, ValueError):
            raise ValueError("account unit_fee value must be numeric")
    if basis == "flat" and rp.get("flat_amount") is not None:
        fa = rp.get("flat_amount") or {}
        if str(fa.get("period") or "").strip().lower() not in _FEE_NATURAL_PERIODS - {"model_period"}:
            raise ValueError(f"unsupported flat amount period: {fa.get('period')!r}")
        try:
            float(fa.get("value") or 0.0)
        except (TypeError, ValueError):
            raise ValueError("flat_amount value must be numeric")
    return True


def fee_stream_q(stream, q, ctx, ppy=4):
    """One fee stream's NET income for engine period q ($). Full six-axis GUT evaluator.

    Axis 1 Basis:        balance | transaction | account | flat | event
    Axis 2 Driver source: constant | own_balance | managed_notional | stream_ref | bank_aggregate
    Axis 3 Trajectory:    flat | proportional | ramp_to_target | explicit_schedule | derived
    Axis 4 Rate:          flat | annual_change | scheduled | tiered
    Axis 5 Timing:        start_period | end_period | ramp_in_periods
    Axis 6 Cost:          none | per_unit | pct_of_revenue

    ctx supplies: own_balance, managed_notional (rolled AUC), stream_qty (map: name->driver
    quantity of already-evaluated streams, for stream_ref), and bank_aggregate (map: e.g.
    total_deposits/total_assets, prior-quarter to avoid circularity).
    Unsupported basis/source/trajectory/rate/cost values fail closed with ValueError.
    """
    if not stream:
        return 0.0, 0.0
    _validate_fee_stream_shape(stream)
    tm = stream.get("timing") or {}
    start = int(tm.get("start_period") or 1)
    end = tm.get("end_period")
    if q < start or (end is not None and q > int(end)):
        return 0.0, 0.0
    basis = stream.get("basis")
    drv = stream.get("driver") or {}
    rt = stream.get("rate") or {}
    params = drv.get("params") or {}
    rate_params = rt.get("params") or {}

    # ---- Axis 2 + 3: driver quantity ----
    src = drv.get("source") or "constant"
    traj = drv.get("trajectory") or "flat"
    base = float(params.get("base") or 0.0)

    def _driver_growth():
        if params.get("growth_per_period") is not None:
            return float(params.get("growth_per_period") or 0.0)
        from .timebase import quarterly_value_to_period
        return quarterly_value_to_period("growth", float(params.get("growth_q") or 0.0), ppy)

    def _driver_growth_multiplier():
        if params.get("growth_spec"):
            from .growth import growth_multiplier
            return growth_multiplier(params.get("growth_spec"), current_period=q,
                                     start_period=1, ppy=ppy,
                                     context=(ctx or {}).get("growth_context"),
                                     base_position="period1")
        return (1.0 + _driver_growth()) ** (q - 1)

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
            qty = base * _driver_growth_multiplier()
        elif traj == "explicit_schedule":
            qty = float((params.get("schedule") or {}).get(str(q), base))
        else:
            qty = base
    else:
        # sourced quantity (own_balance/managed_notional/stream_ref/bank_aggregate)
        if traj == "derived":
            # Explicit natural-period coefficient = FLOW semantics (e.g. 4 turns / Year,
            # 24% of AUC / Year), periodized BEFORE a transaction fee/spread is applied.
            # Absence of the marker preserves legacy raw `multiple`/`pct` behavior exactly.
            coef = params.get("coefficient")
            if coef is not None:
                qty = sb * _fee_coefficient_value(coef, q, ppy, ctx)
            else:
                mult = params.get("multiple")
                pct = params.get("pct")
                if mult is not None:
                    qty = sb * float(mult)
                elif pct is not None:
                    qty = sb * float(pct)
                else:
                    qty = sb
        elif traj == "proportional":
            qty = sb * _driver_growth_multiplier()
        else:
            qty = sb  # flat/ramp_to_target already baked into the source stock

    # expose this stream's driver quantity for downstream stream_ref consumers
    nm = stream.get("name")
    if nm and isinstance(ctx, dict):
        ctx.setdefault("stream_qty", {})[nm] = qty

    # ---- Axis 1 + 4: basis application with rate behavior ----
    eff_rate = _fee_rate_q(rt, q, qty, ppy)
    gross = 0.0
    if basis == "balance":
        if eff_rate is None:  # tiered on balance
            gross = _apply_tiers(rate_params.get("tiers"), qty) / float(ppy)
        else:
            gross = qty * eff_rate / float(ppy)
    elif basis == "transaction":
        if eff_rate is None:
            gross = _apply_tiers(rate_params.get("tiers"), qty)
        else:
            per_unit = float(rate_params.get("per_unit") or 0.0)
            gross = qty * per_unit
    elif basis == "account":
        # New explicit natural-unit contract. Legacy `fee_per_period` remains $/account/MONTH
        # when the marker is absent; `periods_per_q` is intentionally ignored/retired so cadence
        # is always derived from ppy rather than a stale quarterly-authored override.
        unit_fee = rate_params.get("unit_fee")
        if unit_fee is not None:
            fee_one_engine_period = _fee_amount_per_engine_period(
                (unit_fee or {}).get("value"), (unit_fee or {}).get("period"), ppy)
        else:
            fee_one_engine_period = float(rate_params.get("fee_per_period") or 0.0) * (12.0 / float(ppy))
        gross = qty * fee_one_engine_period
    elif basis == "flat":
        flat_amount = rate_params.get("flat_amount")
        if flat_amount is not None:
            gross = _fee_amount_per_engine_period(
                (flat_amount or {}).get("value"), (flat_amount or {}).get("period"), ppy)
        else:
            # Legacy contract: amount_per_period is already an engine-period amount.
            gross = float(rate_params.get("amount_per_period") or 0.0)
    elif basis == "event":
        at = params.get("at_period")
        amt = float(rate_params.get("amount") or params.get("amount") or 0.0)
        gross = amt if (at is not None and int(at) == q) else 0.0
    else:
        raise ValueError(f"unsupported fee basis: {basis!r}")

    # ---- Axis 5: ramp-in phase (revenue phases in over K periods after start) ----
    ramp_in = tm.get("ramp_in_periods")
    if ramp_in:
        k = int(ramp_in)
        if k > 0:
            gross *= min(1.0, (q - start + 1) / k)

    # ---- Axis 6: cost side ----
    # Two economically distinct cost types:
    #  - per_unit  : an OPERATING cost (cost to process each unit, e.g. payment-rail
    #    network fees). Reported GROSS -> routed to noninterest EXPENSE (overhead),
    #    NOT netted against fee income. Netting would misstate Schedule RI (gross fee
    #    income and gross opex are reported separately) and the efficiency ratio.
    #  - pct_of_revenue : a CONTRA-REVENUE / revenue share (a cut of THIS fee owed
    #    away). Correctly NETS against the fee, because it reduces the revenue itself.
    # Returns (income, opcost): income is the fee line; opcost lands in overhead.
    cost = stream.get("cost") or {}
    ck = cost.get("kind") or "none"
    cp = cost.get("params") or {}
    opcost = 0.0
    if ck == "per_unit" and basis == "transaction":
        opcost = qty * float(cp.get("cost_per_unit") or 0.0)   # -> overhead (gross)
    elif ck == "pct_of_revenue":
        gross -= gross * float(cp.get("pct") or 0.0)           # -> nets (contra-revenue)

    return gross, opcost


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


def product_fee_streams_q(p, q, ctx, ppy=4):
    """A product's fee_streams for engine period q, as (fee_income, operating_cost) in $.
    Evaluated in dependency order so stream_ref consumers see their source's quantity.
    operating_cost (per_unit costs) routes to overhead; pct_of_revenue already netted
    into fee_income. Empty/absent => (0.0, 0.0) (hash-safe)."""
    streams = p.get("fee_streams") or []
    if not streams:
        return 0.0, 0.0
    ctx = dict(ctx or {})
    ctx.setdefault("stream_qty", {})
    try:
        order = fee_streams_order(streams)
    except ValueError:
        # fail-closed: a cyclic config contributes nothing rather than looping/guessing
        raise
    inc_total = 0.0
    cost_total = 0.0
    for i in order:
        _inc, _cost = fee_stream_q(streams[i], q, ctx, ppy)
        inc_total += _inc
        cost_total += _cost
    return inc_total, cost_total


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
