"""Configuration I/O: the upload door and the T14 fail-closed validator.

A Foundry engagement configuration is a single JSON object mirroring the
Tier 3 Python configs. Top-level required keys:

  engagement_id, client_legal_name, proposed_bank, config_version,
  config_frozen, step_0 (with .modules), constraints, target_state,
  peer_query, assumptions

step_0.modules names Tier 2 modules from foundry.modules.REGISTRY. Each
module contributes required assumption keys (below); the chassis has its
own always-required set. Validation fails closed with precise, actionable
errors — an invalid configuration never produces partial financials.
"""
from .modules import REGISTRY

class ConfigError(ValueError):
    pass


TOP_REQUIRED = ["engagement_id", "client_legal_name", "proposed_bank",
                "config_version", "config_frozen", "step_0", "constraints",
                "target_state", "peer_query", "assumptions",
                # seam fix (v2 ledger A.13): run() consumes these; a config that
                # validates must run — validation now covers everything behind it
                "hq", "step_minus_1", "step_0a", "step_1", "assumption_tags"]

CHASSIS_REQUIRED = ["cash_target_pct_deposits", "cash_yield", "securities_yield",
                    "productive_hours_m", "loaded_cost_ops_fte_m", "fixed_exec_team_m",
                    "tech_core_base_m", "tech_per_acct_m", "occupancy_other_m",
                    "org_costs_pre_open", "tax_rate", "fed_funds",
                    "savings_rate", "deposit_beta_up", "monthly_attrition",
                    "balance_ramp_months"]

MODULE_REQUIRED = {
    "core_deposits": ["migration_accounts_m1", "migration_decay",
                      "new_accts_per_marketing_dollar", "marketing_budget_m",
                      "avg_balance_savings", "avg_balance_checking",
                      "savings_share_accounts", "checking_rate"],
    "relationship_deposits": ["bankers_start", "bankers_add_per_m", "bankers_max",
                              "new_relationships_per_banker_m",
                              "avg_deposit_per_relationship", "interest_bearing_share"],
    "revolving_credit": ["card_penetration", "card_penetration_ramp_m",
                         "card_avg_balance", "card_yield", "card_nco_mature",
                         "card_nco_ramp_m", "allowance_coverage"],
    "commercial_lending": ["lenders_start", "lenders_add_per_m", "lenders_max",
                           "loan_segments"],
    "payments_fees": ["monthly_debit_spend_per_acct", "interchange_rate",
                      "fee_per_acct_m"],
    "relationship_fees": ["service_charge_per_rel_m", "tm_fee_rate_ann"],
    "capacity_expenses": ["kyc_reviews_per_new_acct", "kyc_min_per_review",
                          "fraud_alerts_per_1k_accts_m", "min_per_alert",
                          "service_contacts_per_acct_m", "min_per_contact"],
    "branch_capacity_expenses": ["onboarding_min_per_rel", "service_min_per_rel_m",
                                 "credit_admin_min_per_loan_m", "loan_segments"],
    "investment_portfolio": [],
}

# (key, min, max, reason) — nonsense fails closed, not "best effort"
RANGES = [
    ("monthly_attrition", 0.0, 0.15, "attrition must be a rate in [0, 0.15]; negative attrition mints customers"),
    ("savings_rate", 0.0, 0.30, "deposit rate must be in [0, 0.30]"),
    ("tax_rate", 0.0, 0.60, "tax rate must be in [0, 0.60]"),
    ("cash_target_pct_deposits", 0.0, 0.50, "cash target must be in [0, 0.50] of deposits"),
    ("card_nco_mature", 0.0, 0.40, "loss rate must be in [0, 0.40]"),
    ("deposit_beta_up", 0.0, 1.5, "deposit beta must be in [0, 1.5]"),
]


def validate_config(cfg):
    errs = []
    for k in TOP_REQUIRED:
        if k not in cfg:
            errs.append(f"missing required top-level key '{k}'")
    if errs:
        raise ConfigError("; ".join(errs))

    if "flags_from_map" not in cfg["step_0a"]:
        errs.append("step_0a.flags_from_map is required (challenge layer consumes it)")

    mods = cfg["step_0"].get("modules", [])
    if not mods:
        errs.append("step_0.modules is empty — at least a deposit module is required")
    unknown = [m for m in mods if m not in REGISTRY]
    if unknown:
        errs.append(f"unknown modules {unknown}; known: {sorted(REGISTRY)}")
    dep_mods = [m for m in mods if m in REGISTRY and REGISTRY[m][1] == "deposits"]
    if mods and not unknown and not dep_mods:
        errs.append("no deposit module loaded — a bank needs a funding side")

    a = cfg["assumptions"]
    need = list(CHASSIS_REQUIRED)
    for m in mods:
        need += MODULE_REQUIRED.get(m, [])
    missing = [k for k in dict.fromkeys(need) if k not in a]
    if missing:
        errs.append(f"missing required assumptions for loaded modules: {missing}")

    for k, lo, hi, reason in RANGES:
        if k in a and not (lo <= a[k] <= hi):
            errs.append(f"'{k}' = {a[k]} out of range: {reason}")

    ts = cfg["target_state"]
    if "initial_capital" not in ts or ts["initial_capital"] <= 0:
        errs.append("target_state.initial_capital must be present and positive")
    if "assets_yr3" not in ts or ts["assets_yr3"] <= 0:
        errs.append("target_state.assets_yr3 must be present and positive")

    for c in cfg["constraints"]:
        for k in ("key", "value", "text", "source"):
            if k not in c:
                errs.append(f"constraint {c.get('key','<?>')} missing field '{k}'")
    if not any(c.get("key") == "leverage_min" for c in cfg["constraints"]):
        errs.append("constraints must include 'leverage_min' (every de novo carries a capital commitment)")

    for k in ["consumer_loan_share", "fee_income_share", "core_funding_share", "digital_channel"]:
        if k not in cfg["peer_query"]:
            errs.append(f"peer_query missing '{k}'")

    if errs:
        raise ConfigError("; ".join(errs))
    return cfg


def slugify(name):
    s = "".join(ch.lower() if ch.isalnum() else "-" for ch in name)
    while "--" in s:
        s = s.replace("--", "-")
    return s.strip("-")[:40] or "engagement"
