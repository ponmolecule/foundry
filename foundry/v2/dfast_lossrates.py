"""DFAST supervisory severely-adverse loss-rate registry.

Same doctrine as regparams.py: values resolve from this module, never from
memory; each vintage block carries its citation and a verified date; updating
means ADDING a new vintage block, never editing history (the Fed re-runs and
re-publishes these annually).

These are the Federal Reserve's published *modeled loss rates* by loan
category under the supervisory **severely adverse** scenario — nine-quarter
cumulative losses as a percent of balance. They are the external anchor for
Foundry's DFAST stress scenario: the macro->loss sensitivity Foundry's own
data window cannot measure (see docs/MACRO_STRESS_SCOPING.md) is imported from
here instead of estimated.

WHAT THESE ARE (and are not):
  - Portfolio-level ("Average") loss rates per category, cumulative over the
    9-quarter horizon, as a share of initial balance. This is the coarsest
    published figure per category (the "typical" hypothetical portfolio, or
    the portfolio-average of the segment table) — deliberately, because a de
    novo reports only Call Report aggregates, NOT the FR Y-14 loan-level
    grids (FICO/LTV/rating) that drive the Fed's finer sub-segment rates.
  - NOT the base case. These apply ONLY inside the optional "dfast_severe"
    scenario. They never touch the client's own charge-off assumptions, and
    never replace the existing Credit Deterioration (CO x mult) scenario —
    the contrast between the two is intended.
  - NOT accounting-adjusted. The Fed notes its published loss rates exclude
    the accounting adjustments used to translate losses into net income.
    Foundry's own provision/allowance mechanism performs that translation, so
    the overlay supplies the LOSS RATE only and lets the existing provision
    path carry it to capital. Do NOT double-count.

MAPPING: keyed to Foundry's call_report_line loan lines so the overlay applies
each rate to the matching product's projected balance through the existing
per-product charge-off path. Rates are cumulative-9Q; the overlay is
responsible for converting to the per-quarter flow the engine consumes (the
engine clock is quarterly — see the overlay design note).
"""

# Proposed / watch note: the supervisory stress framework itself had an open
# proposal (Oct 2025) as of the REG_PARAMS pending-rule watch. That affects
# scenario *design*, not these published rates; annotated, not encoded.

DFAST_LOSSRATES = {
    "version": "DFAST-2025",
    "scenario": "severely adverse",
    "horizon_quarters": 9,
    "basis": "cumulative nine-quarter loss as percent of balance; portfolio-average per category",
    "published": "2025-06",
    "scenario_vintage": "2024 Stress Test severely adverse scenario "
                        "(portfolio data as of 2023-12-31, scenario published Feb 2024)",
    "verified": "2026-07-25",
    "citation": "Board of Governors of the Federal Reserve System, 2025 Supervisory Stress "
                "Test Methodology (June 2025), 'Modeled Loss Rates' — Tables 22 (corporate/"
                "typical), 24 & 27 (CRE), 32 (first-lien mortgage/typical), 37 (credit card/"
                "typical). www.federalreserve.gov/publications/2025-june-supervisory-stress-"
                "test-methodology-modeled-loss-rates.htm",
    "disclosures": [
        "Portfolio-average rates only; de novo lacks FR Y-14 loan-level grids for finer rates.",
        "Loss rates EXCLUDE accounting adjustments to net income (Fed 'Explanatory Notes on "
        "Model Disclosures'); Foundry's provision path performs that translation.",
        "Adopting these applies the Fed's severe scenario and the industry loss-given-macro "
        "relationship to a de novo with no seasoning: a supervisory-calibrated BENCHMARK, not "
        "a forecast of this specific bank.",
    ],

    # Per Foundry call_report_line -> cumulative-9Q severe loss rate (as a fraction of balance).
    # Values are the published portfolio-average / typical-portfolio figures for each category.
    "rates": {
        # C&I / commercial: corporate 'typical' hypothetical portfolio (Table 22 = 5.8%).
        "loanCommercial": {
            "rate": 0.058,
            "source": "Table 22, typical corporate portfolio",
            "note": "corporate/C&I typical portfolio, 9Q cumulative",
        },
        # CRE: 'typical' hypothetical CRE portfolio (Table 27 = 5.5%).
        "loanCRE": {
            "rate": 0.055,
            "source": "Table 27, typical CRE portfolio",
            "note": "income-producing + construction blended 'typical'; construction-only avg is "
                    "higher (Table 24 construction = 10.5%)",
        },
        # Construction & land: CRE construction-loans portfolio-average (Table 24 = 10.5%).
        "loanConstruction": {
            "rate": 0.105,
            "source": "Table 24, construction loans (portfolio average)",
            "note": "distinct, higher line for construction & land development",
        },
        # 1-4 family first-lien residential mortgage: 'typical' portfolio (Table 32 = 2.5%).
        "loanMortgage": {
            "rate": 0.025,
            "source": "Table 32, typical first-lien mortgage portfolio",
            "note": "first-lien residential; junior liens/HELOC not separately mapped",
        },
        # Credit card: 'typical' hypothetical card portfolio (Table 37 = 19.7%).
        "loanCreditCard": {
            "rate": 0.197,
            "source": "Table 37, typical credit card portfolio",
            "note": "domestic bank card typical portfolio, 9Q cumulative",
        },
        # Other consumer: no single published 'typical' consumer figure in the modeled-loss-rate
        # tables (card is broken out; other consumer is modeled separately and not published as a
        # single portfolio-average here). Left absent deliberately rather than guessed — the
        # overlay falls back to the client's own rate for any unmapped line (additive, never a
        # fabricated stress). Populate when a cited figure is adopted.
    },
}

# Vintage history is kept as a list so older cycles remain resolvable and auditable;
# newest first. Add a new block each DFAST cycle; never edit a prior one.
DFAST_VINTAGES = [DFAST_LOSSRATES]


def dfast_rates(version=None):
    """Resolve a DFAST loss-rate block by version; default = newest.
    Returns the block dict. Never falls back to memory — raises if a named
    version is not present."""
    if version is None:
        return DFAST_VINTAGES[0]
    for v in DFAST_VINTAGES:
        if v["version"] == version:
            return v
    raise KeyError(f"DFAST vintage {version!r} not in registry; "
                   f"available: {[v['version'] for v in DFAST_VINTAGES]}")
