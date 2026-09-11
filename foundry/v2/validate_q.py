"""Foundry v2 — fail-closed configuration validation (ledger A.13).

Same philosophy as v1 configio: an invalid configuration never produces partial
financials. Three tiers — structural, completeness (per product instance), and
sanity ranges — with every violation reported at once.
"""


class ConfigErrorV2(ValueError):
    pass


TOP_REQUIRED = ["engagement_id", "schema_version", "client_legal_name", "proposed_bank",
                "hq", "config_version", "config_frozen", "parity_profile",
                "step_minus_1", "step_0", "step_0a", "step_1", "assumption_tags",
                "constraints", "target_state", "assumptions"]
# peer_query became OPTIONAL with the synthetic-cohort purge: the wizard no
# longer writes it, and peer evidence pends substrate calibration either way.

KNOWN_MODULES = {"balance_driven_deposits", "balance_driven_lending",
                 "balance_driven_obs", "mortgage_banking", "investment_portfolio"}

ASSUMPTION_REQUIRED = ["rate_path_q", "rate_path_longer_run", "tax_semantics", "tax_rate",
                       "cash_yield", "premises_equipment", "intangibles",
                       "other_assets", "other_liabilities"]

DEP_REQUIRED = ["name", "opening_balance", "growth_per_period", "rate_type"]
LEND_REQUIRED = ["name", "opening_balance", "runoff_per_period", "rate_type",
                 "charge_off_ann", "measurement"]

# (path, lo, hi, reason) — nonsense fails closed
RANGES = [
    ("tax_rate", 0.0, 0.60, "tax rate must be in [0, 0.60]"),
    ("cash_yield", 0.0, 0.30, "cash yield must be in [0, 0.30]"),
]
PROD_RANGES = [
    ("rate_paid_ann", 0.0, 0.30, "deposit rate must be in [0, 0.30]"),
    ("yield_ann", 0.0, 0.60, "asset yield must be in [0, 0.60]"),
    ("charge_off_ann", 0.0, 0.40, "loss rate must be in [0, 0.40]"),
    ("provision_rate_ann", 0.0, 0.40, "provision rate must be in [0, 0.40]"),
    ("runoff_per_period", 0.0, 1.0, "runoff must be a rate in [0, 1]; negative runoff mints balances"),
    ("growth_per_period", -0.5, 1.0, "growth must be in [-0.5, 1.0]"),
]
MB_RANGES = [
    ("sale_pct_of_orig", 0.0, 1.0, "sale share must be in [0, 1]"),
    ("gain_on_sale_margin", -0.05, 0.10, "gain-on-sale margin must be in [-0.05, 0.10]"),
    ("warehouse_hold_q", 0, 4, "warehouse period must be 0-4 quarters"),
    ("servicing_retained_pct", 0.0, 1.0, "servicing retained must be in [0, 1]"),
    ("servicing_fee_bp_ann", 0.0, 100.0, "servicing fee must be 0-100bp"),
    ("msr_cap_rate_pct_upb", 0.0, 0.03, "MSR capitalization must be in [0, 3%] of UPB"),
]


def _range_check(obj, ranges, ctx, errs):
    for key, lo, hi, reason in ranges:
        v = obj.get(key)
        if v is None:
            continue
        try:
            ok = lo <= float(v) <= hi
        except (TypeError, ValueError):
            ok = False
        if not ok:
            errs.append(f"{ctx}'{key}' = {v!r} out of range: {reason}")


def validate_errors_v2(cfg):
    """Structured error objects for the console (C.2): [{'message': ...}, ...].
    Empty list == valid. validate_config_v2 raises on the same set."""
    try:
        validate_config_v2(cfg)
        return []
    except ConfigErrorV2 as e:
        return [{"message": m.strip()} for m in str(e).split(";") if m.strip()]


def validate_config_v2(cfg):
    errs = []
    from .timebase import quarterly_value_to_period
    from .growth import validate_growth_spec_for_cadence, growth_context_from_cfg
    _a0 = cfg.get("assumptions") or {}
    _alias_ppy = _a0.get("periods_per_year") or 4
    if not isinstance(_alias_ppy, int) or isinstance(_alias_ppy, bool) or _alias_ppy not in (4, 12):
        _alias_ppy = 4
    # Cadence field-name aliasing (mirror of the engine): accept BOTH the legacy "_q" per-period
    # field names and the canonical "_per_period" names, so a config authored with either passes.
    # We mirror new->old before the required-field/range checks (which reference the "_q" names),
    # so a new-name config validates without changing those checks. Mutates in place; harmless
    # (the engine re-aliases anyway). Old-name configs are untouched.
    _PP = ["growth", "runoff", "purchases", "new_deposits", "orig_growth", "originations",
           "opex_fixed", "fv_decay", "msr_decay", "overhead_growth", "overhead"]
    _alias_conflicts = []
    def _alias(d):
        if not isinstance(d, dict):
            return
        for _st in _PP:
            _n, _o = _st + "_per_period", _st + "_q"
            # AUDIT (val-alias): both legacy and canonical names present with DIFFERENT values is
            # ambiguous — reject rather than silently pick one.
            _converted_old = (quarterly_value_to_period(_st, d[_o], _alias_ppy)
                              if _o in d and isinstance(d.get(_o), (int, float)) and not isinstance(d.get(_o), bool)
                              else None)
            if (_n in d and isinstance(d[_n], (int, float)) and not isinstance(d[_n], bool)
                    and _converted_old is not None
                    and abs(d[_n] - _converted_old) > 1e-12):
                _alias_conflicts.append(f"{_st}: both {_o}={d[_o]} and {_n}={d[_n]} present and differ")
            if (_n not in d or d[_n] is None) and _converted_old is not None:
                d[_n] = _converted_old         # legacy quarter value -> equivalent engine-period value
    def _alias_rec(node):
        if isinstance(node, dict):
            _alias(node)
            for _v in node.values():
                _alias_rec(_v)
        elif isinstance(node, list):
            for _v in node:
                _alias_rec(_v)
    _alias_rec(cfg.get("assumptions") or {})
    if _alias_conflicts:
        errs.append("conflicting legacy/canonical cadence fields — " + "; ".join(_alias_conflicts))
    for k in TOP_REQUIRED:
        if k not in cfg:
            errs.append(f"missing required top-level key '{k}'")
    if errs:
        raise ConfigErrorV2("; ".join(errs))

    if "flags_from_map" not in cfg["step_0a"]:
        errs.append("step_0a.flags_from_map is required (the challenge layer consumes it)")

    mods = cfg["step_0"].get("modules", [])
    # Empty modules is LEGAL (fidelity ruling 2026-07-16): the source model
    # keeps a balance sheet alive with zero products — initial capital plugs
    # into securities/cash via the funding waterfall. A module loaded with an
    # empty product list is still rejected below (that is misconfiguration).
    unknown = [m for m in mods if m not in KNOWN_MODULES]
    if unknown:
        errs.append(f"unknown modules {unknown}; known: {sorted(KNOWN_MODULES)}")
    # A funding/revenue side is required, but deposits are not the ONLY valid one: a trust /
    # custody / BaaS charter runs on off-balance-sheet fee income (balance_driven_obs) with
    # little or no deposits. Block only when NEITHER a deposit module NOR an OBS/fee module is
    # loaded (a config with modules but no revenue engine at all is the real misconfiguration).
    # A deposit-less-but-fee-bearing engagement is permitted (fidelity: fee-first charters are
    # real; the funding waterfall keeps the balance sheet alive off initial capital).
    if mods and not unknown and "balance_driven_deposits" not in mods \
            and "balance_driven_obs" not in mods:
        errs.append("no funding or fee side loaded — a bank needs deposits or off-balance-sheet "
                    "fee income (balance_driven_deposits or balance_driven_obs)")

    a = cfg["assumptions"]
    if a.get("overhead_flow_spec") is None and a.get("overhead_per_period") is None and a.get("overhead_q") is None:
        errs.append("missing required assumption: overhead_flow_spec, overhead_per_period, or legacy overhead_q")
    # Projection horizon (optional). Bounded in YEARS (1-7) so table layout stays sane, but the
    # period count depends on cadence: periods_per_year (ppy) 4=quarterly, 12=monthly (annual removed: cannot downsample to the quarterly Call Report floor).
    # So the valid n_periods range is ppy*1 .. ppy*7.
    _ppy = a.get("periods_per_year") or 4
    if not isinstance(_ppy, int) or isinstance(_ppy, bool) or _ppy not in (4, 12):
        errs.append(f"assumptions.periods_per_year = {_ppy!r} invalid: must be 4 (quarterly) or 12 (monthly)")
        _ppy = 4
    # AUDIT 1.3/3: Profile B (parity/override engine) is internally 12-quarter and not cadence-
    # generalized. Fence it to quarterly until converted, rather than crash at run time.
    if (cfg.get("parity_profile") == "pf_b") and _ppy != 4:
        errs.append("Profile B (parity_profile=pf_b) supports quarterly only (periods_per_year=4); "
                    "monthly/annual cadence is not yet available for Profile B")
    _growth_ctx = growth_context_from_cfg(cfg, _ppy)
    if "n_periods" in a and a["n_periods"] is not None:
        _np = a["n_periods"]
        _lo, _hi = _ppy, _ppy * 7
        if not isinstance(_np, int) or isinstance(_np, bool) or not (_lo <= _np <= _hi):
            errs.append(f"assumptions.n_periods = {_np!r} out of range: with periods_per_year={_ppy} "
                        f"must be an integer between {_lo} and {_hi} (1-7 years)")
    s = a.get("aoci_sensitivity_annual")
    if s is not None and (not isinstance(s, (int, float)) or not (-0.5 <= s <= 0.5)):
        errs.append("aoci_sensitivity_annual must be a rate in [-0.5, 0.5] "
                     "(annual change in AOCI as a share of the AFS book)")
    d = a.get("premises_depreciation_annual")
    if d is not None and (not isinstance(d, (int, float)) or d < 0):
        errs.append("premises_depreciation_annual must be a non-negative dollar amount per year")
    # Fixed-asset schedule is opt-in; absence preserves the legacy flat premises path.
    _fa = a.get("fixed_assets") or {}
    _fa_nper = int(a.get("n_periods") or 12)
    if _fa and _fa.get("mode") not in (None, "simple", "schedule"):
        errs.append("fixed_assets.mode must be 'simple' or 'schedule'")
    if _fa.get("mode") == "schedule":
        for i, _asset in enumerate(_fa.get("assets") or []):
            if not isinstance(_asset, dict):
                errs.append(f"fixed_assets.assets[{i}] must be an object")
                continue
            if not str(_asset.get("name", "")).strip():
                errs.append(f"fixed_assets.assets[{i}].name is required")
            _method = str(_asset.get("method") or "straight_line")
            if _method != "straight_line":
                errs.append(f"fixed_assets.assets[{i}].method must be straight_line")
            _res = _asset.get("residual_value", 0.0)
            if not isinstance(_res, (int, float)) or _res < 0:
                errs.append(f"fixed_assets.assets[{i}].residual_value must be a non-negative dollar amount")
                _res = 0.0
            _existing = (_asset.get("opening_gross_cost") is not None or
                         _asset.get("opening_accumulated_depreciation") is not None)
            if _existing:
                _g = _asset.get("opening_gross_cost")
                _ad = _asset.get("opening_accumulated_depreciation", 0.0)
                _life = _asset.get("remaining_life_years")
                if not isinstance(_g, (int, float)) or _g < 0:
                    errs.append(f"fixed_assets.assets[{i}].opening_gross_cost must be non-negative")
                if not isinstance(_ad, (int, float)) or _ad < 0 or (isinstance(_g, (int, float)) and _ad > _g):
                    errs.append(f"fixed_assets.assets[{i}].opening_accumulated_depreciation must be between 0 and opening_gross_cost")
                if isinstance(_g, (int, float)) and isinstance(_res, (int, float)) and _res > _g:
                    errs.append(f"fixed_assets.assets[{i}].residual_value cannot exceed opening_gross_cost")
                if not isinstance(_life, (int, float)) or _life <= 0:
                    errs.append(f"fixed_assets.assets[{i}].remaining_life_years must be > 0")
            else:
                _cost = _asset.get("cost")
                _isp = _asset.get("in_service_period", 0)
                _life = _asset.get("useful_life_years")
                if not isinstance(_cost, (int, float)) or _cost < 0:
                    errs.append(f"fixed_assets.assets[{i}].cost must be a non-negative dollar amount")
                if not isinstance(_isp, int) or isinstance(_isp, bool) or not (0 <= _isp <= _fa_nper):
                    errs.append(f"fixed_assets.assets[{i}].in_service_period must be an integer 0..{_fa_nper} (0 = at opening)")
                if not isinstance(_life, (int, float)) or _life <= 0:
                    errs.append(f"fixed_assets.assets[{i}].useful_life_years must be > 0")
                if isinstance(_cost, (int, float)) and isinstance(_res, (int, float)) and _res > _cost:
                    errs.append(f"fixed_assets.assets[{i}].residual_value cannot exceed cost")
    # Calendar-quarter events are independent of computational cadence. Permit any quarter
    # that actually exists in the configured horizon (1-7 years), rather than the legacy 12Q cap.
    _nper = a.get("n_periods") if isinstance(a.get("n_periods"), int) else 12
    _ppyear = a.get("periods_per_year") if isinstance(a.get("periods_per_year"), int) else 4
    _max_model_q = max(1, int((_nper * 4 + _ppyear - 1) // _ppyear))
    for i, sb in enumerate(a.get("scheduled_borrowings") or []):
        if not str(sb.get("name", "")).strip():
            errs.append(f"scheduled_borrowings[{i}].name is required")
        _ep = sb.get("period")
        _eq = sb.get("quarter")
        if _ep not in (None, ""):
            if not isinstance(_ep, int) or not (1 <= _ep <= _nper):
                errs.append(f"scheduled_borrowings[{i}].period must be an integer 1-{_nper} "
                            "(engine draw period within the projection horizon)")
        elif not isinstance(_eq, int) or not (1 <= _eq <= _max_model_q):
            errs.append(f"scheduled_borrowings[{i}] requires period 1-{_nper} or legacy quarter "
                        f"1-{_max_model_q} within the projection horizon")
        if not isinstance(sb.get("amount"), (int, float)) or sb["amount"] <= 0:
            errs.append(f"scheduled_borrowings[{i}].amount must be a positive dollar amount")
        r_ = sb.get("rate_ann")
        if not isinstance(r_, (int, float)) or not (0 <= r_ <= 0.25):
            errs.append(f"scheduled_borrowings[{i}].rate_ann must be a rate in [0, 0.25]")
        t_ = sb.get("term_q")
        if not isinstance(t_, int) or not (1 <= t_ <= 40):
            errs.append(f"scheduled_borrowings[{i}].term_q must be an integer 1-40 "
                         "(quarters to maturity; bullet advance held flat, then matures)")
    for fld, lo, hi, unit in (("cash_at_banks_pct", 0.0, 1.0, "a share in [0,1]"),
                                ("construction_land_total", 0.0, None, "a non-negative dollar amount"),
                                ("single_largest_borrower", 0.0, None, "a non-negative dollar amount")):
        vv = a.get(fld)
        if vv is not None and (not isinstance(vv, (int, float)) or vv < lo
                                 or (hi is not None and vv > hi)):
            errs.append(f"{fld} must be {unit}")
    for con in (cfg.get("constraints") or []):
        if con.get("key") == "leverage_min":
            lv = con.get("value")
            if not isinstance(lv, (int, float)) or not (0.02 <= lv <= 0.25):
                errs.append(f"constraints leverage_min = {lv!r} is outside the plausible "
                             f"range [2%, 25%] — a chartering commitment is a fraction "
                             f"(0.09 = 9%); this usually means a value landed in the "
                             f"wrong field")
    for i, dp in enumerate(a.get("deposit_products") or []):
        ip = dp.get("insured_pct")
        if ip is not None and (not isinstance(ip, (int, float)) or not (0 <= ip <= 1)):
            errs.append(f"deposit_products[{i}].insured_pct must be a share in [0, 1]")
    nd = a.get("nie_detail")
    if nd:
        fby = nd.get("fte_by_year")
        if fby is not None and (not isinstance(fby, list) or len(fby) != 3 or any(
                not isinstance(x, (int, float)) or x < 0 for x in fby)):
            errs.append("nie_detail.fte_by_year must be three non-negative counts [y1, y2, y3]")
        gr = nd.get("other_gross_up_rate")
        if gr is not None and (not isinstance(gr, (int, float)) or not (0 <= gr < 0.5)):
            errs.append("nie_detail.other_gross_up_rate must be a rate in [0, 0.5)")
        try:
            from .opex_extensions import fee_stream_quantity_catalog, customer_acquisition_auc_catalog
            _fee_qty_ids = {x["series_id"] for x in fee_stream_quantity_catalog(a)}
            _auc_ids = {x["series_id"] for x in customer_acquisition_auc_catalog(a)}
        except (TypeError, ValueError) as e:
            _fee_qty_ids = set()
            _auc_ids = set()
            errs.append(f"Opex linked Series catalog invalid: {e}")
        for i, cat in enumerate(nd.get("categories") or []):
            if cat.get("flow_spec") is not None:
                try:
                    from .periodic_flows import validate_periodic_flow_spec
                    validate_periodic_flow_spec(cat.get("flow_spec"), ppy=_ppy, context=_growth_ctx)
                except (TypeError, ValueError) as e:
                    errs.append(f"nie_detail.categories[{i}].flow_spec invalid: {e}")
            elif cat.get("growth_spec"):
                try:
                    validate_growth_spec_for_cadence(cat.get("growth_spec"), ppy=_ppy, context=_growth_ctx)
                except (TypeError, ValueError) as e:
                    errs.append(f"nie_detail.categories[{i}].growth_spec invalid: {e}")
            try:
                from .opex_extensions import (normalize_linked_component, normalize_settlement,
                                              recognition_spec_for_category, auc_link_creates_cycle)
                _lc = [normalize_linked_component(x) for x in (cat.get("linked_components") or [])]
                for _x in _lc:
                    if _x.get("driver") == "fee_stream_quantity" and _x.get("series_id") not in _fee_qty_ids:
                        raise ValueError(f"linked fee-stream quantity Series {_x.get('series_id')!r} does not exist")
                    if _x.get("driver") == "customer_acquisition_auc":
                        if _x.get("series_id") not in _auc_ids:
                            raise ValueError(f"linked CAC AUC Series {_x.get('series_id')!r} does not exist")
                        if auc_link_creates_cycle(a, cat, _x.get("series_id")):
                            raise ValueError("AUC-linked Opex would create a circular dependency through Customer Acquisition")
                _rt = recognition_spec_for_category(cat, _ppy)
                _st = normalize_settlement(cat.get("settlement"), _ppy)
                _linked_recognition_ok = (_rt["mode"] == "trajectory" or
                                          (_rt["mode"] == "monthly" and int(_rt.get("first_period") or 1) == 1))
                if _lc and not _linked_recognition_ok:
                    raise ValueError("delayed/custom recognition cannot be combined with linked revenue components")
                if _lc and _st["mode"] not in {"recognition", "monthly"}:
                    raise ValueError("custom settlement cannot be combined with linked revenue components")
            except (TypeError, ValueError) as e:
                errs.append(f"nie_detail.categories[{i}] advanced Opex invalid: {e}")
        if nd.get("occ_payment_first_period") is not None:
            _op = nd.get("occ_payment_first_period")
            try:
                _opi = int(_op)
                if float(_op) != float(_opi) or _opi < 1:
                    raise ValueError
            except (TypeError, ValueError):
                errs.append("nie_detail.occ_payment_first_period must be a positive integer model-period ordinal")
        wf = nd.get("workforce") or {}
        if wf.get("default_payroll_load_rate") is not None:
            rr = wf.get("default_payroll_load_rate")
            if not isinstance(rr, (int, float)) or rr < 0 or rr > 2:
                errs.append("nie_detail.workforce.default_payroll_load_rate must be in [0, 2]")
        _wf_default_gs = None
        if wf.get("default_salary_growth_spec"):
            try:
                _wf_default_gs = validate_growth_spec_for_cadence(
                    wf.get("default_salary_growth_spec"), ppy=_ppy, context=_growth_ctx)
            except (TypeError, ValueError) as e:
                errs.append(f"nie_detail.workforce.default_salary_growth_spec invalid: {e}")
        from .activation import managed_notional_source_catalog
        _mn_trigger_catalog = managed_notional_source_catalog(a)
        for i, role in enumerate(wf.get("roles") or []):
            cnt = role.get("count", 1)
            comp = role.get("annual_comp", role.get("base_salary_annual", 0))
            hp = role.get("hire_period", 1)
            ep = role.get("end_period")
            load = role.get("payroll_load_rate")
            activation = role.get("activation") or None
            if not isinstance(cnt, (int, float)) or cnt < 0:
                errs.append(f"nie_detail.workforce.roles[{i}].count must be non-negative")
            if role.get("count_spec"):
                try:
                    from .series import normalize_series_spec, resolve_entered_series
                    _cs = normalize_series_spec(role.get("count_spec"), default_value=float(cnt or 0.0))
                    if _cs.get("source") != "entered":
                        raise ValueError("workforce count_spec must be entered")
                    resolve_entered_series(_cs, max(1, int(a.get("n_periods") or 12)), _ppy,
                                            context=_growth_ctx, default_value=float(cnt or 0.0))
                except (TypeError, ValueError) as e:
                    errs.append(f"nie_detail.workforce.roles[{i}].count_spec invalid: {e}")
            if not isinstance(comp, (int, float)) or comp < 0:
                errs.append(f"nie_detail.workforce.roles[{i}].annual_comp must be non-negative")
            if role.get("compensation_spec"):
                try:
                    from .series import normalize_series_spec, resolve_entered_series
                    _cps = normalize_series_spec(role.get("compensation_spec"), default_value=float(comp or 0.0))
                    if _cps.get("source") != "entered":
                        raise ValueError(
                            "workforce compensation_spec must be entered; no compatible Link/Derived source is whitelisted")
                    _cp_arr = resolve_entered_series(
                        _cps, max(1, int(a.get("n_periods") or 12)), _ppy,
                        context=_growth_ctx, default_value=float(comp or 0.0))
                    if any(float(v) < 0 for v in _cp_arr):
                        raise ValueError("compensation values must be non-negative")
                except (TypeError, ValueError) as e:
                    errs.append(f"nie_detail.workforce.roles[{i}].compensation_spec invalid: {e}")
            if activation:
                try:
                    from .activation import validate_activation_rule
                    validate_activation_rule(activation, source_catalog=_mn_trigger_catalog)
                except (TypeError, ValueError) as e:
                    errs.append(f"nie_detail.workforce.roles[{i}].activation invalid: {e}")
                if ep not in (None, "") and (not isinstance(ep, int) or isinstance(ep, bool) or ep < 1):
                    errs.append(f"nie_detail.workforce.roles[{i}].end_period must be blank or an integer >= 1")
            else:
                if not isinstance(hp, int) or isinstance(hp, bool) or hp < 1:
                    errs.append(f"nie_detail.workforce.roles[{i}].hire_period must be an integer >= 1")
                if ep not in (None, "") and (not isinstance(ep, int) or isinstance(ep, bool) or ep < hp):
                    errs.append(f"nie_detail.workforce.roles[{i}].end_period must be blank or >= hire_period")
            if load is not None and (not isinstance(load, (int, float)) or load < 0 or load > 2):
                errs.append(f"nie_detail.workforce.roles[{i}].payroll_load_rate must be in [0, 2]")
            if role.get("salary_growth_spec"):
                try:
                    _eff = dict(wf.get("default_salary_growth_spec") or {})
                    _eff.update(role.get("salary_growth_spec") or {})
                    validate_growth_spec_for_cadence(_eff, ppy=_ppy, context=_growth_ctx)
                except (TypeError, ValueError) as e:
                    errs.append(f"nie_detail.workforce.roles[{i}].salary_growth_spec invalid: {e}")
    if a.get("overhead_flow_spec") is not None:
        try:
            from .periodic_flows import validate_periodic_flow_spec
            validate_periodic_flow_spec(a.get("overhead_flow_spec"), ppy=_ppy, context=_growth_ctx)
        except (TypeError, ValueError) as e:
            errs.append(f"overhead_flow_spec invalid: {e}")
    elif a.get("overhead_growth_spec"):
        try:
            validate_growth_spec_for_cadence(a.get("overhead_growth_spec"), ppy=_ppy, context=_growth_ctx)
        except (TypeError, ValueError) as e:
            errs.append(f"overhead_growth_spec invalid: {e}")
    # Cost pools are shared non-posting pricing sources. Resolve them during validation so
    # bad IDs, natural-period contracts, canonical-balance links, allocations, or dependency
    # cycles fail before the financial engine can run.
    try:
        from .cost_pools import cost_pool_series_map
        cost_pool_series_map(a, max(1, int(a.get("n_periods") or 12)), _ppy,
                             growth_context=_growth_ctx)
    except (TypeError, ValueError) as e:
        errs.append(f"cost_pools invalid: {e}")

    for pi, prod in enumerate(a.get("obs_exposures") or []):
        mn = prod.get("managed_notional") or {}
        if mn.get("growth_spec"):
            try:
                validate_growth_spec_for_cadence(mn.get("growth_spec"), ppy=_ppy, context=_growth_ctx)
            except (TypeError, ValueError) as e:
                errs.append(f"obs_exposures[{pi}].managed_notional.growth_spec invalid: {e}")
        for si, st in enumerate(prod.get("fee_streams") or []):
            from .income_modules import _validate_fee_stream_shape, _fee_coefficient_value
            try:
                _validate_fee_stream_shape(st)
                if ((st.get("driver") or {}).get("source") == "cost_pool"):
                    from .cost_pools import resolve_cost_pool_ref
                    _linked_pool = resolve_cost_pool_ref((st.get("driver") or {}).get("ref"), a)
                    if not ((_linked_pool or {}).get("components") or []):
                        raise ValueError("referenced cost_pool requires at least one eligible expense component")
                coef = (((st.get("driver") or {}).get("params") or {}).get("coefficient"))
                if coef is not None:
                    _fee_coefficient_value(coef, 1, _ppy, {"growth_context": _growth_ctx})
            except (TypeError, ValueError) as e:
                errs.append(f"obs_exposures[{pi}].fee_streams[{si}] invalid: {e}")
            gs0 = (((st.get("driver") or {}).get("params") or {}).get("growth_spec"))
            if gs0:
                try:
                    validate_growth_spec_for_cadence(gs0, ppy=_ppy, context=_growth_ctx)
                except (TypeError, ValueError) as e:
                    errs.append(f"obs_exposures[{pi}].fee_streams[{si}].driver.params.growth_spec invalid: {e}")
            cgs = ((((st.get("driver") or {}).get("params") or {}).get("coefficient") or {}).get("growth_spec"))
            if cgs:
                try:
                    validate_growth_spec_for_cadence(cgs, ppy=_ppy, context=_growth_ctx)
                except (TypeError, ValueError) as e:
                    errs.append(f"obs_exposures[{pi}].fee_streams[{si}].driver.params.coefficient.growth_spec invalid: {e}")
    po = cfg.get("pre_opening") or {}
    for i, e in enumerate(po.get("expenses") or []):
        if not str(e.get("category", "")).strip():
            errs.append(f"pre_opening.expenses[{i}].category is required")
        t = e.get("total")
        if not isinstance(t, (int, float)) or t < 0:
            errs.append(f"pre_opening.expenses[{i}].total must be a non-negative dollar amount")
    if po.get("min_day1_capital") is not None:
        m = po["min_day1_capital"]
        if not isinstance(m, (int, float)) or m < 0:
            errs.append("pre_opening.min_day1_capital must be a non-negative dollar amount")
    for i, r in enumerate(a.get("capital_raises") or []):
        ep = r.get("period"); q = r.get("quarter"); amt = r.get("amount")
        if ep not in (None, ""):
            if not isinstance(ep, int) or not (1 <= ep <= _nper):
                errs.append(f"capital_raises[{i}].period must be an integer 1..{_nper} "
                            "(engine period within the projection horizon)")
        elif not isinstance(q, int) or not (1 <= q <= _max_model_q):
            errs.append(f"capital_raises[{i}] requires period 1..{_nper} or legacy quarter "
                        f"1..{_max_model_q} within the projection horizon")
        if not isinstance(amt, (int, float)) or amt <= 0:
            errs.append(f"capital_raises[{i}].amount must be a positive dollar amount")
    missing = [k for k in ASSUMPTION_REQUIRED if k not in a]
    if missing:
        errs.append(f"missing required assumptions: {missing}")
    # rate_path_q is a QUARTERLY-authored path (its natural resolution), independent of engine
    # cadence — the engine interpolates it to the run cadence. Accept any sane quarterly length
    # (4-28 quarters = 1-7 years); it need not equal the period count.
    if "rate_path_q" in a and (not isinstance(a["rate_path_q"], list) or not (4 <= len(a["rate_path_q"]) <= 28)):
        errs.append("rate_path_q must be a quarterly list of annual rates, length 4-28 (1-7 years)")
    _range_check(a, RANGES, "", errs)

    dep = a.get("deposit_products") or []
    lend = a.get("lending_products") or []
    if "balance_driven_deposits" in mods and not dep:
        errs.append("balance_driven_deposits loaded but assumptions.deposit_products is empty")
    if "balance_driven_lending" in mods and not lend:
        errs.append("balance_driven_lending loaded but assumptions.lending_products is empty")

    for p in dep:
        ctx = f"deposit '{p.get('name', '<?>')}': "
        for k in DEP_REQUIRED:
            if k not in p:
                errs.append(ctx + f"missing required field '{k}'")
        if p.get("rate_type") == "float" and "index_spread" not in p:
            errs.append(ctx + "floating rate requires 'index_spread'")
        if p.get("rate_type") == "float" and p.get("index") is not None \
                and p.get("index") not in ("sofr", "effr", "prime"):
            errs.append(ctx + f"unknown floating index {p.get('index')!r}: must be one of "
                        "sofr, effr, prime (unknown indexes silently fell back to SOFR)")
        if p.get("rate_type") == "fixed" and p.get("rate_paid_ann") is None:
            errs.append(ctx + "fixed rate requires 'rate_paid_ann'")
        _range_check(p, PROD_RANGES, ctx, errs)
    for p in lend:
        ctx = f"lending '{p.get('name', '<?>')}': "
        for k in LEND_REQUIRED:
            if k not in p:
                errs.append(ctx + f"missing required field '{k}'")
        if p.get("rate_type") == "float" and "index_spread" not in p:
            errs.append(ctx + "floating rate requires 'index_spread'")
        if p.get("rate_type") == "float" and p.get("index") is not None \
                and p.get("index") not in ("sofr", "effr", "prime"):
            errs.append(ctx + f"unknown floating index {p.get('index')!r}: must be one of "
                        "sofr, effr, prime (unknown indexes silently fell back to SOFR)")
        if p.get("rate_type") == "fixed" and p.get("yield_ann") is None:
            errs.append(ctx + "fixed rate requires 'yield_ann'")
        if p.get("measurement") == "fair_value" and p.get("discount_spread_ann") is None:
            errs.append(ctx + "fair-value election requires 'discount_spread_ann'")
        _range_check(p, PROD_RANGES, ctx, errs)
        mb = p.get("mortgage_banking")
        if mb:
            _range_check(mb, MB_RANGES, ctx + "mortgage_banking.", errs)

    # Generic Customer Acquisition / Foundry-Series validation.  This executes only the
    # deterministic assumption-side customer/AUC roll-forward, not the financial engine,
    # so invalid links, unsupported acquisition equations, or circular workforce links
    # fail closed before a run can silently omit/misstate customer economics.
    for _fn, _feed in (a.get("cac_feeds") or {}).items():
        try:
            from .cac_feeder import cac_auc_rollforward
            cac_auc_rollforward(_feed, max(1, int(a.get("n_periods") or 12)), _ppy,
                                assumptions=a, growth_context=_growth_ctx)
        except (TypeError, ValueError) as e:
            errs.append(f"cac_feeds[{_fn!r}] invalid: {e}")

    # Stable Series identities are the cross-module contract.  Legacy configs may omit
    # them, but any identity that exists must be globally unique and owned by the module
    # that authors the economics.  Nested Count specs reuse the role's count series_id.
    _series_ids = []
    _nd_ids = a.get("nie_detail") or {}
    for _j, _r in enumerate(_nd_ids.get("categories") or []):
        _r = _r or {}
        _sid = str(_r.get("series_id") or "").strip()
        if _sid: _series_ids.append(_sid)
        _own = str(_r.get("owner_module") or "").strip()
        if _own and _own != "operating_expense":
            errs.append(f"nie_detail.categories[{_j}].owner_module must be operating_expense")
    for _j, _r in enumerate((((_nd_ids.get("workforce") or {}).get("roles")) or [])):
        _r = _r or {}
        _sid = str(_r.get("series_id") or "").strip()
        if _sid: _series_ids.append(_sid)
        _csid = str(((_r.get("count_spec") or {}).get("series_id")) or "").strip()
        if _sid and _csid and _sid != _csid:
            errs.append(f"nie_detail.workforce.roles[{_j}].count_spec.series_id must match the role count series_id")
        _comp_sid = str(_r.get("compensation_series_id") or ((_r.get("compensation_spec") or {}).get("series_id")) or "").strip()
        if _comp_sid: _series_ids.append(_comp_sid)
        _expense_sid = str(_r.get("expense_series_id") or "").strip()
        if _expense_sid: _series_ids.append(_expense_sid)
        _cpsid = str(((_r.get("compensation_spec") or {}).get("series_id")) or "").strip()
        if _comp_sid and _cpsid and _comp_sid != _cpsid:
            errs.append(f"nie_detail.workforce.roles[{_j}].compensation_spec.series_id must match compensation_series_id")
        _own = str(_r.get("owner_module") or "").strip()
        if _own and _own != "operating_expense.workforce":
            errs.append(f"nie_detail.workforce.roles[{_j}].owner_module must be operating_expense.workforce")
    for _fn, _feed in (a.get("cac_feeds") or {}).items():
        _feed_sid = str((_feed or {}).get("series_id") or "").strip()
        if _feed_sid: _series_ids.append(_feed_sid)
        for _k, _sp in ((_feed or {}).get("driver_specs") or {}).items():
            _sid = str((_sp or {}).get("series_id") or "").strip()
            if _sid: _series_ids.append(_sid)
            _own = str((_sp or {}).get("owner_module") or "").strip()
            if _own and _own != "customer_acquisition":
                errs.append(f"cac_feeds[{_fn!r}].driver_specs[{_k!r}].owner_module must be customer_acquisition")
        for _ci, _ch in enumerate((_feed or {}).get("channels") or []):
            for _k, _sp in ((_ch or {}).get("driver_specs") or {}).items():
                _sid = str((_sp or {}).get("series_id") or "").strip()
                if _sid: _series_ids.append(_sid)
                _own = str((_sp or {}).get("owner_module") or "").strip()
                if _own and _own != "customer_acquisition":
                    errs.append(f"cac_feeds[{_fn!r}].channels[{_ci}].driver_specs[{_k!r}].owner_module must be customer_acquisition")
            for _k, _sid0 in ((_ch or {}).get("derived_series_ids") or {}).items():
                _sid = str(_sid0 or "").strip()
                if _sid: _series_ids.append(_sid)
    try:
        from .opex_extensions import fee_stream_quantity_catalog
        for _meta in fee_stream_quantity_catalog(a):
            _sid = str(_meta.get("series_id") or "").strip()
            if _sid: _series_ids.append(_sid)
    except (TypeError, ValueError):
        pass
    try:
        from .cost_pools import cost_pool_catalog, cost_pool_component_series_ids
        for _pool_meta in cost_pool_catalog(a):
            _sid = str(_pool_meta.get("series_id") or "").strip()
            if _sid: _series_ids.append(_sid)
        _series_ids.extend(cost_pool_component_series_ids(a))
    except (TypeError, ValueError):
        pass  # the structural cost-pool validation above already reports the actionable error
    if len(_series_ids) != len(set(_series_ids)):
        errs.append("Foundry linked-series series_id values must be unique")

    ts = cfg["target_state"]
    if not ts.get("initial_capital") or ts["initial_capital"] <= 0:
        errs.append("target_state.initial_capital must be present and positive")
    for c in cfg["constraints"]:
        for k in ("key", "value", "text", "source"):
            if k not in c:
                errs.append(f"constraint {c.get('key', '<?>')} missing field '{k}'")
    if not any(c.get("key") == "leverage_min" for c in cfg["constraints"]):
        errs.append("constraints must include 'leverage_min' (every de novo carries a capital commitment)")

    if errs:
        raise ConfigErrorV2("; ".join(errs))
    return cfg


def structural_rate_gaps(cfg):
    """The specific structural incompleteness that must never be persisted: a rate_type /
    measurement selector pointing at an empty field. This is a mistake (a half-finished type
    flip), not legitimate work-in-progress, so the save door hard-refuses it — the same
    fail-closed rule freeze and download already enforce. Returns a list of human messages
    (empty => clean). NARROWER than validate_config_v2: only these selector-vs-value gaps,
    so genuine WIP with other open questions can still be saved."""
    a = cfg.get("assumptions") or {}
    gaps = []
    for p in a.get("deposit_products") or []:
        ctx = f"deposit '{p.get('name', '<?>')}': "
        if p.get("rate_type") == "float" and p.get("index_spread") is None:
            gaps.append(ctx + "rate type is floating but no spread over SOFR is set")
        if p.get("rate_type") == "fixed" and p.get("rate_paid_ann") is None:
            gaps.append(ctx + "rate type is fixed but no rate paid is set")
    for p in a.get("lending_products") or []:
        ctx = f"loan '{p.get('name', '<?>')}': "
        if p.get("rate_type") == "float" and p.get("index_spread") is None:
            gaps.append(ctx + "rate type is floating but no spread over SOFR is set")
        if p.get("rate_type") == "fixed" and p.get("yield_ann") is None:
            gaps.append(ctx + "rate type is fixed but no yield is set")
        if p.get("measurement") == "fair_value" and p.get("discount_spread_ann") is None:
            gaps.append(ctx + "measurement is fair value but no DCF discount spread is set")
    return gaps
