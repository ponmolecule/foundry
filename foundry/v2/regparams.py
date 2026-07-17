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
}
