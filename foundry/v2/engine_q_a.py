"""Foundry v2 — quarterly balance-driven projection engine, profile A semantics.

Balance-driven product instances (deposits, lending, OBS) projected over a
12-quarter horizon with: forward rate path (fixed/floating pricing), reserve-
maintenance ALLL, originate-to-sell warehouse cohorts with MSR capitalization,
fair-value election via DCF, NOL-carryforward taxation, an iteratively solved
funding waterfall with a cash floor, and downturn overlay scenarios.

Deterministic, fail-closed, dollars in / dollars out. Pure Python.
"""

Q = 12
FV_HORIZON = 60


def opex_fixed_q(p):
    """Fixed operating cost per QUARTER for a product.

    Canonical key is `opex_fixed_q` (quarterly). Legacy configs stored `opex_fixed_m` (monthly,
    which the engine used to multiply by 3); those are still read correctly here by converting
    monthly -> quarterly. This read-time fallback is the safety net: even a config that was never
    migrated is interpreted with the right magnitude. `opex_fixed_q` wins when both are present.
    """
    if "opex_fixed_q" in p and p["opex_fixed_q"] is not None:
        return p["opex_fixed_q"] or 0.0
    return (p.get("opex_fixed_m") or 0.0) * 3.0


def rate_fn(path_q, longer_run):
    """Quarterly annual-rate lookup; glides 5bp/qtr toward longer_run past the end of path_q."""
    n = len(path_q)                     # horizon = length of the provided path (not a global)
    def r(t):
        if t < 1:
            t = 1
        if t <= n:
            return path_q[t - 1]
        last = path_q[n - 1]
        step = 0.0005 * (t - n)
        if last > longer_run:
            return max(longer_run, last - step)
        return min(longer_run, last + step)
    return r


def _ovq(p, field, q, base):
    m = (p.get("overrides") or {}).get(field) or {}
    v = m.get(str(q))
    return float(v) if v is not None else base


def _prod_rate(p, t, rate):
    # Read strictly gated by rate_type (the selector), never by field-presence: a product's
    # inactive rate field may persist in the config, and the type — not which field happens to
    # exist — decides what the engine reads. yield_ann for fixed lending, rate_paid_ann for fixed
    # deposits; both fall back to each other only as a legacy convenience.
    if p.get("rate_type") == "float":
        # Multi-curve dispatch: a floating product may name an index (sofr|effr|prime). The curve
        # set is carried as an attribute on the passed-in rate fn (set in the engine). When the
        # product names no index, or names one with no curve available, fall back to the passed
        # rate fn — which is SOFR — preserving pre-multi-curve behavior exactly (backward compat).
        idx = p.get("index")
        curves = getattr(rate, "_curves", None)
        rfn = curves.get(idx) if (curves and idx in curves) else rate
        return rfn(t) + _ovq(p, "index_spread", t, p.get("index_spread", 0.0) or 0.0)
    if p.get("yield_ann") is not None:
        return _ovq(p, "yield_ann", t, p.get("yield_ann") or 0.0)
    return _ovq(p, "rate_paid_ann", t, p.get("rate_paid_ann") or 0.0)


def _fv_of(p, q, bal, rate, is_asset):
    """DCF fair value of the existing book at end of quarter q."""
    if bal <= 0:
        return 0.0
    decay = (p.get("runoff_q", 0.0) if is_asset else p.get("fv_decay_q", 0.10)) or 0.0
    co_rate = (p.get("charge_off_ann", 0.0) / 4.0) if is_asset else 0.0
    b, pv, df = bal, 0.0, 1.0
    for t in range(1, FV_HORIZON + 1):
        rc = _prod_rate(p, q + t, rate) / 4.0
        rd = (rate(q + t) + p.get("discount_spread_ann", 0.0)) / 4.0
        interest = b * rc
        principal = b * decay
        co = b * co_rate
        df /= (1.0 + rd)
        pv += (interest + principal) * df
        b -= (principal + co)
        if b < 1e-7:
            b = 0.0
            break
    pv += b * df
    return pv


def _apply_overlays(lend, dep, a, ov):
    """Downturn overlays: credit multipliers, rate shock, volume/GOS/MSR/sale-share."""
    shock = (ov.get("rate_shock_bp", 0) or 0) / 10000.0
    if shock:
        a["cash_yield"] = max(0.0, a["cash_yield"] + shock)
        a["securities_yield"] = max(0.0, a["securities_yield"] + shock)
        a["borrow_rate_ann"] = max(0.0, a["borrow_rate_ann"] + shock)
        a["rate_path_q"] = [max(0.0, x + shock) for x in a["rate_path_q"]]
        a["rate_path_longer_run"] = max(0.0, a["rate_path_longer_run"] + shock)
    co_m = ov.get("charge_off_mult", 1) or 1
    res_m = ov.get("reserve_mult", 1) or 1
    # DFAST severe overlay: an ABSOLUTE per-call_report_line 9Q-cumulative loss rate that
    # SUBSTITUTES for the product's own charge-off over the 9-quarter supervisory window, via
    # a per-quarter override (quarters 1-9). This is a different mechanism from charge_off_mult
    # (which scales) — they never both run for the same scenario. Unmapped lines are untouched
    # here and fall back to the client's own rate. Level spread: per-quarter = cumulative / 9.
    dfast = ov.get("dfast_severe_rates") or {}
    dfast_spread = ov.get("dfast_spread") or "level"   # "level" | "front"
    # Front-loaded weights over the 9Q window: losses cluster early in a real downturn then fade.
    # Weights sum to 1.0; the per-quarter charge-off is w_q * cum9, converted to an annual rate
    # (x4) the engine consumes. Level = equal 1/9 each quarter (reproduces cum9 over the window).
    if dfast_spread == "front":
        _w = [0.18, 0.16, 0.14, 0.12, 0.11, 0.09, 0.08, 0.07, 0.05]  # sums to 1.00, monotone fade
    else:
        _w = [1.0 / 9.0] * 9
    for p in lend:
        if dfast and p.get("call_report_line") in dfast:
            cum9 = dfast[p["call_report_line"]]          # 9Q cumulative loss fraction
            # per-quarter charge-off rate q = w_q * cum9; engine reads an ANNUAL rate (co = bal*ann/4),
            # so ann_q = 4 * w_q * cum9. Over the 9Q window sum(co) ~ cum9 * balance (constant bal).
            sched = {str(q): 4.0 * _w[q - 1] * cum9 for q in range(1, 10)}
            p.setdefault("overrides", {})["charge_off_ann"] = sched
        else:
            p["charge_off_ann"] = (p.get("charge_off_ann") or 0.0) * co_m
        if p.get("reserve_rate_pct_bal") is not None:
            p["reserve_rate_pct_bal"] *= res_m
        p["originations_q"] = (p.get("originations_q") or 0.0) * (1 - (ov.get("origination_volume_haircut", 0) or 0))
        mb = p.get("mortgage_banking")
        if mb:
            if "gain_on_sale_margin" in mb:
                mb["gain_on_sale_margin"] *= (1 - (ov.get("gos_margin_compression", 0) or 0))
            if "msr_cap_rate_pct_upb" in mb:
                mb["msr_cap_rate_pct_upb"] *= (1 - (ov.get("msr_value_haircut", 0) or 0))
            if "sale_pct_of_orig" in mb:
                mb["sale_pct_of_orig"] *= (1 - (ov.get("sale_share_retention_shift", 0) or 0))


def run_pf_a(cfg):
    a = {k: (list(v) if isinstance(v, list) else v) for k, v in cfg["assumptions"].items()}
    # Authoritative projection horizon: read from config (default 12 = the historical quarterly horizon).
    # This local Q shadows the module constant so every Q-reference below honors the chosen horizon; a
    # config without n_periods reproduces the 12-period numbers byte-identically. rate_fn is already
    # horizon-independent (it derives from len(path_q)), so the rate path glides past its end as needed.
    Q = int((cfg.get("assumptions") or {}).get("n_periods") or 12)
    import copy
    lend = copy.deepcopy(a.get("lending_products") or [])
    # Originate-to-sell normalization. The engine reads the sale config under the `mortgage_banking`
    # key (historical name). A product may instead carry the product-neutral `originate_to_sell` block;
    # normalize it into `mortgage_banking` so all downstream reads are unchanged. Backward-compat is
    # exact: a product with `mortgage_banking` and no `originate_to_sell` is left byte-identical, and
    # `sale_timing` defaults to "at_origination" (the historical behavior). MSR fields default to 0
    # when absent (off-mortgage products), matching the prior `.get(...,0)` reads.
    for _p in lend:
        _ots = _p.get("originate_to_sell")
        if _ots and not _p.get("mortgage_banking"):
            _mb = {
                "sale_pct_of_orig": _ots.get("sale_pct", _ots.get("sale_pct_of_orig", 0.0)) or 0.0,
                "gain_on_sale_margin": _ots.get("gain_on_sale_margin", 0.0) or 0.0,
                "warehouse_hold_q": int(_ots.get("warehouse_hold_q", 0) or 0),
                "servicing_retained_pct": _ots.get("servicing_retained_pct", 0.0) or 0.0,
                "servicing_fee_bp_ann": _ots.get("servicing_fee_bp_ann", 0.0) or 0.0,
                "msr_cap_rate_pct_upb": _ots.get("msr_cap_rate_pct_upb", 0.0) or 0.0,
                "msr_decay_q": _ots.get("msr_decay_q", 0.0) or 0.0,
                # new: seasoning-based sale. "at_origination" reproduces historical behavior.
                "sale_timing": _ots.get("sale_timing", "at_origination"),
                "season_q": int(_ots.get("season_q", 0) or 0),
            }
            _p["mortgage_banking"] = _mb
    dep = copy.deepcopy(a.get("deposit_products") or [])
    obs = copy.deepcopy(a.get("obs_exposures") or [])
    afs_p = copy.deepcopy(a.get("securities_afs") or [])
    htm_p = copy.deepcopy(a.get("securities_htm") or [])
    ov = cfg.get("scenario_overlays")
    if ov:
        _apply_overlays(lend, dep, a, ov)

    # Multi-curve rate set (SOFR / EFFR / Prime). Backward-compat shim: the SOFR curve is built from
    # the legacy rate_path_q so index-less products (which dispatch to SOFR in _prod_rate) reproduce
    # the pre-multi-curve numbers exactly. EFFR/Prime use their own explicit paths when present; when
    # absent they fall back to a conventional offset off SOFR (a seed default, NOT a formula — once a
    # real path is fetched/entered it is used verbatim). Offsets: EFFR ≈ SOFR − 5bp; Prime ≈ SOFR +
    # ~2.92% (WSJ convention target+300bp, expressed off the ~8bp-below-target SOFR proxy).
    def _curve_paths(a):
        rc = a.get("rate_curves") or {}
        sofr_p = (rc.get("sofr") or {}).get("path_q") or a["rate_path_q"]
        sofr_lr = (rc.get("sofr") or {}).get("longer_run",
                    a.get("rate_path_longer_run", 0.0)) if rc.get("sofr") else a.get("rate_path_longer_run", 0.0)
        def _seed(off):
            return ([x + off for x in sofr_p], sofr_lr + off)
        effr = rc.get("effr") or {}
        prime = rc.get("prime") or {}
        effr_p, effr_lr = (effr.get("path_q"), effr.get("longer_run")) if effr.get("path_q") else _seed(-0.0005)
        prime_p, prime_lr = (prime.get("path_q"), prime.get("longer_run")) if prime.get("path_q") else _seed(0.0292)
        return {"sofr": (sofr_p, sofr_lr), "effr": (effr_p, effr_lr), "prime": (prime_p, prime_lr)}

    _cp = _curve_paths(a)
    rate_curves = {k: rate_fn(p, lr) for k, (p, lr) in _cp.items()}
    rate = rate_curves["sofr"]     # default curve
    rate._curves = rate_curves     # _prod_rate reads p['index'] off this to dispatch per-product

    capital = cfg["target_state"]["initial_capital"]
    # staged capital raises (additive, default-off): raises land at the START
    # of their stated quarter; the waterfall absorbs the cash side via plug()
    _raises = cfg["assumptions"].get("capital_raises") or []
    cap_t = [capital] * (Q + 1)
    for _r in _raises:
        for _q in range(int(_r["quarter"]), Q + 1):
            cap_t[_q] += float(_r["amount"])
    from .income_modules import (nie_detail_series, product_fee_streams_q,
                                 durbin_effective_rate, _g,
                                 managed_notional_series)
    from .cac_feeder import cac_managed_notional
    from .regparams import REG_PARAMS as _RP
    _nie_d = nie_detail_series(a)
    # Scheduled (term) borrowings are modeled as BULLET advances: the full draw is
    # held flat for `term_q` quarters (outstanding q0 .. q0+term_q-1), then matures to
    # zero. This is what an FHLB term advance actually is, and it corrects both anchor
    # artifacts: Patrick held it flat but never matured it (dead maturity input);
    # Roman carries no such instrument. Interest is full-quarter on the outstanding
    # principal (amount*rate/4) each quarter it is alive — a term advance is a discrete
    # lump-sum draw, not a ramping balance, so it is NOT averaged like balance-driven
    # products, and it accrues no interest after maturity. See ENGINE_SPEC "Scheduled
    # borrowings". term_q = quarters to maturity (bullet), not an amortization term.
    _sched = a.get("scheduled_borrowings") or []
    sched_t = [0.0] * (Q + 1)
    for _sb in _sched:
        _amt, _q0, _tq = float(_sb["amount"]), int(_sb["quarter"]), int(_sb["term_q"])
        for _q in range(_q0, min(_q0 + _tq, Q + 1)):
            sched_t[_q] += _amt
    sched_int_t = [0.0] * (Q + 1)
    for _sb in _sched:
        _amt, _q0, _tq, _r = float(_sb["amount"]), int(_sb["quarter"]), int(_sb["term_q"]), float(_sb["rate_ann"])
        for _q in range(_q0, min(_q0 + _tq, Q + 1)):
            sched_int_t[_q] += _amt * _r / 4.0
    _dep_q = float(a.get("premises_depreciation_annual") or 0.0) / 4.0
    prem_t = [max(0.0, a["premises_equipment"] - _dep_q * q) for q in range(Q + 1)]
    dep_exp_t = [0.0] + [prem_t[q - 1] - prem_t[q] for q in range(1, Q + 1)]
    non_earn_t = [prem_t[q] + a["intangibles"] + a["other_assets"] for q in range(Q + 1)]
    non_earn = non_earn_t[0]
    cash_floor = a["cash_target_pct_deposits"]
    other_liab = a["other_liabilities"]

    # deliberate securities books (A.6): balance path with purchases and runoff;
    # HTM income at its own fixed coupon — the rate shock (applied above to the
    # path and treasury yields) does not touch it. That is what HTM means.
    for p in afs_p + htm_p:
        bal = [p.get("opening", 0.0) or 0.0]
        for _q in range(1, Q + 1):
            bal.append(max(0.0, bal[-1] * (1 + (p.get("growth_q") or 0.0) - (p.get("runoff_q") or 0.0))
                           + (p.get("purchases_q") or 0.0)))
        p["_bal"] = bal
        p["_avg"] = [None] + [(bal[i - 1] + bal[i]) / 2.0 for i in range(1, Q + 1)]

    # ---- per-product projection ----
    for p in lend + dep + obs:
        p["_bal"] = [p.get("opening_balance", p.get("notional", 0.0)) or 0.0]
        p["_avg"] = [None]
        p["_ii"] = [None]; p["_ie"] = [None]; p["_fee"] = [None]; p["_ox"] = [None]
        p["_fcost"] = [None]
    for p in lend:
        p["_co"] = [None]; p["_alll"] = [0.0]; p["_orig"] = [None]
        p["_sold"] = [0.0]; p["_wh"] = [0.0]; p["_whc"] = [0.0]; p["_gos"] = [None]
        p["_upb"] = [0.0]; p["_msr"] = [0.0]; p["_scap"] = [None]; p["_samort"] = [None]
        p["_sfee"] = [None]; p["_snet"] = [None]
        p["_is_fv"] = p.get("measurement") == "fair_value"
        mb = p.get("mortgage_banking") or {}
        p["_sale"] = mb.get("sale_pct_of_orig", 0.0) or 0.0
        p["_alll"][0] = 0.0 if p["_is_fv"] else p["_bal"][0] * (p.get("reserve_rate_pct_bal") or 0.0)

    for p in dep + obs:
        # managed notional (off-book AUC/AUM) for fee products; empty => zeros (hash-safe)
        # managed_notional: inline on the product, OR sourced from a named CAC feed
        # (assumptions.cac_feeds[name]) so multiple products share ONE customer-driven AUC.
        _mn_cfg = p.get("managed_notional")
        _src = p.get("managed_notional_source")
        if _src:
            _feed = (a.get("cac_feeds") or {}).get(_src)
            if _feed is not None:
                _mn_cfg = cac_managed_notional(_feed, Q)
        _mn_avg, _mn_end = managed_notional_series(_mn_cfg, Q)
        p["_mn_end"] = _mn_end
        # term products: average maturity (months -> quarters, quarterly clock)
        # drives cohort roll-OFF — deposits exit when their cohort matures.
        # The opening balance is a seasoned even ladder (1/mq exits per quarter);
        # each quarter's inflows form a cohort that exits whole at +mq.
        _mq = int(round((p.get("avg_maturity_m") or 0.0) / 3.0))
        _cohorts = {}          # born_q -> remaining balance
        if _mq > 0 and (p["_bal"][0] or 0.0) > 0:
            for _k in range(1, _mq + 1):
                _cohorts[_k - _mq] = p["_bal"][0] / _mq   # ages 1.._mq
        for q in range(1, Q + 1):
            beg = p["_bal"][q - 1]
            growth_amt = beg * _ovq(p, "growth_q", q, p.get("growth_q") or 0.0)
            runoff_rt = _ovq(p, "runoff_q", q, p.get("runoff_q") or 0.0)
            new_abs = _ovq(p, "new_deposits_q", q, p.get("new_deposits_q") or 0.0)
            if _mq > 0:
                for _b in _cohorts: _cohorts[_b] *= max(0.0, 1 - runoff_rt)
                matured = _cohorts.pop(q - _mq, 0.0)
                inflow = max(0.0, growth_amt + new_abs)
                if inflow > 0: _cohorts[q] = _cohorts.get(q, 0.0) + inflow
                end = max(0.0, sum(_cohorts.values()))
                _ = matured  # exits the balance sheet; no other effect
            else:
                end = max(0.0, beg * (1 + _ovq(p, "growth_q", q, p.get("growth_q") or 0.0)
                                      - runoff_rt) + new_abs)
            avg = (beg + end) / 2.0
            r = _prod_rate(p, q, rate) if "rate_type" in p else 0.0
            p["_bal"].append(end); p["_avg"].append(avg)
            p["_ii"].append(0.0)
            p["_ie"].append(avg * r / 4.0 if p in dep else 0.0)
            _pf_inc, _pf_cost = product_fee_streams_q(p, q, {"own_balance": avg,
                                                            "managed_notional": _mn_avg[q - 1]})
            p["_fee"].append(avg * (p.get("fee_yield_ann") or 0.0) / 4.0 + _pf_inc)
            p["_ox"].append(avg * (p.get("opex_pct_ann") or 0.0) / 4.0 + opex_fixed_q(p))
            p.setdefault("_fcost", [None]).append(_pf_cost)   # fee-stream op cost: NIE, post-gross-up

    for p in lend:
        mb = p.get("mortgage_banking") or {}
        h = int(mb.get("warehouse_hold_q", 0) or 0)
        # Originate-to-sell timing. "at_origination" (default/historical): a fraction is designated for
        # sale at origination and warehoused briefly (the mortgage/SBA path below via p["_sale"]).
        # "after_seasoning": the account is HELD (earning, reserved) for season_q quarters, THEN a
        # fraction of the seasoned cohort is sold at a gain. For after_seasoning nothing is sold at
        # origination, so p["_sale"] stays 0 and the warehouse path stays dormant; the seasoned sale is
        # handled by its own cohort tracker below and reduces the ending balance in the sale quarter.
        _sale_timing = mb.get("sale_timing", "at_origination")
        _season_sale = (_sale_timing == "after_seasoning") and (mb.get("sale_pct_of_orig", 0.0) or 0.0) > 0
        if _season_sale:
            p["_sale"] = 0.0                                   # nothing sold at origination
            _sq = int(mb.get("season_q", 0) or 0)
            _spct = mb.get("sale_pct_of_orig", 0.0) or 0.0
            _smargin = mb.get("gain_on_sale_margin", 0.0) or 0.0
            _scoh = []                                         # [balance, age] origination cohorts
            if (p["_bal"][0] or 0.0) > 0:
                _scoh.append([p["_bal"][0], 0])
        # Level-payment amortization for TERM products (structure=='term' with a maturity). Each cohort
        # (the opening book, then each quarter's retained originations) amortizes on a constant-payment
        # schedule over term_q quarters and is gone at maturity. When not a term product, _amort stays
        # False and the flat-runoff path below runs UNCHANGED (byte-identical for every existing config).
        _amort = (p.get("structure") == "term") and int(p.get("term_q") or 0) > 0
        if _amort:
            _T = int(p["term_q"])
            # cohorts: list of [remaining_balance, quarters_elapsed]. Opening book is a seasoned even
            # ladder — treat it as one cohort at age 0 amortizing over its remaining term (approximation:
            # the opening book amortizes over a full term from Day 1; refined seasoning is a later item).
            _coh = []
            if (p["_bal"][0] or 0.0) > 0:
                _coh.append([p["_bal"][0], 0])
        for q in range(1, Q + 1):
            beg = p["_bal"][q - 1]
            r = _prod_rate(p, q, rate)
            co = beg * _ovq(p, "charge_off_ann", q, p.get("charge_off_ann") or 0.0) / 4.0
            o = _ovq(p, "originations_q", q,
                     (p.get("originations_q") or 0.0) * (1 + (p.get("orig_growth_q") or 0.0)) ** (q - 1))
            retained = o * (1 - p["_sale"])
            p["_sold"].append(o * p["_sale"])
            if _amort:
                # amortize every living cohort one quarter (level payment), then add this quarter's
                # retained origination as a fresh cohort. Balance = sum of cohorts, less charge-offs.
                _i = max(0.0, r) / 4.0
                _next = []
                for _bal, _age in _coh:
                    _rem = _T - _age
                    if _rem <= 0 or _bal <= 0:
                        continue
                    if _i > 0:
                        _pay = _bal * _i / (1 - (1 + _i) ** (-_rem))
                        _princ = _pay - _bal * _i
                    else:
                        _princ = _bal / _rem
                    _nb = max(0.0, _bal - _princ)
                    if _nb > 1e-9 and (_age + 1) < _T:
                        _next.append([_nb, _age + 1])
                if retained > 0:
                    _next.append([retained, 0])
                _coh = _next
                gross = sum(_b for _b, _a in _coh)
                end = max(0.0, gross - co)
            else:
                end = max(0.0, beg + retained - beg * _ovq(p, "runoff_q", q, p.get("runoff_q") or 0.0) - co)
            # after_seasoning originate-to-sell: age cohorts; when one reaches season_q, sell sale_pct of
            # its current balance. Each cohort decays by the product's runoff_q (so the cohort sum tracks
            # the same paydown as the balance), then the sale removes principal and books a gain =
            # sold_balance * gain_on_sale_margin. New origination enters as a fresh cohort. The sold
            # amount is subtracted from `end` so the balance sheet reflects the sale.
            _season_gain_q = 0.0
            if _season_sale:
                _ro = _ovq(p, "runoff_q", q, p.get("runoff_q") or 0.0)
                _snext = []
                _sold_amt = 0.0
                for _b, _a in _scoh:
                    _bcur = _b * max(0.0, 1 - _ro)             # decay this cohort like the balance
                    _newage = _a + 1
                    if _newage == _sq and _bcur > 0:           # held season_q full quarters -> sell now
                        _sell = _bcur * _spct
                        _sold_amt += _sell
                        _season_gain_q += _sell * _smargin
                        _keep = _bcur - _sell
                        if _keep > 1e-9:
                            _snext.append([_keep, _newage])
                    elif _bcur > 1e-9:
                        _snext.append([_bcur, _newage])
                if retained > 0:
                    _snext.append([retained, 0])
                _scoh = _snext
                end = max(0.0, end - _sold_amt)
                p["_sold"][q] = p["_sold"][q] + _sold_amt      # report as sold volume this quarter
                p.setdefault("_season_gos", []).append(_season_gain_q)
            avg = (beg + end) / 2.0
            p["_bal"].append(end); p["_avg"].append(avg); p["_co"].append(co); p["_orig"].append(o)
            p["_ii"].append(avg * r / 4.0); p["_ie"].append(0.0)
            _pf_inc, _pf_cost = product_fee_streams_q(p, q, {"own_balance": avg})
            p["_fee"].append(avg * _ovq(p, "fee_yield_ann", q, p.get("fee_yield_ann") or 0.0) / 4.0 + _pf_inc)
            p["_ox"].append(avg * (p.get("opex_pct_ann") or 0.0) / 4.0 + opex_fixed_q(p))
            p.setdefault("_fcost", [None]).append(_pf_cost)   # fee-stream op cost: NIE, post-gross-up
            p["_alll"].append(0.0 if p["_is_fv"] else end * (p.get("reserve_rate_pct_bal") or 0.0))
        # warehouse cohorts: half-quarter coupon at origination and sale
        if p["_sale"] > 0:
            margin = mb.get("gain_on_sale_margin", 0.0) or 0.0
            for q in range(1, Q + 1):
                wh, wh_int, gos = 0.0, 0.0, 0.0
                rq = _prod_rate(p, q, rate)
                for j in range(max(1, q - h), q + 1):
                    cohort = p["_sold"][j]
                    if not cohort:
                        continue
                    if h == 0:
                        w = 0.5 if j == q else 0.0
                    elif j == q:
                        w = 0.5
                    elif q < j + h:
                        w = 1.0
                    elif q == j + h:
                        w = 0.5
                    else:
                        w = 0.0
                    wh_int += cohort * w * rq / 4.0
                    if q < j + h:
                        wh += cohort
                if p["_is_fv"]:
                    gos = p["_sold"][q] * margin
                elif q - h >= 1:
                    gos = p["_sold"][q - h] * margin
                p["_wh"].append(wh)
                p["_whc"].append(wh * (1 + (margin if p["_is_fv"] else 0.0)))
                p["_ii"][q] += wh_int
                p["_gos"].append(gos)
        else:
            _sgos = p.get("_season_gos") or []
            for q in range(1, Q + 1):
                p["_wh"].append(0.0); p["_whc"].append(0.0)
                p["_gos"].append(_sgos[q - 1] if q - 1 < len(_sgos) else 0.0)
        # servicing retained: MSR capitalized at settlement, amortized on decay
        srv = mb.get("servicing_retained_pct", 0.0) or 0.0
        if p["_sale"] > 0 and srv > 0:
            fee_bp = mb.get("servicing_fee_bp_ann", 0.0) or 0.0
            cap_rate = mb.get("msr_cap_rate_pct_upb", 0.0) or 0.0
            decay = mb.get("msr_decay_q", 0.0) or 0.0
            for q in range(1, Q + 1):
                settled = p["_sold"][q - h] if q - h >= 1 else 0.0
                add = settled * srv
                upb_beg = p["_upb"][q - 1]
                upb = max(0.0, upb_beg - upb_beg * decay + add)
                cap = add * cap_rate
                amort = p["_msr"][q - 1] * decay
                msr = max(0.0, p["_msr"][q - 1] + cap - amort)
                sfee = ((upb_beg + upb) / 2.0) * fee_bp / 10000.0 / 4.0
                p["_upb"].append(upb); p["_msr"].append(msr)
                p["_scap"].append(cap); p["_samort"].append(amort)
                p["_sfee"].append(sfee); p["_snet"].append(sfee - amort)
                p["_gos"][q] += cap
        else:
            for q in range(1, Q + 1):
                p["_upb"].append(0.0); p["_msr"].append(0.0)
                p["_scap"].append(0.0); p["_samort"].append(0.0)
                p["_sfee"].append(0.0); p["_snet"].append(0.0)
        # fair value of the existing book
        p["_fv"] = []; p["_fvadj"] = []
        for q in range(0, Q + 1):
            if p["_is_fv"]:
                fv = _fv_of(p, q, p["_bal"][q], rate, True)
                p["_fv"].append(fv); p["_fvadj"].append(fv - p["_bal"][q])
            else:
                p["_fv"].append(None); p["_fvadj"].append(0.0)

    # ---- aggregation ----
    def z():
        return [0.0] * (Q + 1)
    gross, alll_t, hfs, msr_t, deps_c, deps_b, obs_n = z(), z(), z(), z(), z(), z(), z()
    for q in range(0, Q + 1):
        for p in lend:
            carry = p["_bal"][q] + (p["_fvadj"][q] if p["_is_fv"] else 0.0)
            gross[q] += carry + p["_whc"][q]
            alll_t[q] += p["_alll"][q]
            hfs[q] += p["_whc"][q]
            msr_t[q] += p["_msr"][q]
        for p in dep:
            deps_c[q] += p["_bal"][q]
            deps_b[q] += p["_bal"][q]
        for p in obs:
            obs_n[q] += p["_bal"][q]

    ne_q = [0]
    def plug(dep_carry, dep_bal, net_loans_end, equity_end, msr_end, sec_books_end=0.0, ne=None):
        funding = dep_carry + other_liab + equity_end + sched_t[ne_q[0]]
        investable = funding - net_loans_end - (non_earn if ne is None else ne) - msr_end - sec_books_end
        req_cash = cash_floor * dep_bal
        if investable >= req_cash:
            return req_cash, investable - req_cash, 0.0
        return req_cash, 0.0, req_cash - investable

    day_one = sum(p["_fvadj"][0] for p in lend if p["_is_fv"])
    # pre-opening burn (Patrick I.9 convention, quarterly-converted at import):
    # organizational costs are EXPENSED into the opening deficit, not capitalized
    _po = cfg.get("pre_opening") or {}
    _burn = sum(float(e.get("total", 0.0)) for e in (_po.get("expenses") or []))
    day_one -= _burn
    net0 = gross[0] - alll_t[0]
    equity0 = capital + day_one
    sec_books0 = sum(p["_bal"][0] for p in afs_p + htm_p)
    ne_q[0] = 0
    c0, s0, b0 = plug(deps_c[0], deps_b[0], net0, equity0, 0.0, sec_books0, non_earn_t[0])

    bs = {k: z() for k in ("cash", "sec", "netLoans", "borrow", "equity", "re", "totalAssets",
                             "afsBook", "htmBook", "aoci", "paidIn")}
    bs["cash"][0], bs["sec"][0], bs["borrow"][0] = c0, s0, b0
    bs["netLoans"][0], bs["re"][0], bs["equity"][0] = net0, day_one, equity0
    bs["afsBook"][0] = sum(p["_bal"][0] for p in afs_p)
    bs["htmBook"][0] = sum(p["_bal"][0] for p in htm_p)
    bs["aoci"][0], bs["paidIn"][0] = 0.0, cap_t[0]
    _aoci_sens = float(a.get("aoci_sensitivity_annual") or 0.0)
    aoci_cum = 0.0
    bs["totalAssets"][0] = c0 + s0 + sec_books0 + net0 + non_earn

    isk = ("loanInt", "secInt", "bookInt", "cashInt", "depExp", "borrExp", "nii", "prov", "fees",
           "gos", "servNet", "fvPnl", "prodOpex", "overhead", "pretax", "tax", "ni", "nco", "nol")
    is_ = {k: [None] * (Q + 1) for k in isk}

    re, nol = day_one, 0.0
    # ---- tax_detail module (NOL -> DTA, ASC 740 presentation; OFF path is
    # byte-identical to the legacy shield-everything treatment) ----
    _td = a.get("tax_detail") or None
    if _td is not None and _td.get("enabled") is False:
        _td = None
    if _td:
        _td_lim = float(_td.get("nol_utilization_limit_pct",
                                  _RP["tax"]["nol_utilization_limit_pct"]))
        _td_va_mode = _td.get("va_mode", "auto")
        _td_va_pct = float(_td.get("va_pct", 0.0))
        for _k in ("taxCurrent", "taxDeferred", "dtaGross", "dtaVA", "dtaNet"):
            is_[_k] = [None] * (Q + 1)
        bs["dta"] = [0.0] * (Q + 1)
    _cum_taxable, _dta_prev = 0.0, 0.0
    # ---- credit_regime module (ASC 326 presentation): decomposes the SAME
    # provision into day-one (retained originations x lifetime EL rate),
    # reserve build/(release) on the existing book, and NCO replenishment.
    # No arithmetic changes anywhere - the decomposition is definitionally
    # additive and the totals are gated byte-identical (T62). ----
    _cr = a.get("credit_regime") or None
    if _cr is not None and _cr.get("enabled") is False:
        _cr = None
    if _cr:
        for _k in ("provDayOne", "provBuild", "provNCO"):
            is_[_k] = [None] * (Q + 1)
    for q in range(1, Q + 1):
        loan_int = sum(p["_ii"][q] for p in lend)
        dep_exp = sum(p["_ie"][q] for p in dep)
        fees = sum(p["_fee"][q] for p in lend + dep + obs)
        # Axis-7 (Durbin cap), GUT-native: interchange is a fee_streams product whose stream
        # declares rate.behavior == "durbin_capped". If PRIOR-quarter assets >= $10B, the
        # gross interchange rate is capped to the regulated cap. Applied HERE in the P&L loop
        # (not in fee_stream_q) because it needs prior-quarter total assets, which include
        # fee feedback and only exist post-P&L. Priced off prior-quarter assets to break the
        # interchange -> NI -> equity -> assets -> cap circularity. 12 CFR 235.3-235.4.
        _pa_k = (bs["totalAssets"][q - 1] / 1000.0) if q >= 1 else 0.0  # raw$ -> $000s
        for _p in lend + dep + obs:
            for _st in (_p.get("fee_streams") or []):
                if ((_st.get("rate") or {}).get("behavior")) != "durbin_capped":
                    continue
                _rp = (_st.get("rate") or {}).get("params") or {}
                _at = float(_rp.get("avg_ticket") or 0.0)
                _ar = float(_rp.get("rate") or 0.0)              # GROSS interchange rate
                _er = durbin_effective_rate(_ar, _at, _pa_k)
                if _er < _ar - 1e-15:
                    _dp = _st.get("driver") or {}
                    _dprm = _dp.get("params") or {}
                    _vol = _g(float(_dprm.get("base") or 0.0), _dprm.get("growth_q"), q)
                    _overage = _vol * _at * (_ar - _er)
                    fees -= _overage
                    is_.setdefault("durbinCap", [None] * (Q + 1))
                    is_["durbinCap"][q] = (is_["durbinCap"][q] or 0.0) + _overage
        prod_ox = sum(p["_ox"][q] for p in lend + dep + obs)
        nco = sum(p["_co"][q] for p in lend)
        gos = sum(p["_gos"][q] for p in lend)
        srv = sum(p["_snet"][q] for p in lend)
        fv_pnl = sum((p["_fvadj"][q] - p["_fvadj"][q - 1]) - p["_co"][q] for p in lend if p["_is_fv"])
        overhead = a["overhead_q"] * (1 + a.get("overhead_growth_q", 0.0)) ** (q - 1) + dep_exp_t[q]
        if _nie_d:
            # Patrick's NIE granularity (F-071): FTE-step comp + category lines +
            # assessments on the CORRECT base (D-P14 fix) + his sub*r/(1-r) gross-up.
            # Assessment RATES are engagement assumptions (12 CFR 327 schedule / 12 CFR 8):
            # read from the config's nie_detail block when set, else the REG_PARAMS default.
            _fdic_bp = _nie_d.get("fdic_bp_ann")
            if _fdic_bp is None:
                _fdic_bp = _RP["assessments"]["fdic_bp_ann"]
            _occ_bp = _nie_d.get("occ_bp_ann")
            if _occ_bp is None:
                _occ_bp = _RP["assessments"]["occ_bp_ann"]
            _avg_a_q = (bs["totalAssets"][q - 1] + 0.0) if q >= 1 else 0.0
            # avg assets this quarter approximated as (prior end + tentative end)/2 is
            # circular pre-plug; use prior end (disclosed) — assessments accrue on it
            _tang_eq = (bs["equity"][q - 1] - a["intangibles"])
            _fdic = max(0.0, _avg_a_q - _tang_eq) * float(_fdic_bp) / 10000.0 / 4.0
            _occ = _avg_a_q * float(_occ_bp) / 10000.0 / 4.0
            _sub = (_nie_d["comp"][q - 1] + _nie_d["categories"][q - 1]
                     + _fdic + _occ + dep_exp_t[q] + prod_ox)
            _r = _nie_d["gross_up_rate"]
            overhead = (_sub - prod_ox) + (_sub * _r / (1 - _r) if 0 < _r < 1 else 0.0)
        # fee-stream operating costs (e.g. payment-rail network fees): external
        # pass-through costs added to NIE POST gross-up (they are not internal
        # expenses that carry overhead-on-overhead), matching legacy _fees_m cost.
        overhead += sum((p.get("_fcost") or [None] * (Q + 1))[q] or 0.0 for p in lend + dep + obs)
        nie = prod_ox + overhead
        nco_ac = sum(p["_co"][q] for p in lend if not p["_is_fv"])
        prov = (alll_t[q] - alll_t[q - 1]) + nco_ac
        if _cr:
            _day1 = sum((p.get("reserve_rate_pct_bal") or 0.0)
                         * (p["_orig"][q] or 0.0) * (1.0 - (p.get("_sale") or 0.0))
                         for p in lend if not p["_is_fv"])
            is_["provDayOne"][q] = _day1
            is_["provNCO"][q] = nco_ac
            is_["provBuild"][q] = prov - _day1 - nco_ac
        net_loans_end = gross[q] - alll_t[q]
        sec_books_end = sum(p["_bal"][q] for p in afs_p + htm_p)
        book_int = sum(p["_avg"][q] * (p.get("yield_ann") or 0.0) / 4.0 for p in afs_p + htm_p)
        beg_c, beg_s, beg_b = bs["cash"][q - 1], bs["sec"][q - 1], bs["borrow"][q - 1]

        ni = 0.0
        _dta_iter = _dta_prev
        for _ in range(60):
            afs_end_b = sum(p["_bal"][q] for p in afs_p)
            aoci_q = afs_end_b * _aoci_sens / 4.0
            equity_end = cap_t[q] + re + ni + aoci_cum + aoci_q
            ne_q[0] = q
            c, s, b = plug(deps_c[q], deps_b[q], net_loans_end, equity_end, msr_t[q], sec_books_end,
                            non_earn_t[q] + (_dta_iter if _td else 0.0))
            sec_int = ((beg_s + s) / 2.0) * a["securities_yield"] / 4.0 + book_int
            cash_int = ((beg_c + c) / 2.0) * a["cash_yield"] / 4.0
            borr_exp = ((beg_b + b) / 2.0) * a["borrow_rate_ann"] / 4.0 + sched_int_t[q]
            nii = loan_int + sec_int + cash_int - dep_exp - borr_exp
            pretax = nii + fees + fv_pnl + gos + srv - nie - prov
            if _td:
                if pretax < 0:
                    _shield = 0.0
                    _current = 0.0
                    _nol_end = nol - pretax
                else:
                    _shield = min(nol, _td_lim * pretax)
                    _current = (pretax - _shield) * a["tax_rate"]
                    _nol_end = nol - _shield
                _dta_gross = _nol_end * a["tax_rate"]
                if _td_va_mode == "auto":
                    _va = _dta_gross if (_cum_taxable + pretax) < 0 else 0.0
                elif _td_va_mode == "pct":
                    _va = _dta_gross * _td_va_pct
                else:
                    _va = 0.0
                _dta_net = _dta_gross - _va
                _deferred = -(_dta_net - _dta_prev)
                tax = _current + _deferred
                _dta_iter = _dta_net
            else:
                taxable = max(0.0, pretax - nol)
                tax = taxable * a["tax_rate"]
            new_ni = pretax - tax
            if abs(new_ni - ni) < 1e-4:
                ni = new_ni
                break
            ni = new_ni
        if _td:
            nol = _nol_end
            _cum_taxable += pretax
            _dta_prev = _dta_net
            bs["dta"][q] = _dta_net
            for _k, _v in (("taxCurrent", _current), ("taxDeferred", _deferred),
                            ("dtaGross", _dta_gross), ("dtaVA", _va), ("dtaNet", _dta_net)):
                is_[_k][q] = _v
        elif pretax < 0:
            nol += -pretax
        else:
            nol = max(0.0, nol - pretax)
        re += ni

        bs["cash"][q], bs["sec"][q], bs["borrow"][q] = c, s, b
        aoci_cum += aoci_q
        bs["netLoans"][q], bs["re"][q] = net_loans_end, re
        bs["equity"][q] = cap_t[q] + re + aoci_cum
        bs["afsBook"][q] = afs_end_b
        bs["htmBook"][q] = sum(p["_bal"][q] for p in htm_p)
        bs["aoci"][q], bs["paidIn"][q] = aoci_cum, cap_t[q]
        bs["totalAssets"][q] = (c + s + sec_books_end + net_loans_end + non_earn_t[q] + msr_t[q]
                                  + (bs["dta"][q] if _td else 0.0))
        for k, v in (("loanInt", loan_int), ("secInt", sec_int), ("bookInt", book_int), ("cashInt", cash_int),
                     ("depExp", dep_exp), ("borrExp", borr_exp), ("nii", nii), ("prov", prov),
                     ("fees", fees), ("gos", gos), ("servNet", srv), ("fvPnl", fv_pnl),
                     ("prodOpex", prod_ox), ("overhead", overhead), ("pretax", pretax),
                     ("tax", tax), ("ni", ni), ("nco", nco), ("nol", nol)):
            is_[k][q] = v

    # ---- ratios (A.7): Tier 1 approx = equity - intangibles - MSA excess over the
    # 25%-of-Tier-1 threshold (12 CFR 3.22(d) simplification); deducted MSAs also
    # come out of average assets in the leverage denominator. ----
    ratios = {k: [None] * (Q + 1) for k in ("roa", "roe", "nim", "eff", "lev", "alllPct", "nco_rate")}
    for q in range(1, Q + 1):
        avg_a = (bs["totalAssets"][q - 1] + bs["totalAssets"][q]) / 2.0
        avg_e = (bs["equity"][q - 1] + bs["equity"][q]) / 2.0
        avg_earn = ((gross[q - 1] + gross[q]) / 2.0 + (bs["sec"][q - 1] + bs["sec"][q]) / 2.0
                    + (bs["cash"][q - 1] + bs["cash"][q]) / 2.0)
        ni_q = is_["ni"][q]
        ratios["roa"][q] = (ni_q * 4 / avg_a * 100) if avg_a > 0 else None
        ratios["roe"][q] = (ni_q * 4 / avg_e * 100) if avg_e > 0 else None
        ratios["nim"][q] = (is_["nii"][q] * 4 / avg_earn * 100) if avg_earn > 0 else None
        rev = is_["nii"][q] + is_["fees"][q] + is_["gos"][q] + is_["servNet"][q]
        ratios["eff"][q] = ((is_["prodOpex"][q] + is_["overhead"][q]) / rev * 100) if rev > 0 else None
        _dta_ded = (bs["dta"][q] * _RP["tax"]["dta_nol_cet1_deduction"]) if _td else 0.0
        t1 = bs["equity"][q] - a["intangibles"] - _dta_ded
        msr_x = max(0.0, msr_t[q] - 0.25 * max(0.0, t1))
        ratios["lev"][q] = ((t1 - msr_x) / (avg_a - msr_x - _dta_ded) * 100) if (avg_a - msr_x - _dta_ded) > 0 else None
        ratios["alllPct"][q] = (alll_t[q] / gross[q] * 100) if gross[q] > 0 else None
        # net charge-off rate: current-quarter net charge-offs annualized (x4) over
        # AVERAGE loans, matching the peer band's UBPR one-quarter-annualized basis
        # exactly (so a modeled value places like-for-like). Can be slightly negative
        # when recoveries exceed charge-offs — a genuinely good quarter, not an anomaly.
        avg_loans = (gross[q - 1] + gross[q]) / 2.0
        ratios["nco_rate"][q] = (is_["nco"][q] * 4 / avg_loans * 100) if avg_loans > 0 else None

    products = []
    for fam, plist in (("lending", lend), ("deposit", dep), ("obs", obs)):
        for p in plist:
            def _s(key):
                return [p[key][q] for q in range(1, Q + 1)] if p.get(key) else None
            products.append({
                "name": p.get("name"), "family": fam,
                "line": p.get("call_report_line"),
                "rate_type": p.get("rate_type", "fixed"),
                "index_spread": p.get("index_spread"),
                "is_fv": bool(p.get("_is_fv")),
                "sale_pct": p.get("_sale", 0.0),
                "serv_retained": (p.get("mortgage_banking") or {}).get("servicing_retained_pct", 0.0) if fam == "lending" else 0.0,
                "bal": [(p["_bal"][q] + (p["_fvadj"][q] if p.get("_is_fv") else 0.0)
                         if fam == "lending" else p["_bal"][q]) for q in range(0, Q + 1)],
                "rateQ": [_prod_rate(p, q, rate) * 100 for q in range(1, Q + 1)] if fam != "obs" else None,
                "intInc": _s("_ii"), "intExp": _s("_ie"),
                "origq": _s("_orig"), "soldOrig": _s("_sold"), "whCarry": _s("_whc"),
                "whBal": _s("_wh"),
                "servUPB": _s("_upb"), "msrCap": _s("_scap"), "msrAmort": _s("_samort"),
                "msrBal": _s("_msr"), "alll": _s("_alll"),
                "fv": ([p["_fv"][q] for q in range(1, Q + 1)] if p.get("_is_fv") else None),
                "fvAdj": ([p["_fvadj"][q] for q in range(1, Q + 1)] if p.get("_is_fv") else None),
                "avg": [p["_avg"][q] for q in range(1, Q + 1)],
                "interest": [(p["_ii"][q] - p["_ie"][q]) for q in range(1, Q + 1)],
                "fees": [p["_fee"][q] for q in range(1, Q + 1)],
                "opex": [p["_ox"][q] for q in range(1, Q + 1)],
                "passCost": [((p.get("_fcost") or [None]*(Q+1))[q] or 0.0) for q in range(1, Q + 1)],
                "co": [(p["_co"][q] if "_co" in p else 0.0) for q in range(1, Q + 1)],
                "gos": [(p["_gos"][q] if p.get("_gos") else 0.0) for q in range(1, Q + 1)],
                "servNet": [(p["_snet"][q] if p.get("_snet") else 0.0) for q in range(1, Q + 1)],
                "ftp_rate": [rate(q) for q in range(1, Q + 1)],
            })
    return {"products": products,
            "ratios": {k: v[1:] for k, v in ratios.items()},
            "bs": {"cash": bs["cash"], "sec": bs["sec"], "netLoans": bs["netLoans"],
                   "grossLoans": gross, "alll": alll_t, "hfs": hfs, "msr": msr_t,
                   "borrow": bs["borrow"], "deposits": deps_c, "equity": bs["equity"],
                   "re": bs["re"], "totalAssets": bs["totalAssets"],
                   "afsBook": bs["afsBook"], "htmBook": bs["htmBook"],
                   "aoci": bs["aoci"], "paidIn": bs["paidIn"],
                   "premises": prem_t, "borrowSched": sched_t,
                   **({"dta": bs["dta"]} if _td else {})},
            "is": {k: v[1:] for k, v in is_.items()}}
