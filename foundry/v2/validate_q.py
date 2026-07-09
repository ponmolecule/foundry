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
                "constraints", "target_state", "peer_query", "assumptions"]

KNOWN_MODULES = {"balance_driven_deposits", "balance_driven_lending",
                 "balance_driven_obs", "mortgage_banking", "investment_portfolio"}

ASSUMPTION_REQUIRED = ["rate_path_q", "rate_path_longer_run", "tax_semantics", "tax_rate",
                       "cash_yield", "overhead_q", "premises_equipment", "intangibles",
                       "other_assets", "other_liabilities"]

DEP_REQUIRED = ["name", "opening_balance", "growth_q", "rate_type"]
LEND_REQUIRED = ["name", "opening_balance", "runoff_q", "rate_type",
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
    ("runoff_q", 0.0, 1.0, "runoff must be a rate in [0, 1]; negative runoff mints balances"),
    ("growth_q", -0.5, 1.0, "quarterly growth must be in [-0.5, 1.0]"),
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
    for k in TOP_REQUIRED:
        if k not in cfg:
            errs.append(f"missing required top-level key '{k}'")
    if errs:
        raise ConfigErrorV2("; ".join(errs))

    if "flags_from_map" not in cfg["step_0a"]:
        errs.append("step_0a.flags_from_map is required (the challenge layer consumes it)")

    mods = cfg["step_0"].get("modules", [])
    if not mods:
        errs.append("step_0.modules is empty — at least a deposit module is required")
    unknown = [m for m in mods if m not in KNOWN_MODULES]
    if unknown:
        errs.append(f"unknown modules {unknown}; known: {sorted(KNOWN_MODULES)}")
    if mods and not unknown and "balance_driven_deposits" not in mods:
        errs.append("no deposit module loaded — a bank needs a funding side")

    a = cfg["assumptions"]
    missing = [k for k in ASSUMPTION_REQUIRED if k not in a]
    if missing:
        errs.append(f"missing required assumptions: {missing}")
    if "rate_path_q" in a and (not isinstance(a["rate_path_q"], list) or len(a["rate_path_q"]) != 12):
        errs.append("rate_path_q must be a 12-quarter list of annual rates")
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
        if p.get("rate_type") == "fixed" and p.get("yield_ann") is None:
            errs.append(ctx + "fixed rate requires 'yield_ann'")
        if p.get("measurement") == "fair_value" and p.get("discount_spread_ann") is None:
            errs.append(ctx + "fair-value election requires 'discount_spread_ann'")
        _range_check(p, PROD_RANGES, ctx, errs)
        mb = p.get("mortgage_banking")
        if mb:
            _range_check(mb, MB_RANGES, ctx + "mortgage_banking.", errs)

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
