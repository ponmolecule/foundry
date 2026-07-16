"""Field library — the INPUT_CONCORDANCE superset as code (INPUT_SPEC §3, P5).

Every input concept from both ancestor artifacts has exactly one disposition here:
a typed driver on an archetype, a defaulted field on an archetype, a global (Tier A/B),
a DERIVED fact (never asked), or a PHASE2 item carried with its ontology disposition.

Progressive disclosure is structural: fields_for(activations) generates the input
surface, so a deposits-only engagement never sees a lending field. Grounded in the
chassis's actual assumption keys (Solstice/Blackland goldens); gate T19 enforces
closure — no chassis-consumed key may lack a disposition, and no library field may
name a key the chassis doesn't consume.

Defaults provenance: engine_default placeholders, clearly labeled, swapped for
CharterIQ-certified peer values when the substrate gates open (standing decision).
"""

# ---- Tier A/B: asked once, archetype-independent -------------------------
TIER_A = ["institution_name", "charter_type", "state_market", "opening_date",
          "pre_open_months", "cblr_election", "peer_archetype",
          "de_novo_period_years", "tax_rate_override"]
TIER_B = ["initial_capital", "org_costs_pre_open", "pre_open_payroll_monthly",
          "staged_raises"]

# ---- Archetypes: runnable today (chassis modules) -------------------------
# driver = typed by the user (identity/strategy); defaults = pre-filled,
# provenance engine_default, materiality high|med|low (flags fire on
# unreviewed high). Field names are chassis assumption keys, verbatim.
ARCHETYPES = {
    "funnel_deposit": {
        "label": "Digital / funnel deposits",
        "module": "core_deposits",
        "drivers": ["marketing_budget_m", "new_accts_per_marketing_dollar",
                     "avg_balance_checking", "avg_balance_savings",
                     "savings_share_accounts"],
        "defaults": {
            "checking_rate": "high", "savings_rate": "high",
            "deposit_beta_up": "high", "monthly_attrition": "high",
            "balance_ramp_months": "med", "migration_accounts_m1": "med",
            "migration_decay": "low",
        },
    },
    "relationship_deposit": {
        "label": "Relationship / commercial deposits",
        "module": "core_deposits",
        "drivers": ["bankers_start", "bankers_add_per_m", "bankers_max",
                     "new_relationships_per_banker_m",
                     "avg_deposit_per_relationship"],
        "defaults": {
            "interest_bearing_share": "high", "savings_rate": "high",
            "deposit_beta_up": "high", "monthly_attrition": "high",
            "balance_ramp_months": "med", "onboarding_min_per_rel": "low",
            "service_min_per_rel_m": "low",
            "service_charge_per_rel_m": "med", "tm_fee_rate_ann": "med",
        },
    },
    "commercial_lending": {
        "label": "Commercial lending (segments: CRE, C&I, ...)",
        "module": "commercial_lending",
        "drivers": ["lenders_start", "lenders_add_per_m", "lenders_max",
                     "loan_segments"],
        "defaults": {
            "credit_admin_min_per_loan_m": "low",
        },
        "segment_note": ("loan_segments rows carry per-segment drivers "
                          "(orig_per_lender_m, avg_loan_size, yield) and "
                          "per-segment defaults (ramp_m, amort_annual, "
                          "nco_mature, nco_ramp_m, allowance_coverage)"),
    },
    "revolving_credit": {
        "label": "Card / revolving credit",
        "module": "revolving_credit",
        "drivers": ["card_penetration", "card_avg_balance", "card_yield"],
        "defaults": {
            "card_penetration_ramp_m": "med", "card_nco_mature": "high",
            "card_nco_ramp_m": "med", "allowance_coverage": "high",
            "interchange_rate": "med", "monthly_debit_spend_per_acct": "med",
        },
    },
    "payments_fees": {
        "label": "Payments & account fees",
        "module": "payments_fees",
        "drivers": [],
        "defaults": {"fee_per_acct_m": "med"},
    },
}

# ---- Capacity/opex overlay (Tier E): defaulted, archetype-conditional ----
CAPACITY_DEFAULTS = {
    "always": {"fixed_exec_team_m": "med", "occupancy_other_m": "med",
                "tech_core_base_m": "med", "productive_hours_m": "low",
                "loaded_cost_ops_fte_m": "med"},
    "funnel_deposit": {"kyc_reviews_per_new_acct": "low",
                        "kyc_min_per_review": "low",
                        "fraud_alerts_per_1k_accts_m": "low",
                        "min_per_alert": "low",
                        "service_contacts_per_acct_m": "low",
                        "min_per_contact": "low", "tech_per_acct_m": "med"},
    "relationship_deposit": {"tech_per_acct_m": "med"},
    "revolving_credit": {},
    "commercial_lending": {},
    "payments_fees": {},
}

# ---- DERIVED: never asked; source of truth stated -------------------------
DERIVED = {
    "securities_balance": "funding waterfall residual (M6)",
    "cash_balance": "cash_target_pct_deposits x deposits (M6)",
    "overnight_borrowings": "funding waterfall residual (M6)",
    "regulator_identity": "charter_type + state (resolver)",
    "capital_thresholds": "REG_PARAMS (versioned, cited)",
    "risk_weights": "archetype mapping facts",
    "rc_line_mapping": "archetype mapping facts",
    "fte_counts": "capacity engine (M8) from module minutes",
}
# Globals still asked (rates/treasury pricing), defaulted not typed:
GLOBAL_DEFAULTS = {"fed_funds": "high", "cash_target_pct_deposits": "med",
                    "cash_yield": "med", "securities_yield": "high",
                    "tax_rate": "med"}

# ---- PHASE2: carried with ontology dispositions (grayed cards) ------------
PHASE2 = {
    "time_deposits": "Maturity-ladder liability (M11) — CDs, brokered, term advances",
    "partner_channel": "Partner-channel volume (M12) — BaaS/sponsorship",
    "construction": "Draw-schedule asset (M13)",
    "mortgage_banking_pipeline": "Pipeline / gain-on-sale (M14)",
    "bhc_layer": "Holding-company view — aligned with Patrick's V2 plan",
}


def fields_for(activations):
    """Progressive disclosure: the exact input surface for a set of archetype
    activations. Returns {'typed': [...], 'defaults': {field: materiality}}.
    Tier A/B always present; nothing else appears without its archetype."""
    unknown = [a for a in activations if a not in ARCHETYPES]
    if unknown:
        raise KeyError(f"unknown archetypes: {unknown} (phase-2 items cannot activate)")
    typed = list(TIER_A) + list(TIER_B)
    defaults = dict(GLOBAL_DEFAULTS)
    defaults.update(CAPACITY_DEFAULTS["always"])
    for a in activations:
        typed += [f for f in ARCHETYPES[a]["drivers"] if f not in typed]
        for f, mat in ARCHETYPES[a]["defaults"].items():
            defaults[f] = mat
        for f, mat in CAPACITY_DEFAULTS.get(a, {}).items():
            defaults[f] = mat
    typed = [f for f in typed if f not in defaults]
    return {"typed": typed, "defaults": defaults}


def typed_budget(activations):
    """Typed-value count for the budget rule (P6): <=40 two-product, <=70 four."""
    return len(fields_for(activations)["typed"])
