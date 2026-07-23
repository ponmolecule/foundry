"""Versioned regulatory parameters — resolved from this set, never from memory.

Doctrine adopted 2026-07-11 after a stale-memory incident: Foundry carried the
pre-2026 CBLR calibration (9%) after the interagency final rule lowered it.
Every regulatory threshold used by the engine or surface resolves from this
module; each version block carries its citations and a verified date. Updating
a parameter means adding a new version block with new citations, never editing
history.
"""

# Proposed-rule watch: named, dated, status "proposed" — annotated in the artifact,
# NEVER encoded as parameters until final. Standing client rule (2026-07-13).
PENDING_RULES = [
    {"name": "Standardized Approach reform proposals (incl. elimination of the MSA "
             "CET1 deduction in favor of a 250% risk weight; est. 7.7\u20138.3% CET1 "
             "requirement reduction for smaller banks)",
     "status": "PROPOSED \u2014 not law; comments closed 2026-06-18; final rule pending",
     "would_affect": ["MSA threshold deduction (12 CFR 3.22(d)) in the capital derivation",
                       "standardized RWA stack (pilot scope)"],
     "watch_opened": "2026-07-13"},
    {"name": "Stress-testing framework proposal (Oct 2025)",
     "status": "PROPOSED \u2014 pending",
     "would_affect": ["scenario framework context; no direct engine parameter"],
     "watch_opened": "2026-07-13"},
]

REG_PARAMS = {
    "version": "2026.07.a",
    "effective": "2026-07-01",
    "verified": "2026-07-11",
    "citations": [
        "Regulatory Capital Rule: Community Bank Leverage Ratio Framework, "
        "91 FR 22973 (Apr. 29, 2026), FR Doc. 2026-08298",
        "OCC Bulletin 2026-15 (rescinds OCC Bulletin 2021-66)",
        "GAO major-rule report B-338364",
    ],
    "pca_well_capitalized": {   # 12 CFR 6.4(b)(1) (OCC) / 12 CFR 324.403 (FDIC)
        "cet1_rwa": 0.065, "tier1_rwa": 0.08, "total_rwa": 0.10, "leverage": 0.05,
    },
    "risk_weights": {           # 12 CFR 324.32 standardized approach
        "cash_fed": 0.0,               # balances at Federal Reserve Banks
        "bank_exposures": 0.20,        # deposits at / exposures to depository institutions
        "agency_securities": 0.20,     # GSE/agency debt (modeling assumption: books are agency)
        "resi_first_lien": 0.50,       # qualifying 1-4 family first lien
        "corporate_consumer_cre": 1.00,
        "classified": 1.50,            # substandard/doubtful (no classification concept modeled yet)
        "msr_nondeducted": 2.50,       # 12 CFR 324.32(l) — below-threshold MSAs
    },
    "ccf": {                    # 12 CFR 324.33 credit conversion factors
        "commitments_le_1y": 0.20, "commitments_gt_1y": 0.50, "default": 0.50,
    },
    "tier2_alll_cap_pct_rwa": 0.0125,   # 12 CFR 324.20(d)(3)
    "assessments": {
        # FDIC base per 12 USC 1817(b)(2)(A): avg consolidated assets - avg tangible equity
        # (D-P14 fix: NOT deposits). Rate is an engagement assumption inside the
        # 12 CFR 327 schedule for a new small institution; OCC per 12 CFR 8.
        "fdic_bp_ann": 5.0, "occ_bp_ann": 1.5,
    },
    "cblr": {
        "requirement": 0.08,            # lowered from 0.09, eff. 2026-07-01
        "grace_floor": 0.07,            # must stay above this during grace
        "grace_max_consecutive_q": 4,   # extended from 2 quarters
        "grace_limit_q": 8,             # max grace quarters...
        "grace_window_q": 20,           # ...within the prior 20 quarters
        "assets_ceiling_usd": 10_000_000_000,
        "obs_share_max": 0.25,
        "trading_share_max": 0.05,
    },
    "tax": {
        # DTAs arising from NOL/credit carryforwards (net of VA and DTLs) are
        # deducted from CET1 IN FULL — no threshold; the 10%/25% machinery
        # applies only to temporary-difference DTAs. 12 CFR 3.22(a).
        "dta_nol_cet1_deduction": 1.0,
        # Post-TCJA federal NOLs: indefinite carryforward, utilization capped
        # at 80% of taxable income per year. IRC 172(a)(2).
        "nol_utilization_limit_pct": 0.80,
    },
    # Cohort-hygiene floors for examiner-facing peer bands (CHARTER_FILTERED_COHORT_SPEC,
    # 2026-07-21). NOT a data edit and NOT winsorization — a COHORT filter for a
    # specific comparison context. The raw substrate values stay raw; these floors
    # define which bank-quarters qualify as meaningful LENDING-bank peers. Floors are
    # stated round numbers one order of magnitude below the smallest genuine lending
    # bank, per the spec — targeting the near-nil-denominator MECHANISM, not a charter
    # type, so they catch de novos, special-purpose, and any future thin filer uniformly.
    "cohort_hygiene": {
        # risk-based ratios (tier1/cet1/total_rbc): require $25M RWA. Below this a
        # small numerator swing yields triple-digit ratio swings.
        "rwa_floor_000s": 25000,
        # leverage / asset-scaled ratios: require $50M assets.
        "assets_floor_mm": 50,
        # efficiency / revenue-scaled: revenue dollars are NOT cleanly stored in the
        # substrate (only net figures — net_income/ppnr — exist, not gross NII+nonII),
        # so a revenue FLOOR isn't cleanly computable. The ratio-ceiling below replaces
        # it: a near-zero-denominator artifact is self-identifying by its OUTPUT (a
        # 54,700% efficiency ratio is obviously an artifact) without needing the
        # denominator at all — denominator-agnostic and more robust than a floor.
        "revenue_floor_000s": 100,   # retained for provenance; superseded by ratio ceilings
        # ratio-ceiling guard: exclude a bank-quarter whose RATIO VALUE exceeds a sanity
        # ceiling — catches near-nil-denominator artifacts regardless of which
        # denominator went to zero, no denominator lookup required. Per-metric because
        # a plausible max differs (capital ratios can legitimately reach ~100% for a
        # young all-equity bank; efficiency should never exceed a few hundred %).
        "ratio_ceilings": {
            "tier1_ratio": 1000.0, "cet1_ratio": 1000.0, "total_rbc_ratio": 1000.0,
            "leverage_ratio": 500.0, "efficiency_ratio": 500.0,
        },
        "ratio_ceiling_default": None,   # None = no ceiling for metrics not listed (roa/nim)
        "spec": "CHARTER_FILTERED_COHORT_SPEC 2026-07-21",
        "basis": "cohort filter for examiner-facing lending-bank comparison; "
                 "raw values unchanged; extract-raw remains authoritative",
    },
}
