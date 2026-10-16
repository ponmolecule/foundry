# r338 — Engagement-driven Business Plan Tables (enhanced template)

Direct continuation of r337 83c51982f1af01b996464c11626d6e5dac3dd66a.

Exec Summary → **Business Plan Tables** now downloads the enhanced Business Plan Table layout: one table per
sheet — Balance Sheet EOP (Annual), Income Statement (Annual), Balance Sheet / Income Statement % of Asset,
Financial Performance Highlight, Balance Sheet / Income Statement Quarterly, Interest Rate Assumptions, Net
Interest Income, Interest Income Calculation, one assumption sheet per asset product, Forecasted Capital Levels,
Non-Interest Income, Non-Interest Expense, De Novo Bank Operating Expenses, and a Product Map & Notes sheet.

Engagement-specific rows come from the engine product registry shown on Detail → Per-Product Contributions:
Asset products → Loan Mix rows and one "<Product> Assumptions" sheet each; Liability products → non-interest-
bearing / interest-bearing Deposit Mix, quarterly deposit split and rate rows; Off-BS products → Non-Interest
Income rows (products with revenue), Cost of Revenue rows (products with cost) and Program Migration rows.
Operating Expense categories and other-income lines are the engagement's own. No template product names are
hard-coded; a new engagement produces its own rows and sheets without code changes.

Sourcing: fresh base-case `run_v2` of the posted configuration, $000s, regulator-facing submission window
(default Q1–Q12) at any cadence. Every table ties to its engine total; a residual line appears only when needed
to tie and is labelled. Lines the engine does not produce (Program Migration share, Day-1 capital ratios) are
blank, not zero. Correction versus r337: interest income no longer adds designated-securities-book interest a
second time (it is an "of which" of securities interest).

Unchanged: route POST /api/v31/bpt-cover, request/response contract, filename, UI button, Procfile,
requirements, engine and all other exports. The pre-r338 two-sheet layout remains available in code as
`bpt_cover.build_bpt_cover_legacy`.

New: foundry/v2/bpt_enhanced.py, foundry/v2/tests_bpt_enhanced.py. Updated: foundry/v2/bpt_cover.py
(delegation), foundry/v2/tests_audit_remediation.py D13 (asserts annual + calendar-quarter views on a monthly
model under the new sheet layout).

History note: repository history was rewritten in this release to normalize one historical commit message and
two code comments that named a third-party template (now "Business Plan Table template"). Every commit from
2026-08-23 onward therefore has a new hash; trees, authors, dates and code behavior are otherwise unchanged.
Commit hashes quoted in earlier release notes refer to the pre-rewrite history; the delivery carries the
old→new hash map.
