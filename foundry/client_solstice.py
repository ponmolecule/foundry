"""Client configuration: Solstice Bank (in organization).

FICTITIOUS ENGAGEMENT — all facts invented for platform demonstration.
This file IS the Tier 3 configuration object: steps -1 through 3 of the
engagement sequence, captured as data. No code below this layer varies
per client.
"""

CLIENT = {
    "engagement_id": "ENG-2026-0001",
    "client_legal_name": "Solstice Financial, Inc.",
    "proposed_bank": "Solstice Bank (in organization)",
    "hq": "Austin, TX",
    "prepared_by": "Klaros Group / Foundry engagement team",
    "config_version": "1.3",
    "config_frozen": "2026-06-19",

    # ---- Step -1: should this be a bank? (decision memo summary) ----
    "step_minus_1": {
        "decision": "proceed_de_novo",
        "alternatives_priced": {
            "remain_sponsor": "Program fees + reserve requirements cost ~41bp of average deposits; no balance-sheet economics; partner concentration risk realized once (2024 partner exit, 11-week migration).",
            "acquire": "Two targets screened; culture/tech integration cost exceeds de novo timeline advantage at current pricing.",
            "de_novo": "Full deposit economics, card program in-house, interchange retained. Accepts 30-42 month path and $135M capital raise.",
        },
    },

    # ---- Step 0: how does the bank make money? ----
    "step_0": {
        "one_sentence": ("We gather consumer deposits at scale through the Solstice app, "
                         "deploy them into a securities portfolio and an in-house credit card "
                         "receivable book, and retain debit interchange the sponsor model gives away."),
        "earning_engine": "hybrid_deposit_led",
        "modules": ["core_deposits", "revolving_credit", "payments_fees",
                    "investment_portfolio", "capacity_expenses"],
    },

    # ---- Step 0A: entity & funds-flow map (gate: approved 2026-06-05) ----
    "step_0a": {
        "entities": {
            "parent": "Solstice Financial, Inc. — app, brand, marketing, 940k funded accounts (via current sponsor)",
            "bank": "Solstice Bank — deposits, card program, securities, payments",
        },
        "flags_from_map": [
            {"id": "MAP-01", "class": "likely_regulatory_objection",
             "text": "Marketing and customer acquisition sit in the parent under a services agreement; "
                     "bank depends on an affiliate it does not control for its sole growth channel."},
            {"id": "MAP-02", "class": "advisory",
             "text": "Fraud-ops staff currently employed by parent; plan migrates them to bank by open date. "
                     "Examiner will test day-one operational independence."},
        ],
        "map_approved": "2026-06-05",
    },

    # ---- Step 1: license (decision, derived) ----
    "step_1": {
        "charter": "Texas state nonmember bank",
        "regulators": ["Texas Department of Banking", "FDIC (insurance + primary federal)"],
        "rationale": "Deposit-led consumer model with modest lending; no parent BHC appetite for Fed membership; ILC rejected on timeline/political risk.",
    },

    # ---- Step 2: pre-filing constraints (binding, provenance-tagged) ----
    "constraints": [
        {"key": "leverage_min", "value": 0.10,
         "text": "Tier 1 leverage >= 10% through year 3",
         "source": "FDIC pre-filing memo 2026-05-12"},
        {"key": "card_receivables_max_share", "value": 0.30,
         "text": "Card receivables <= 30% of total assets through year 3",
         "source": "TX DOB pre-filing letter 2026-05-20"},
        {"key": "brokered_max_share", "value": 0.10,
         "text": "Brokered deposits <= 10% of total deposits; migrated app deposits treated as core "
                 "given direct customer relationship",
         "source": "FDIC field office letter 2026-06-02"},
        {"key": "marketing_linkage", "value": None,
         "text": "Deposit growth must be explicitly linked to acquisition spend in the model",
         "source": "FDIC pre-filing memo 2026-05-12"},
    ],

    # ---- Step 3: target state (stated intent, coarse bands) ----
    "target_state": {
        "assets_yr3": 860e6, "deposits_yr3": 735e6,
        "card_receivables_yr3": 210e6, "securities_yr3": 430e6,
        "headcount_yr3": 96, "footprint": "national digital",
        "initial_capital": 135e6,
    },

    # ---- Step 3 feature vector for peer selection (intent only, no model outputs) ----
    "peer_query": {
        "log_assets_yr3": None,          # computed from target_state
        "consumer_loan_share": 210/860,
        "fee_income_share": 0.24,        # interchange + fees / revenue, stated intent
        "core_funding_share": 0.95,
        "digital_channel": 1.0,
    },

    # ---- Step 5: calibrated assumptions (values chosen AFTER cohort freeze 2026-06-12) ----
    "assumptions": {
        "migration_accounts_m1": 14000,   # funded accounts migrating from parent base, month 1
        "migration_decay": 0.93,          # geometric monthly decay of migration flow
        "new_accts_per_marketing_dollar": 1/165.0,  # CAC $165 per funded account
        "marketing_budget_m": [1.0e6]*6 + [1.2e6]*6 + [1.4e6]*12 + [1.5e6]*12,
        "monthly_attrition": 0.014,
        "avg_balance_savings": 2900.0, "avg_balance_checking": 1400.0,
        "savings_share_accounts": 0.58,
        "balance_ramp_months": 9,         # new accounts reach avg balance over this ramp
        "fed_funds": 0.0450,
        "savings_rate": 0.0360, "checking_rate": 0.0010,
        "deposit_beta_up": 0.55,
        "cash_yield": 0.0440, "securities_yield": 0.0445,
        "cash_target_pct_deposits": 0.08,
        "card_penetration": 0.28,         # share of active accounts holding the card at maturity
        "card_penetration_ramp_m": 18,
        "card_avg_balance": 2200.0,
        "card_yield": 0.2150,
        "card_nco_mature": 0.052,         # annualized, mature book
        "card_nco_ramp_m": 12,
        "allowance_coverage": 0.065,
        "interchange_rate": 0.0105,       # Durbin-exempt while < $10B
        "monthly_debit_spend_per_acct": 610.0,
        "fee_per_acct_m": 0.55,
        # capacity-driven opex
        "kyc_reviews_per_new_acct": 1.0, "kyc_min_per_review": 6.0,
        "fraud_alerts_per_1k_accts_m": 9.0, "min_per_alert": 22.0,
        "service_contacts_per_acct_m": 0.09, "min_per_contact": 7.5,
        "productive_hours_m": 140.0, "loaded_cost_ops_fte_m": 8100.0,
        "fixed_exec_team_m": 610000.0,    # execs, risk, compliance leadership, finance
        "tech_core_base_m": 240000.0, "tech_per_acct_m": 0.42,
        "occupancy_other_m": 150000.0,
        "org_costs_pre_open": 9.5e6,      # expensed at month 0
        "tax_rate": 0.24,
    },
    # assumption metadata: confidence tags + which prior each maps to
    "assumption_tags": {
        "migration_accounts_m1": ("management_estimate", None),
        "new_accts_per_marketing_dollar": ("externally_benchmarked", None),
        "avg_balance_savings": ("observed", None),  # parent app data
        "savings_rate": ("management_estimate", "cost_of_deposits_spread"),
        "card_nco_mature": ("externally_benchmarked", "card_nco_mature"),
        "monthly_attrition": ("observed", None),
        "interchange_rate": ("contractual", None),
        "deposit_growth_yr1": ("derived", "deposit_growth_yr1"),
        "opex_per_active_acct": ("derived", "opex_per_active_acct"),
    },
}
