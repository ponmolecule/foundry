"""Wave 3 (FLOOR F-036/070/071/072/141/142/143): income granularity.

Pure functions from config to engine-period series ($ dollars), consumed by BOTH
engines. Everything is additive and default-off: absent config => empty series.

NIE detail (F-071/072, fixing D-P14 and D-R8):
  assumptions.nie_detail = {
    "fte_by_year": [y1, y2, y3], "loaded_comp_annual": $,
    "categories": [{"name": str, "flow_spec": {trajectory, value/values, period, ...}}, ...],
    # legacy per_period/per_quarter categories remain readable unchanged
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
    _cat_economic = [nie_category_series(c, Q, ppy, growth_context=growth_context) for c in _catlist]

    # Recognition timing is a separate axis from the economic expense trajectory.  Rebucket the
    # entered economic path into ordinal model periods before any cash-settlement accounting is
    # computed.  Endogenous linked components cannot yet be forecast across future recurrence
    # blocks, so custom recognition for those components fails closed below.
    from .opex_extensions import (resolve_linked_components, resolve_recognition,
                                  normalize_recognition, resolve_settlement, normalize_settlement,
                                  recognition_spec_for_category)
    _cat_recognition_specs = [recognition_spec_for_category(c, ppy) for c in _catlist]
    _cat_series = [resolve_recognition(arr, rec, ppy, context=growth_context)
                   for arr, rec in zip(_cat_economic, _cat_recognition_specs)]
    cats = [float(sum(arr[i] for arr in _cat_series)) for i in range(Q)]

    # Optional advanced Opex mechanics. Linked components are evaluated later in the engine after
    # whitelisted upstream metrics for that period are known. Custom recognition/settlement
    # is limited to the pre-resolvable entered category path; forecasting a future endogenous linked
    # charge across recurrence blocks is a different contract and therefore fails closed.
    _linked = []
    _sett_pre = [0.0] * Q
    _sett_acc = [0.0] * Q
    _sett_cash = [0.0] * Q
    for _ci, (_c, _arr) in enumerate(zip(_catlist, _cat_series)):
        _lc = resolve_linked_components(_c, Q, ppy, context=growth_context)
        _rec = recognition_spec_for_category(_c, ppy)
        _sett = normalize_settlement(_c.get("settlement"), ppy)
        _linked_recognition_ok = (_rec["mode"] == "trajectory" or
                                  (_rec["mode"] == "monthly" and int(_rec.get("first_period") or 1) == 1))
        if _lc and not _linked_recognition_ok:
            raise ValueError(
                f"Operating Expense category {_c.get('name') or _ci + 1!r}: delayed/custom recognition "
                "cannot be combined with linked revenue components; use recognition=trajectory")
        if _lc and _sett["mode"] not in {"recognition", "monthly"}:
            raise ValueError(
                f"Operating Expense category {_c.get('name') or _ci + 1!r}: custom settlement "
                "cannot be combined with linked revenue components; use settlement=recognition")
        if _lc:
            _linked.extend({**x, "category_index": _ci} for x in _lc)
        _sr = resolve_settlement(_arr, _sett, ppy, context=growth_context)
        for _i in range(Q):
            _sett_pre[_i] += _sr["prepaid"][_i]
            _sett_acc[_i] += _sr["accrued"][_i]
            _sett_cash[_i] += _sr["cash"][_i]
    return {"comp": comp, "categories": cats, "linked_components": _linked,
             "settlement_prepaid": _sett_pre, "settlement_accrued": _sett_acc,
             "settlement_cash": _sett_cash,
             "gross_up_rate": float(nd.get("other_gross_up_rate") or 0.0),
             # Assessment-rate overrides (engagement assumptions). None -> engine falls back to
             # the REG_PARAMS default, so an untouched config's assessments are byte-identical.
             "fdic_bp_ann": (float(nd["fdic_bp_ann"]) if nd.get("fdic_bp_ann") is not None else None),
             "occ_bp_ann": (float(nd["occ_bp_ann"]) if nd.get("occ_bp_ann") is not None else None),
             "occ_payment_first_period": (int(nd["occ_payment_first_period"])
                                          if nd.get("occ_payment_first_period") is not None else None)}



def nie_category_series(c, Q, ppy=4, growth_context=None):
    """Resolve one Operating Expense category to its native-period dollar flow.

    New Configuration authoring uses ``flow_spec`` so the amount owns its natural
    Month / Quarter / Year unit independently of computational cadence.  Legacy
    ``per_period`` / ``per_quarter`` configs retain their exact historic behavior when
    ``flow_spec`` is absent.

    Public helper for safe cross-module Foundry-series links.  It is intentionally the
    same resolver used by ``nie_detail_series`` so a linked CAC spend path cannot drift
    from the expense actually modeled on the income statement.
    """
    from .timebase import quarterly_value_to_period
    Q, ppy = int(Q), int(ppy)
    c = c or {}
    if c.get("flow_spec") is not None:
        from .periodic_flows import resolve_periodic_flow
        # r61 deliberately does not treat flow_spec.start_period as a second Opex timing axis.
        # Saved r60 configs are migrated through recognition_spec_for_category instead.
        fs = dict(c.get("flow_spec") or {})
        fs.pop("start_period", None)
        return resolve_periodic_flow(fs, Q, ppy, context=growth_context)

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


def simple_overhead_series(a, Q, ppy=4, growth_context=None):
    """Resolve the Configuration Simple-overhead recurring flow, excluding depreciation.

    ``overhead_flow_spec`` is the opt-in natural-period contract.  In its absence the
    historical per-engine-period fields are preserved exactly for backward compatibility.
    """
    a = a or {}
    Q, ppy = int(Q), int(ppy)
    if a.get("overhead_flow_spec") is not None:
        from .periodic_flows import resolve_periodic_flow
        return resolve_periodic_flow(a.get("overhead_flow_spec"), Q, ppy, context=growth_context)

    from .timebase import quarterly_value_to_period
    if a.get("overhead_per_period") is not None:
        base = float(a.get("overhead_per_period") or 0.0)
    else:
        base = quarterly_value_to_period("overhead", float(a.get("overhead_q") or 0.0), ppy)
    if a.get("overhead_growth_spec"):
        from .growth import resolve_growth_series
        return resolve_growth_series(base, a.get("overhead_growth_spec"), Q, ppy,
                                     context=growth_context)
    if a.get("overhead_growth_per_period") is not None:
        g = float(a.get("overhead_growth_per_period") or 0.0)
    else:
        g = quarterly_value_to_period("overhead_growth", float(a.get("overhead_growth_q") or 0.0), ppy)
    return [base * ((1.0 + g) ** (q - 1)) for q in range(1, Q + 1)]

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


def _fee_rate_q(rt, q, base_qty, ppy=4, ctx=None):
    """Axis 4 (rate behavior), including opt-in Series-style rate paths.

    Legacy ``annual_change`` / model-period ``scheduled`` / ``tiered`` behavior is
    preserved exactly.  New balance-rate authoring may opt into ``params.rate_path``
    with Flat / Growth / Explicit natural-period level semantics.
    """
    behavior = (rt or {}).get("behavior") or "flat"
    rp = (rt or {}).get("params") or {}
    if behavior == "cost_recovery":
        # Dimensionless markup on a native-period cost flow.  This is deliberately a
        # level path, not an annualized fee rate and not a natural-period coefficient.
        # ``markup_pct`` is accepted as the compact scalar form; new UI authoring uses
        # the Series-capable ``markup`` object.
        if rp.get("markup") is not None:
            return _fee_level_path_value(
                rp.get("markup"), q, ppy, ctx, rp.get("markup_pct") or 0.0)
        return float(rp.get("markup_pct") or 0.0)
    if rp.get("rate_path") is not None:
        if behavior != "flat":
            raise ValueError("fee rate_path requires rate.behavior='flat'")
        return _fee_level_path_value(rp.get("rate_path"), q, ppy, ctx, rp.get("rate") or 0.0)
    r0 = float(rp.get("rate") or 0.0)
    if behavior == "annual_change":
        yr = (q - 1) // ppy                      # 0 in year 1, 1 in year 2, ...
        delta = float(rp.get("annual_delta") or 0.0)
        return r0 * ((1.0 + delta) ** yr)
    if behavior == "scheduled":
        sched = rp.get("schedule") or {}         # {model period: rate}
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
_FEE_SOURCES = {"constant", "own_balance", "managed_notional", "stream_ref", "bank_aggregate", "cost_pool"}
_FEE_TRAJECTORIES = {"flat", "proportional", "ramp_to_target", "explicit_schedule", "derived"}
_FEE_RATE_BEHAVIORS = {"flat", "annual_change", "scheduled", "tiered", "durbin_capped", "cost_recovery"}
_FEE_COST_KINDS = {"none", "per_unit", "pct_of_revenue", "pct_of_revenue_opex"}
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


def _fee_level_schedule_value(spec, q, ppy, default=0.0):
    """Resolve explicit natural-period END-OF-PERIOD levels to an engine-period average.

    Fee levels such as mandate counts, reserve percentages, and annualized fee rates are
    stocks/levels, not flows.  To keep economics cadence-stable, Foundry first resolves
    their EOP path on a conceptual monthly grid, then averages those monthly levels into
    the model period (month / quarter / year).  Thus the same annual EOP schedule produces
    the same annual fee economics in monthly and quarterly models.

    ``step`` holds the prior EOP level until the next endpoint month; ``smooth`` linearly
    interpolates between endpoints. No rounding is applied. The first supplied anchor is
    held through its first natural period because no earlier opening anchor was supplied.
    """
    spec = dict(spec or {})
    period = str(spec.get("period") or "").strip().lower()
    if period not in _FEE_NATURAL_PERIODS - {"model_period"}:
        raise ValueError(f"unsupported fee level schedule period: {period!r}")
    resolution = str(spec.get("resolution") or "step").strip().lower()
    if resolution not in {"step", "smooth"}:
        raise ValueError(f"unsupported fee level schedule resolution: {resolution!r}")
    schedule = spec.get("schedule") or {}
    if not isinstance(schedule, dict) or not schedule:
        raise ValueError("fee level explicit_schedule requires at least one schedule value")

    ppy = int(ppy)
    if ppy not in (1, 4, 12):
        raise ValueError(f"unsupported cadence periods_per_year={ppy}")
    width_months = {"year": 12, "quarter": 3, "month": 1}[period]
    engine_width_months = 12 // ppy

    def _month_level(month_index):
        idx = (int(month_index) - 1) // width_months + 1
        cur = _fee_schedule_value(schedule, idx, default)
        if idx <= 1:
            return cur
        prev = _fee_schedule_value(schedule, idx - 1, default)
        pos = (int(month_index) - 1) % width_months + 1
        if resolution == "step":
            return cur if pos == width_months else prev
        frac = pos / float(width_months)
        return prev + (cur - prev) * frac

    first_month = (int(q) - 1) * engine_width_months + 1
    vals = [_month_level(first_month + j) for j in range(engine_width_months)]
    return sum(vals) / float(len(vals))


def _fee_level_path_value(spec, q, ppy, ctx=None, default=0.0):
    """Resolve a scalar level path (Flat / Growth / Explicit) without periodization.

    Used for economic *levels* such as account counts, stock multipliers, and annualized
    fee-rate assumptions.  Explicit schedules are natural-period END-OF-PERIOD anchors
    and may resolve Step or Smooth.  Unlike flow coefficients and recurring dollar
    amounts, level values are not divided by the model cadence.
    """
    spec = dict(spec or {})
    traj = str(spec.get("trajectory") or "flat").strip().lower()
    if traj not in {"flat", "growth", "explicit_schedule"}:
        raise ValueError(f"unsupported fee level trajectory: {traj!r}")
    val = float(spec.get("value") if spec.get("value") is not None else default or 0.0)
    if traj == "growth":
        gs = spec.get("growth_spec")
        if not gs:
            raise ValueError("fee level growth trajectory requires growth_spec")
        from .growth import growth_multiplier
        val *= growth_multiplier(gs, current_period=int(q), start_period=1, ppy=int(ppy),
                                 context=(ctx or {}).get("growth_context"), base_position="period1")
    elif traj == "explicit_schedule":
        ls = dict(spec)
        # Some level paths (notably account unit fees) separate the billing unit from
        # the trajectory's source cadence.  Default to `period` for simple paths.
        ls["period"] = str(spec.get("path_period") or spec.get("period") or "year")
        val = _fee_level_schedule_value(ls, q, ppy, val)
    return val


def _fee_flat_amount_value(spec, q, ppy, ctx=None):
    """Resolve a recurring Flat-basis amount into one engine-period dollar amount.

    ``spec.value`` is stated in the selected natural ``period`` (Month / Quarter / Year).
    ``trajectory`` controls how that recurring amount itself changes through time:

    - flat: hold ``value`` constant;
    - growth: grow ``value`` using a standard Foundry ``growth_spec``;
    - explicit_schedule: use natural-period schedule points, carrying the last value forward.

    This contract is opt-in through ``rate.params.flat_amount``.  Legacy
    ``amount_per_period`` continues to bypass this helper so old configs remain exact.
    """
    spec = dict(spec or {})
    period = str(spec.get("period") or "").strip().lower()
    if period not in _FEE_NATURAL_PERIODS - {"model_period"}:
        raise ValueError(f"unsupported flat amount period: {period!r}")
    traj = str(spec.get("trajectory") or "flat").strip().lower()
    if traj not in {"flat", "growth", "explicit_schedule"}:
        raise ValueError(f"unsupported flat amount trajectory: {traj!r}")
    val = float(spec.get("value") or 0.0)
    if traj == "growth":
        gs = spec.get("growth_spec")
        if not gs:
            raise ValueError("flat amount growth trajectory requires growth_spec")
        from .growth import growth_multiplier
        val *= growth_multiplier(gs, current_period=int(q), start_period=1, ppy=int(ppy),
                                 context=(ctx or {}).get("growth_context"), base_position="period1")
    elif traj == "explicit_schedule":
        schedule = spec.get("schedule") or {}
        if not isinstance(schedule, dict):
            raise ValueError("flat amount explicit_schedule requires a mapping")
        idx = _fee_natural_period_index(q, period, ppy)
        val = _fee_schedule_value(schedule, idx, val)
    return _fee_amount_per_engine_period(val, period, ppy)


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
        "transaction": {"flat", "tiered", "durbin_capped", "cost_recovery"},
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
    if src == "cost_pool":
        if basis != "transaction":
            raise ValueError("fee cost_pool source is supported only on transaction basis")
        if traj != "flat":
            raise ValueError("fee cost_pool source follows its native-period flow and requires driver.trajectory='flat'")
        if not str(drv.get("ref") or "").strip():
            raise ValueError("fee cost_pool source requires driver.ref")
        if rb != "cost_recovery":
            raise ValueError("fee cost_pool source requires rate.behavior='cost_recovery'")
    if rb == "cost_recovery":
        if basis != "transaction" or src != "cost_pool":
            raise ValueError("fee rate behavior 'cost_recovery' requires transaction basis with driver.source='cost_pool'")
        if ck != "none":
            raise ValueError("cost_recovery streams must use cost.kind='none'; linked source expenses are observational and already posted upstream")
        try:
            recovery = float((rt.get("params") or {}).get("recovery_pct") or 0.0)
        except (TypeError, ValueError):
            raise ValueError("cost_recovery requires numeric recovery_pct")
        if recovery < 0.0 or recovery > 1.0:
            raise ValueError("cost_recovery recovery_pct must be between 0 and 1")
        crp = rt.get("params") or {}
        try:
            scalar_markup = float(crp.get("markup_pct") or 0.0)
        except (TypeError, ValueError):
            raise ValueError("cost_recovery markup_pct must be numeric")
        if scalar_markup < -1.0:
            raise ValueError("cost_recovery markup_pct must be >= -1")
        if crp.get("markup") is not None:
            mp = dict(crp.get("markup") or {})
            mtraj = str(mp.get("trajectory") or "flat").strip().lower()
            if mtraj not in {"flat", "growth", "explicit_schedule"}:
                raise ValueError(f"unsupported cost_recovery markup trajectory: {mtraj!r}")
            try:
                mval = float(mp.get("value") or 0.0)
            except (TypeError, ValueError):
                raise ValueError("cost_recovery markup value must be numeric")
            if mval < -1.0:
                raise ValueError("cost_recovery markup value must be >= -1")
            if mtraj == "growth" and not mp.get("growth_spec"):
                raise ValueError("cost_recovery markup growth trajectory requires growth_spec")
            if mtraj == "explicit_schedule":
                if str(mp.get("period") or "").strip().lower() not in _FEE_NATURAL_PERIODS - {"model_period"}:
                    raise ValueError(f"unsupported cost_recovery markup period: {mp.get('period')!r}")
                if str(mp.get("resolution") or "step").strip().lower() not in {"step", "smooth"}:
                    raise ValueError(f"unsupported cost_recovery markup resolution: {mp.get('resolution')!r}")
                sched = mp.get("schedule")
                if not isinstance(sched, dict) or not sched:
                    raise ValueError("cost_recovery explicit markup requires at least one schedule value")
                try:
                    vals = [float(v) for v in sched.values()]
                except (TypeError, ValueError):
                    raise ValueError("cost_recovery markup schedule values must be numeric")
                if any(v < -1.0 for v in vals):
                    raise ValueError("cost_recovery markup schedule values must be >= -1")
    if ck == "per_unit" and basis != "transaction":
        raise ValueError("fee cost kind 'per_unit' is supported only on transaction basis")
    if ck in {"pct_of_revenue", "pct_of_revenue_opex"}:
        try:
            _pct = float((cost.get("params") or {}).get("pct") or 0.0)
        except (TypeError, ValueError):
            raise ValueError(f"fee cost kind {ck!r} requires numeric pct")
        if _pct < 0.0 or _pct > 1.0:
            raise ValueError(f"fee cost kind {ck!r} pct must be between 0 and 1")
    coef = (drv.get("params") or {}).get("coefficient")
    level_schedule = (drv.get("params") or {}).get("level_schedule")
    stock_multiplier = (drv.get("params") or {}).get("stock_multiplier")
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
    if level_schedule is not None:
        if traj != "explicit_schedule":
            raise ValueError("fee level_schedule requires driver.trajectory='explicit_schedule'")
        if src != "constant":
            raise ValueError("fee level_schedule is supported only for constant/entered drivers")
        ls = dict(level_schedule or {})
        if str(ls.get("period") or "").strip().lower() not in _FEE_NATURAL_PERIODS - {"model_period"}:
            raise ValueError(f"unsupported fee level schedule period: {ls.get('period')!r}")
        if str(ls.get("resolution") or "step").strip().lower() not in {"step", "smooth"}:
            raise ValueError(f"unsupported fee level schedule resolution: {ls.get('resolution')!r}")
        if not isinstance(ls.get("schedule"), dict) or not ls.get("schedule"):
            raise ValueError("fee level explicit_schedule requires at least one schedule value")
    if stock_multiplier is not None:
        if basis != "balance" or traj != "derived" or src == "constant":
            raise ValueError("fee stock_multiplier requires a sourced balance driver with trajectory='derived'")
        sm = dict(stock_multiplier or {})
        if str(sm.get("kind") or "").strip().lower() != "pct":
            raise ValueError(f"unsupported fee stock multiplier kind: {sm.get('kind')!r}")
        smtraj = str(sm.get("trajectory") or "flat").strip().lower()
        if smtraj not in {"flat", "growth", "explicit_schedule"}:
            raise ValueError(f"unsupported fee stock multiplier trajectory: {smtraj!r}")
        try:
            float(sm.get("value") or 0.0)
        except (TypeError, ValueError):
            raise ValueError("fee stock multiplier value must be numeric")
        if smtraj == "growth" and not sm.get("growth_spec"):
            raise ValueError("fee stock multiplier growth trajectory requires growth_spec")
        if smtraj == "explicit_schedule":
            if str(sm.get("period") or "").strip().lower() not in _FEE_NATURAL_PERIODS - {"model_period"}:
                raise ValueError(f"unsupported fee stock multiplier period: {sm.get('period')!r}")
            if str(sm.get("resolution") or "step").strip().lower() not in {"step", "smooth"}:
                raise ValueError(f"unsupported fee stock multiplier resolution: {sm.get('resolution')!r}")
            if not isinstance(sm.get("schedule"), dict) or not sm.get("schedule"):
                raise ValueError("fee stock multiplier explicit_schedule requires at least one schedule value")
    rp = (rt.get("params") or {})
    if rp.get("rate_path") is not None:
        if basis != "balance" or rb != "flat":
            raise ValueError("fee rate_path is supported only on balance basis with rate.behavior='flat'")
        rpath = dict(rp.get("rate_path") or {})
        rtraj = str(rpath.get("trajectory") or "flat").strip().lower()
        if rtraj not in {"flat", "growth", "explicit_schedule"}:
            raise ValueError(f"unsupported fee rate trajectory: {rtraj!r}")
        try:
            float(rpath.get("value") or 0.0)
        except (TypeError, ValueError):
            raise ValueError("fee rate path value must be numeric")
        if rtraj == "growth" and not rpath.get("growth_spec"):
            raise ValueError("fee rate growth trajectory requires growth_spec")
        if rtraj == "explicit_schedule":
            if str(rpath.get("period") or "").strip().lower() not in _FEE_NATURAL_PERIODS - {"model_period"}:
                raise ValueError(f"unsupported fee rate path period: {rpath.get('period')!r}")
            if str(rpath.get("resolution") or "step").strip().lower() not in {"step", "smooth"}:
                raise ValueError(f"unsupported fee rate path resolution: {rpath.get('resolution')!r}")
            if not isinstance(rpath.get("schedule"), dict) or not rpath.get("schedule"):
                raise ValueError("fee rate explicit_schedule requires at least one schedule value")
    if basis == "account" and rp.get("unit_fee") is not None:
        uf = rp.get("unit_fee") or {}
        if str(uf.get("period") or "").strip().lower() not in _FEE_NATURAL_PERIODS - {"model_period"}:
            raise ValueError(f"unsupported account fee period: {uf.get('period')!r}")
        utraj = str(uf.get("trajectory") or "flat").strip().lower()
        if utraj not in {"flat", "growth", "explicit_schedule"}:
            raise ValueError(f"unsupported account fee trajectory: {utraj!r}")
        try:
            float(uf.get("value") or 0.0)
        except (TypeError, ValueError):
            raise ValueError("account unit_fee value must be numeric")
        if utraj == "growth" and not uf.get("growth_spec"):
            raise ValueError("account fee growth trajectory requires growth_spec")
        if utraj == "explicit_schedule":
            upath = str(uf.get("path_period") or uf.get("period") or "").strip().lower()
            if upath not in _FEE_NATURAL_PERIODS - {"model_period"}:
                raise ValueError(f"unsupported account fee path period: {upath!r}")
            if str(uf.get("resolution") or "step").strip().lower() not in {"step", "smooth"}:
                raise ValueError(f"unsupported account fee resolution: {uf.get('resolution')!r}")
            if not isinstance(uf.get("schedule"), dict) or not uf.get("schedule"):
                raise ValueError("account fee explicit_schedule requires at least one schedule value")
    if basis == "flat" and rp.get("flat_amount") is not None:
        fa = rp.get("flat_amount") or {}
        if str(fa.get("period") or "").strip().lower() not in _FEE_NATURAL_PERIODS - {"model_period"}:
            raise ValueError(f"unsupported flat amount period: {fa.get('period')!r}")
        ftraj = str(fa.get("trajectory") or "flat").strip().lower()
        if ftraj not in {"flat", "growth", "explicit_schedule"}:
            raise ValueError(f"unsupported flat amount trajectory: {ftraj!r}")
        if ftraj == "growth" and not fa.get("growth_spec"):
            raise ValueError("flat amount growth trajectory requires growth_spec")
        if ftraj == "explicit_schedule":
            fsched = fa.get("schedule")
            if not isinstance(fsched, dict) or not fsched:
                raise ValueError("flat amount explicit_schedule requires at least one schedule value")
        try:
            float(fa.get("value") or 0.0)
        except (TypeError, ValueError):
            raise ValueError("flat_amount value must be numeric")
    return True


def fee_stream_q(stream, q, ctx, ppy=4):
    """One fee stream's NET income for engine period q ($). Full six-axis GUT evaluator.

    Axis 1 Basis:        balance | transaction | account | flat | event
    Axis 2 Driver source: constant | own_balance | managed_notional | stream_ref | bank_aggregate | cost_pool
    Axis 3 Trajectory:    flat | proportional | ramp_to_target | explicit_schedule | derived
    Axis 4 Rate:          flat | annual_change | scheduled | tiered | durbin_capped | cost_recovery
    Axis 5 Timing:        start_period | end_period | ramp_in_periods
    Axis 6 Cost:          none | per_unit | pct_of_revenue | pct_of_revenue_opex

    ctx supplies: own_balance, managed_notional (rolled AUC), stream_qty (map: name->driver
    quantity of already-evaluated streams, for stream_ref), bank_aggregate (map: e.g.
    total_deposits/total_assets, prior-quarter to avoid circularity), and cost_pool
    (map: stable pool ID -> native-period eligible expense flow).
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
        if src == "cost_pool":
            ref = str(drv.get("ref") or "").strip()
            pools = (ctx or {}).get("cost_pool") or {}
            if not ref or ref not in pools:
                raise ValueError(f"fee cost_pool source {ref!r} is unavailable in evaluator context")
            return float(pools[ref] or 0.0)
        return base  # constant

    sb = _source_base()
    if src == "constant":
        if traj == "proportional":
            qty = base * _driver_growth_multiplier()
        elif traj == "explicit_schedule":
            if params.get("level_schedule") is not None:
                qty = _fee_level_schedule_value(params.get("level_schedule"), q, ppy, base)
            else:
                # Legacy contract: explicit schedule keys are model-period numbers.
                qty = float((params.get("schedule") or {}).get(str(q), base))
        else:
            qty = base
    else:
        # sourced quantity (own_balance/managed_notional/stream_ref/bank_aggregate/cost_pool)
        if traj == "derived":
            # Explicit natural-period coefficient = FLOW semantics (e.g. 4 turns / Year,
            # 24% of AUC / Year), periodized BEFORE a transaction fee/spread is applied.
            # Absence of the marker preserves legacy raw `multiple`/`pct` behavior exactly.
            coef = params.get("coefficient")
            stock_multiplier = params.get("stock_multiplier")
            if stock_multiplier is not None:
                sm = dict(stock_multiplier or {})
                qty = sb * _fee_level_path_value(sm, q, ppy, ctx, 0.0)
            elif coef is not None:
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

    # Expose this stream's driver quantity for downstream stream_ref consumers and, when
    # explicitly requested by the engine, as a stable read-only cross-module Series. The latter
    # is observational only: Opex may consume the resolved quantity but never owns/recalculates it.
    nm = stream.get("name")
    if nm and isinstance(ctx, dict):
        ctx.setdefault("stream_qty", {})[nm] = qty
    if isinstance(ctx, dict):
        sid = str(stream.get("quantity_series_id") or "").strip()
        cap = ctx.get("capture_stream_qty")
        if sid and isinstance(cap, dict):
            arr = cap.setdefault(sid, [])
            while len(arr) < int(q):
                arr.append(0.0)
            arr[int(q) - 1] = float(qty or 0.0)

    # ---- Axis 1 + 4: basis application with rate behavior ----
    eff_rate = _fee_rate_q(rt, q, qty, ppy, ctx)
    gross = 0.0
    if basis == "balance":
        if eff_rate is None:  # tiered on balance
            gross = _apply_tiers(rate_params.get("tiers"), qty) / float(ppy)
        else:
            gross = qty * eff_rate / float(ppy)
    elif basis == "transaction":
        if (rt.get("behavior") or "flat") == "cost_recovery":
            recovery = float(rate_params.get("recovery_pct") or 0.0)
            markup = float(eff_rate or 0.0)
            gross = qty * recovery * (1.0 + markup)
        elif eff_rate is None:
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
            uf = dict(unit_fee or {})
            fee_level = _fee_level_path_value(uf, q, ppy, ctx, uf.get("value") or 0.0)
            fee_one_engine_period = _fee_amount_per_engine_period(
                fee_level, uf.get("period"), ppy)
        else:
            fee_one_engine_period = float(rate_params.get("fee_per_period") or 0.0) * (12.0 / float(ppy))
        gross = qty * fee_one_engine_period
    elif basis == "flat":
        flat_amount = rate_params.get("flat_amount")
        if flat_amount is not None:
            gross = _fee_flat_amount_value(flat_amount, q, ppy, ctx)
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
    # Three economically distinct cost types:
    #  - per_unit  : an OPERATING cost (cost to process each unit, e.g. payment-rail
    #    network fees). Reported GROSS -> routed to noninterest EXPENSE (fee product costs),
    #    NOT netted against fee income. Netting would misstate Schedule RI (gross fee
    #    income and gross opex are reported separately) and the efficiency ratio.
    #  - pct_of_revenue : a CONTRA-REVENUE / revenue share (a cut of THIS fee owed
    #    away). Correctly NETS against the fee, because it reduces the revenue itself.
    #  - pct_of_revenue_opex : an OPERATING expense stated as a percentage of gross
    #    fee revenue. Gross fee income remains intact and the cost routes to NIE.
    # Returns (income, opcost): income is the fee line; opcost lands in fee-product NIE.
    cost = stream.get("cost") or {}
    ck = cost.get("kind") or "none"
    cp = cost.get("params") or {}
    opcost = 0.0
    if ck == "per_unit" and basis == "transaction":
        opcost = qty * float(cp.get("cost_per_unit") or 0.0)   # -> fee-product NIE (gross)
    elif ck == "pct_of_revenue":
        gross -= gross * float(cp.get("pct") or 0.0)           # -> nets (contra-revenue)
    elif ck == "pct_of_revenue_opex":
        opcost = gross * float(cp.get("pct") or 0.0)           # -> fee-product NIE; gross income preserved

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
