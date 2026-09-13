"""Foundry v2 — quarterly balance-driven projection engine, profile B semantics.

Distinctives vs profile A: per-period override vectors on any driver; deliberate
AFS and HTM securities books plus a surplus-liquidity sweep (HTM never reprices);
expected-loss provisioning separate from charge-offs with an entity ALLL floor
true-up; beginning-of-quarter accrual on treasury balances; taxes on positive
pre-tax income only (no DTA). Deterministic, dollars in / dollars out.
"""

Q = 12


def _ov(p, field, q, base):
    """1-based per-quarter override lookup; blank -> baseline."""
    m = (p.get("overrides") or {}).get(field) or {}
    v = m.get(str(q))
    return float(v) if v is not None else base


def run_pf_b(cfg):
    import copy
    a = copy.deepcopy(cfg["assumptions"])
    lend = copy.deepcopy(a.get("lending_products") or [])
    dep = copy.deepcopy(a.get("deposit_products") or [])
    obs = copy.deepcopy(a.get("obs_exposures") or [])
    afs_p = copy.deepcopy(a.get("securities_afs") or [])
    htm_p = copy.deepcopy(a.get("securities_htm") or [])

    # Profile B is intentionally quarterly-only, but it still participates in the
    # same public scenario/rate contract as Profile A. Apply the common overlay and
    # common floating-rate dispatch rather than silently ignoring them.
    from .engine_q_a import (_apply_overlays, _build_rate_curve_set, _prod_rate, opex_fixed_q)
    if cfg.get("scenario_overlays"):
        _apply_overlays(lend, dep, a, cfg["scenario_overlays"], 4)
    _curves = _build_rate_curve_set(a, cfg, 4)
    _rate = _curves["sofr"]
    from .growth import growth_context_from_cfg
    _growth_ctx = growth_context_from_cfg(cfg, 4)
    from .cac_feeder import cac_auc_rollforward
    _auc_month_sources = {}
    _auc_beginning_sources = {}
    for _feed_name, _feed_cfg in (a.get("cac_feeds") or {}).items():
        _feed_key = str((_feed_cfg or {}).get("series_id") or _feed_name or "").strip()
        if not _feed_key:
            continue
        _cacr = cac_auc_rollforward(_feed_cfg or {}, Q, 4, assumptions=a, growth_context=_growth_ctx)
        _auc_month_sources[_feed_key] = list(_cacr.get("auc_end_by_month") or [])
        _auc_beginning_sources[_feed_key] = float((_feed_cfg or {}).get("beginning_auc") or 0.0)
    from .income_modules import simple_overhead_series
    _simple_overhead = simple_overhead_series(a, Q, 4, _growth_ctx)
    # Cost pools are shared non-posting native-period flows. Profile B does not yet use
    # first-class Fee Product cost-pool pricing, but Operating Expense is a valid consumer.
    from .cost_pools import cost_pool_series_map
    _cost_pool_series = cost_pool_series_map(a, Q, 4, growth_context=_growth_ctx)

    from .timebase import event_start_period

    capital = cfg["target_state"]["initial_capital"]
    _raises = cfg["assumptions"].get("capital_raises") or []
    cap_t = [capital] * (Q + 1)
    for _r in _raises:
        _q0 = event_start_period(_r, 4)
        for _q in range(_q0, Q + 1):
            cap_t[_q] += float(_r["amount"])
    from .income_modules import nie_detail_series
    from .regparams import REG_PARAMS as _RP
    _nie_d = nie_detail_series(a, 4, _growth_ctx)
    from .opex_extensions import linked_component_amount
    from .workforce import resolve_workforce_additive_components, workforce_additive_component_amount
    _wf_cfg = ((a.get("nie_detail") or {}).get("workforce") or {})
    _wf_add_components = resolve_workforce_additive_components(_wf_cfg, 4) if _nie_d else []
    _wf_comp_native, _wf_role_comp_native, _wf_additive_comp_native = [], [], []
    _wf_additive_component_native = [[] for _ in _wf_add_components]
    _opex_static_pre = list((_nie_d or {}).get("settlement_prepaid") or [0.0] * Q)
    _opex_static_acc = list((_nie_d or {}).get("settlement_accrued") or [0.0] * Q)
    _occ_half_amt = 0.0
    _occ_signed_balance = 0.0
    # Scheduled (term) borrowings: BULLET advance — full draw held flat for `term_q`
    # quarters, then matures to zero; full-quarter interest on outstanding principal,
    # no averaging, no post-maturity accrual. Must match engine_q_a exactly (parity
    # gate). See ENGINE_SPEC "Scheduled borrowings".
    _schedb = a.get("scheduled_borrowings") or []
    _sched_t = [0.0] * (Q + 1)
    _sched_int = [0.0] * 12
    for _sb in _schedb:
        _amt, _q0, _tq, _r = float(_sb["amount"]), event_start_period(_sb, 4), int(_sb["term_q"]), float(_sb["rate_ann"])
        for _q in range(_q0, min(_q0 + _tq, Q + 1)):
            _sched_t[_q] += _amt
            _sched_int[_q - 1] += _amt * _r / 4.0
    from .fixed_assets import fixed_asset_mode, fixed_asset_schedule
    if fixed_asset_mode(a) == "schedule":
        _fa = fixed_asset_schedule(a.get("fixed_assets"), Q, 4)
        _prem_t = _fa["net"]
        _prem_gross_t = _fa["gross"]
        _prem_accum_t = _fa["accumulated_depreciation"]
        _dep_exp = _fa["depreciation_expense"][1:]
        _capex_t = _fa["capex"]
    else:
        _dep_q = float(a.get("premises_depreciation_annual") or 0.0) / 4.0
        _prem_t = [max(0.0, a["premises_equipment"] - _dep_q * q) for q in range(Q + 1)]
        _dep_exp = [_prem_t[q - 1] - _prem_t[q] for q in range(1, Q + 1)]
        _prem_gross_t = [float(a["premises_equipment"])] * (Q + 1)
        _prem_accum_t = [max(0.0, _prem_gross_t[q] - _prem_t[q]) for q in range(Q + 1)]
        _capex_t = [0.0] * (Q + 1)
        _fa = {"preopening_capex": 0.0, "asset_rows": []}
    non_earn = _prem_t[0] + a["intangibles"] + a["other_assets"]
    other_liab = a["other_liabilities"]
    alloc = a["sweep_securities_alloc"]
    floor_pct = a["alll_floor_pct_loans"]

    # ---- product projections ----
    def project(p, is_lend):
        beg, end, avg = [], [], []
        b = p.get("opening_balance", p.get("opening", p.get("notional", 0.0))) or 0.0
        for q in range(1, Q + 1):
            beg.append(b)
            runoff = _ov(p, "runoff_q", q, p.get("runoff_q") or 0.0)
            if is_lend and p.get("volume_mode") == "originations":
                e = max(0.0, b * (1 - runoff) + _ov(p, "originations_q", q, p.get("originations_q") or 0.0))
            else:
                e = max(0.0, b * (1 + _ov(p, "growth_q", q, p.get("growth_q") or 0.0) - runoff)
                        + (p.get("purchases_q") or 0.0))
            end.append(e)
            avg.append((b + e) / 2.0)
            b = e
        p["_beg"], p["_end"], p["_avg"] = beg, end, avg

    for p in lend:
        project(p, True)
    for p in dep + obs + afs_p + htm_p:
        project(p, False)

    gl0 = sum(p["_beg"][0] for p in lend)
    alll = gl0 * floor_pct
    _po = cfg.get("pre_opening") or {}
    _burn = sum(float(e.get("total", 0.0)) for e in (_po.get("expenses") or []))
    re = -_burn                      # organizational costs: opening deficit in RE
    equity = capital + re
    _aoci_sens = float(a.get("aoci_sensitivity_annual") or 0.0)
    aoci_cum = 0.0

    def plug(gross_end, alll_end, sec_prod_end, dep_end, equity_end, extra_liab=0.0):
        uses = gross_end - alll_end + sec_prod_end + _ne[0] - _sched_t[_ne_q[0]]
        liquid = dep_end + other_liab + float(extra_liab or 0.0) + equity_end - uses
        borrow = 0.0
        if liquid < 0:
            borrow = -liquid
            liquid = 0.0
        return liquid * (1 - alloc), liquid * alloc, borrow

    sec0 = sum(p["_beg"][0] for p in afs_p + htm_p)
    dep0 = sum(p["_beg"][0] for p in dep)
    _ne = [non_earn]
    _ne_q = [0]
    cash, sweep, borrow = plug(gl0, alll, sec0, dep0, equity)
    prev_assets = cash + sweep + sec0 + (gl0 - alll) + non_earn

    out_bs = {k: [] for k in ("cash", "afs", "htm", "grossLoans", "alll", "netLoans",
                              "deposits", "borrowings", "equity", "retained", "aoci",
                              "paidIn", "premises", "premisesGross", "premisesAccumDep",
                              "borrowSched", "prepaidOpex", "accruedOpex", "totalAssets")}
    out_is = {k: [] for k in ("intLoans", "intSec", "intCash", "intDep", "intBorrow", "nii",
                              "provision", "fees", "opexProd", "workforceComp", "otherOpex", "depreciationExpense", "fixedOpex", "pretax", "tax",
                              "ni", "chargeoffs")}

    for qi in range(Q):
        q = qi + 1
        int_loans = sum(p["_avg"][qi] * _prod_rate(p, q, _rate) / 4.0 for p in lend)
        int_sec_prod = sum(p["_avg"][qi] * (p.get("yield_ann") or 0.0) / 4.0 for p in afs_p + htm_p)
        int_sweep = sweep * a["sweep_securities_yield"] / 4.0          # beginning balance
        int_cash = cash * a["cash_yield"] / 4.0                        # beginning balance
        int_dep = sum(p["_avg"][qi] * _prod_rate(p, q, _rate) / 4.0 for p in dep)
        int_borrow = borrow * a["borrow_rate_ann"] / 4.0 + _sched_int[qi]   # beginning balance + scheduled
        nii = int_loans + int_sec_prod + int_sweep + int_cash - int_dep - int_borrow

        fees = (sum(p["_avg"][qi] * (p.get("fee_yield_ann") or 0.0) / 4.0 for p in lend + dep + obs + afs_p + htm_p)
                 )
        opex_prod = sum(opex_fixed_q(p) for p in lend + dep + obs + afs_p + htm_p)
        _ovh_b = _simple_overhead[qi] + _dep_exp[qi]
        # Disclosure-only decomposition; see Profile A for the same contract.
        _workforce_comp = 0.0
        _depreciation_expense = _dep_exp[qi]
        _other_opex = _ovh_b - _depreciation_expense
        if _nie_d:
            _pa = prev_assets
            _te = (equity if qi == 0 else out_bs["equity"][qi - 1]) - a["intangibles"]
            _pa_d = _pa if qi == 0 else out_bs["totalAssets"][qi - 1]
            _fdic_bp = (_nie_d.get("fdic_bp_ann") if _nie_d.get("fdic_bp_ann") is not None
                        else _RP["assessments"]["fdic_bp_ann"])
            _occ_enabled = bool(_nie_d.get("occ_simplified_enabled"))
            _occ_bp = float(_nie_d.get("occ_bp_ann") or 0.0) if _occ_enabled else 0.0
            _fdic = max(0.0, _pa_d - _te) * float(_fdic_bp) / 10000.0 / 4.0
            # Quarterly Profile B uses the same ordinal semiannual OCC contract as Profile A:
            # one two-quarter assessment block, with the first payment period translated into Q#.
            _occ = 0.0
            if _occ_enabled:
                _occ_half_interval = 2
                _occ_half = qi // _occ_half_interval
                if qi % _occ_half_interval == 0:
                    _occ_half_amt = _pa_d * _occ_bp / 10000.0 / 2.0
                _occ = _occ_half_amt / float(_occ_half_interval)
                _occ_first_pay = max(1, int(_nie_d.get("occ_payment_first_period") or 1))
                _occ_pay_phase = (_occ_first_pay - 1) % _occ_half_interval
                _occ_pay_start_half = (_occ_first_pay - 1) // _occ_half_interval
                _occ_cash = (_occ_half_amt if (_occ_half >= _occ_pay_start_half
                                                and (qi % _occ_half_interval) == _occ_pay_phase)
                             else 0.0)
                _occ_signed_balance += _occ_cash - _occ
            _linked_opex = sum(linked_component_amount(
                _lc, qi, {"fee_income": fees, "gain_on_sale": 0.0, "servicing_net": 0.0,
                          "customer_acquisition_auc_monthly": _auc_month_sources,
                          "customer_acquisition_auc_beginning": _auc_beginning_sources,
                          "fee_stream_quantity_history": {},
                          "bank_total_assets_end_by_period": [prev_assets] + list(out_bs["totalAssets"]),
                          "cost_pool": {k: float(v[qi] or 0.0) for k, v in _cost_pool_series.items()},
                          "periods_per_year": 4})
                for _lc in (_nie_d.get("linked_components") or []))
            _role_workforce_comp = _nie_d["comp"][qi]
            _wf_add_values = []
            if _wf_add_components:
                _hist_nii = [float(x or 0.0) for x in out_is["nii"]] + [float(nii or 0.0)]
                _hist_fee = [float(x or 0.0) for x in out_is["fees"]] + [float(fees or 0.0)]
                _hist_zero = [0.0] * (qi + 1)
                _hist_nonint = list(_hist_fee)
                _hist_total = [_hist_nii[_i] + _hist_nonint[_i] for _i in range(qi + 1)]
                _wf_metrics = {
                    "periods_per_year": 4,
                    "income_statement_flow_history": {
                        "fee_income": _hist_fee, "gain_on_sale": _hist_zero, "servicing_net": _hist_zero,
                        "noninterest_income": _hist_nonint, "net_interest_income": _hist_nii,
                        "total_operating_revenue": _hist_total,
                    },
                    "customer_acquisition_auc_monthly": _auc_month_sources,
                    "customer_acquisition_auc_beginning": _auc_beginning_sources,
                    "fee_stream_quantity_history": {},
                    "fee_stream_quantity_known_ids": set(),
                    "bank_total_assets_end_by_period": [prev_assets] + list(out_bs["totalAssets"]),
                }
                _wf_add_values = [workforce_additive_component_amount(_wc, qi, _wf_metrics)
                                  for _wc in _wf_add_components]
            _workforce_comp = _role_workforce_comp + sum(_wf_add_values)
            _sub = (_workforce_comp + _nie_d["categories"][qi] + _linked_opex
                    + _fdic + _occ + _dep_exp[qi] + opex_prod)
            _r = _nie_d["gross_up_rate"]
            _ovh_b = (_sub - opex_prod) + (_sub * _r / (1 - _r) if 0 < _r < 1 else 0.0)
            _other_opex = _ovh_b - _workforce_comp - _depreciation_expense
            _wf_comp_native.append(float(_workforce_comp or 0.0))
            _wf_role_comp_native.append(float(_role_workforce_comp or 0.0))
            _wf_additive_comp_native.append(float(sum(_wf_add_values)))
            for _wci in range(len(_wf_additive_component_native)):
                _wf_additive_component_native[_wci].append(float(_wf_add_values[_wci] if _wci < len(_wf_add_values) else 0.0))
        nie = opex_prod + _ovh_b
        _prepaid_opex_q = (_opex_static_pre[qi] if qi < len(_opex_static_pre) else 0.0) + max(0.0, _occ_signed_balance)
        _accrued_opex_q = (_opex_static_acc[qi] if qi < len(_opex_static_acc) else 0.0) + max(0.0, -_occ_signed_balance)

        gl_end = sum(p["_end"][qi] for p in lend)
        chargeoffs = sum(p["_avg"][qi] * _ov(p, "charge_off_ann", q, p.get("charge_off_ann") or 0.0) / 4.0
                         for p in lend)
        prov_prod = sum(p["_avg"][qi] * (p.get("provision_rate_ann")
                                          if p.get("provision_rate_ann") is not None
                                          else _ov(p, "charge_off_ann", q, p.get("charge_off_ann") or 0.0)) / 4.0
                        for p in lend)
        alll_tent = alll - chargeoffs + prov_prod
        floor = gl_end * floor_pct
        true_up = max(0.0, floor - alll_tent)
        provision = prov_prod + true_up
        alll_end = alll_tent + true_up

        pretax = nii + fees - nie - provision
        tax = max(0.0, pretax) * a["tax_rate"]
        ni = pretax - tax
        re += ni
        _afs_end = sum(p["_end"][qi] for p in afs_p) if afs_p else 0.0
        aoci_cum += _afs_end * _aoci_sens / 4.0
        # qi is zero-based while cap_t is [opening,Q1..Q12]. A Q1 raise must
        # therefore be present in period 1, not delayed to Q2.
        equity_end = cap_t[qi + 1] + re + aoci_cum

        dep_end = sum(p["_end"][qi] for p in dep)
        sec_prod_end = sum(p["_end"][qi] for p in afs_p + htm_p)
        _ne[0] = _prem_t[qi + 1] + a["intangibles"] + a["other_assets"] + _prepaid_opex_q
        _ne_q[0] = qi + 1
        c2, s2, b2 = plug(gl_end, alll_end, sec_prod_end, dep_end, equity_end, _accrued_opex_q)
        net_loans = gl_end - alll_end
        afs_end = s2 + sum(p["_end"][qi] for p in afs_p)
        htm_end = sum(p["_end"][qi] for p in htm_p)
        total_assets = c2 + afs_end + htm_end + net_loans + _ne[0]

        for k, v in (("cash", c2), ("afs", afs_end), ("htm", htm_end), ("grossLoans", gl_end),
                     ("alll", alll_end), ("netLoans", net_loans), ("deposits", dep_end),
                     ("borrowings", b2), ("equity", equity_end), ("retained", re),
                     ("aoci", aoci_cum), ("paidIn", cap_t[qi + 1]),
                     ("premises", _prem_t[qi + 1]),
                     # Match Profile A's presentation contract: gross PP&E and
                     # accumulated depreciation are visible regardless of whether the
                     # user authored fixed assets in Simple or schedule mode.
                     ("premisesGross", _prem_gross_t[qi + 1]),
                     ("premisesAccumDep", _prem_accum_t[qi + 1]),
                     ("borrowSched", _sched_t[qi + 1]), ("prepaidOpex", _prepaid_opex_q),
                     ("accruedOpex", _accrued_opex_q), ("totalAssets", total_assets)):
            out_bs[k].append(v)
        for k, v in (("intLoans", int_loans), ("intSec", int_sec_prod + int_sweep),
                     ("intCash", int_cash), ("intDep", int_dep), ("intBorrow", int_borrow),
                     ("nii", nii), ("provision", provision), ("fees", fees),
                     ("opexProd", opex_prod), ("workforceComp", _workforce_comp),
                     ("otherOpex", _other_opex), ("depreciationExpense", _depreciation_expense),
                     ("fixedOpex", _ovh_b), ("pretax", pretax), ("tax", tax), ("ni", ni), ("chargeoffs", chargeoffs)):
            out_is[k].append(v)

        alll = alll_end
        cash, sweep, borrow = c2, s2, b2

    out_ratios = {"roa": [], "roe": [], "nim": [], "eff": [], "leverage": []}
    pa, pe = prev_assets, capital
    for qi in range(Q):
        ta, eq, ni = out_bs["totalAssets"][qi], out_bs["equity"][qi], out_is["ni"][qi]
        avg_a, avg_e = (pa + ta) / 2.0, (pe + eq) / 2.0
        out_ratios["roa"].append(ni * 4 / avg_a * 100 if avg_a > 0 else None)
        out_ratios["roe"].append(ni * 4 / avg_e * 100 if avg_e > 0 else None)
        out_ratios["nim"].append(None)  # informational only in profile B fixtures
        rev = out_is["nii"][qi] + out_is["fees"][qi]
        out_ratios["eff"].append((out_is["opexProd"][qi] + out_is["fixedOpex"][qi]) / rev * 100 if rev > 0 else None)
        out_ratios["leverage"].append(eq / ta * 100 if ta > 0 else None)
        pa, pe = ta, eq
    ftp = (a.get("reporting") or {}).get("ftp_benchmark_ann", 0.0)
    products = []
    for fam, plist in (("lending", lend), ("deposit", dep), ("obs", obs)):
        for p in plist:
            def _r(field, dflt_key):
                return [_ov(p, field, qi + 1, p.get(dflt_key) or 0.0) for qi in range(Q)]
            yv = ([_prod_rate(p, qi + 1, _rate) for qi in range(Q)]
                  if fam in ("lending", "deposit") else [0.0] * Q)
            cov = _r("charge_off_ann", "charge_off_ann")
            products.append({
                "name": p.get("name"), "family": fam,
                "line": p.get("call_report_line"),
                "rate_type": p.get("rate_type", "fixed"),
                "index_spread": p.get("index_spread"), "is_fv": False,
                "sale_pct": 0.0, "serv_retained": 0.0,
                "rateQ": [v * 100 for v in yv] if fam != "obs" else None,
                "intInc": ([p["_avg"][qi] * yv[qi] / 4.0 for qi in range(Q)] if fam == "lending" else [0.0] * Q),
                "intExp": ([p["_avg"][qi] * yv[qi] / 4.0 for qi in range(Q)] if fam == "deposit" else [0.0] * Q),
                "origq": None, "soldOrig": None, "whCarry": None, "servUPB": None,
                "msrCap": None, "msrAmort": None, "msrBal": None, "alll": None,
                "fv": None, "fvAdj": None,
                "bal": list(p["_end"]),
                "avg": list(p["_avg"]),
                "interest": [p["_avg"][qi] * yv[qi] / 4.0 * (1 if fam == "lending" else -1)
                             for qi in range(Q)] if fam != "obs" else [0.0] * Q,
                "fees": [p["_avg"][qi] * (p.get("fee_yield_ann") or 0.0) / 4.0 for qi in range(Q)],
                "opex": [opex_fixed_q(p)] * Q,
                "co": [p["_avg"][qi] * cov[qi] / 4.0 for qi in range(Q)] if fam == "lending" else [0.0] * Q,
                "gos": [0.0] * Q, "servNet": [0.0] * Q,
                "ftp_rate": [ftp] * Q,
            })
    _out = {"products": products, "bs": out_bs, "is": out_is, "ratios": out_ratios}
    if _nie_d and (_wf_cfg.get("mode") == "roles" or (_wf_cfg.get("roles") or []) or _wf_add_components):
        _out["workforce"] = {
            "resolved_hire_periods": [int((r or {}).get("hire_period") or 1) for r in (_wf_cfg.get("roles") or [])],
            "roles": [str((r or {}).get("role") or "") for r in (_wf_cfg.get("roles") or [])],
            "series_ids": [str((r or {}).get("series_id") or "") for r in (_wf_cfg.get("roles") or [])],
            "counts": [],
            "comp": list(_wf_comp_native),
            "role_comp": list(_wf_role_comp_native),
            "additive_comp": list(_wf_additive_comp_native),
            "additive_components": [
                {"component_id": str((c or {}).get("component_id") or ""),
                 "name": str((c or {}).get("name") or "Tiered / banded compensation component"),
                 "amounts": list(_wf_additive_component_native[i])}
                for i, c in enumerate(_wf_add_components)
            ],
        }
    if fixed_asset_mode(a) == "schedule":
        _out["fixed_assets"] = {
            "mode": "schedule",
            "preopening_capex": float(_fa.get("preopening_capex") or 0.0),
            "assets": list(_fa.get("asset_rows") or []),
            "gross": list(_prem_gross_t),
            "accumulated_depreciation": list(_prem_accum_t),
            "net": list(_prem_t),
            "depreciation_expense": list(_dep_exp),
            "capex": list(_capex_t),
        }
    return _out
