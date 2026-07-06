"""Client configuration: Blackland State Bank (in organization).

FICTITIOUS ENGAGEMENT — gauntlet Bank 2 and the T1 blind-second-client case.
Three ex-community bankers chartering a CRE/C&I commercial bank in the
Dallas-Fort Worth metroplex. This file is pure Tier 3 data.
"""

CLIENT = {
    "engagement_id": "ENG-2026-0003",
    "client_legal_name": "Blackland Bancshares, Inc.",
    "proposed_bank": "Blackland State Bank (in organization)",
    "hq": "McKinney, TX",
    "prepared_by": "Klaros Group / Foundry engagement team",
    "config_version": "1.0",
    "config_frozen": "2026-07-02",
    "archetype": "community_commercial",

    "step_minus_1": {
        "decision": "proceed_de_novo",
        "alternatives_priced": {
            "acquire": "Two DFW targets at 1.6-1.8x TBV; seller expectations exceed de novo cost.",
            "de_novo": "Team's lending relationships are portable; charter cost < acquisition premium.",
        },
    },
    "step_0": {
        "one_sentence": ("We gather commercial operating deposits from DFW businesses our team has "
                         "banked for fifteen years and lend them back as CRE and C&I credit at "
                         "relationship spreads."),
        "earning_engine": "spread_relationship",
        "modules": ["relationship_deposits", "commercial_lending", "relationship_fees",
                    "investment_portfolio", "branch_capacity_expenses"],
    },
    "step_0a": {
        "entities": {
            "parent": "Blackland Bancshares, Inc. — holding company, no operating activities",
            "bank": "Blackland State Bank — all deposits, lending, and operations",
        },
        "flags_from_map": [
            {"id": "MAP-01", "class": "advisory",
             "text": "Two organizers retain board seats at a competing bank until charter approval; "
                     "resignation letters escrowed, examiner will verify timing."},
        ],
        "map_approved": "2026-06-20",
    },
    "step_1": {
        "charter": "Texas state nonmember bank",
        "regulators": ["Texas Department of Banking", "FDIC (insurance + primary federal)"],
        "rationale": "Conventional community charter; no BHC complexity; team's regulatory history is with TX DOB.",
    },

    "constraints": [
        {"key": "leverage_min", "value": 0.09,
         "text": "Tier 1 leverage >= 9% through year 3",
         "source": "FDIC pre-filing memo 2026-06-10"},
        {"key": "cre_max_pct_capital", "value": 3.50,
         "text": "CRE concentration <= 350% of tier 1 capital through year 3",
         "source": "TX DOB / FDIC joint pre-filing letter 2026-06-15"},
    ],

    "target_state": {
        "assets_yr3": 450e6, "deposits_yr3": 385e6,
        "loans_yr3": 225e6, "securities_yr3": 190e6,
        "headcount_yr3": 58, "footprint": "DFW metroplex, 2 branches",
        "initial_capital": 60e6,
    },

    "peer_query": {
        "log_assets_yr3": None,
        "consumer_loan_share": 0.02,
        "fee_income_share": 0.08,
        "core_funding_share": 0.90,
        "digital_channel": 0.0,
    },
    "prior_metrics": ["deposit_growth_yr1", "cost_of_deposits_spread", "efficiency_q12"],

    "assumptions": {
        # relationship deposit engine
        "bankers_start": 5.0, "bankers_add_per_m": 0.25, "bankers_max": 13.0,
        "new_relationships_per_banker_m": 4.8,
        "monthly_attrition": 0.008,
        "avg_deposit_per_relationship": 340000.0,
        "interest_bearing_share": 0.70,
        "balance_ramp_months": 12,
        "fed_funds": 0.0450,
        "savings_rate": 0.0320,          # blended interest-bearing deposit rate
        "deposit_beta_up": 0.35,
        # commercial lending: CRE and C&I as parameterizations of one mechanic
        "lenders_start": 4.0, "lenders_add_per_m": 0.20, "lenders_max": 9.0,
        "loan_segments": [
            {"name": "cre", "orig_per_lender_m": 0.68e6, "ramp_m": 9,
             "amort_annual": 0.08, "yield": 0.0715, "nco_mature": 0.0035,
             "nco_ramp_m": 24, "allowance_coverage": 0.013, "avg_loan_size": 1.6e6},
            {"name": "ci", "orig_per_lender_m": 0.45e6, "ramp_m": 6,
             "amort_annual": 0.22, "yield": 0.0790, "nco_mature": 0.0045,
             "nco_ramp_m": 18, "allowance_coverage": 0.015, "avg_loan_size": 0.45e6},
        ],
        # portfolio & liquidity
        "cash_target_pct_deposits": 0.05,
        "cash_yield": 0.0440, "securities_yield": 0.0445,
        # fees
        "service_charge_per_rel_m": 95.0, "tm_fee_rate_ann": 0.0009,
        # capacity expenses (branch/credit-admin drivers)
        "onboarding_min_per_rel": 240.0, "service_min_per_rel_m": 35.0,
        "credit_admin_min_per_loan_m": 90.0,
        "productive_hours_m": 140.0, "loaded_cost_ops_fte_m": 7400.0,
        "fixed_exec_team_m": 355000.0, "tech_core_base_m": 95000.0,
        "tech_per_acct_m": 4.0, "occupancy_other_m": 205000.0,
        "marketing_budget_m": [55000.0],
        "org_costs_pre_open": 4.5e6,
        "tax_rate": 0.24,
    },
    "assumption_tags": {
        "new_relationships_per_banker_m": ("management_estimate", None),
        "avg_deposit_per_relationship": ("observed", None),      # team's prior book
        "savings_rate": ("externally_benchmarked", "cost_of_deposits_spread"),
        "deposit_growth_yr1": ("derived", "deposit_growth_yr1"),
        "monthly_attrition": ("observed", None),
    },
}
