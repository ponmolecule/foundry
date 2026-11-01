# r434 — Field system on products and customer acquisition

Built on r433 (5132052). Presentation only: no calculation, configuration-shape or save changes. Every control keeps its own handler; the console regroups and restyles what it already renders.

Product setup steps (lending, deposits, off-balance-sheet), every step:

- Fields move from a three-across grid of top-labelled boxes to one 150px right-aligned label column, the same as the fee-stream editor.
- Amounts are 210px including their unit; text 320px; dropdowns fitted to their longest option (minimum 240px). Rate type and reference index become compact segmented buttons instead of full-width bars.
- Managed-series rows (Yield, Rate paid) take their caption into the label column (the caption element moves, so its text appears once), and their path becomes Flat | Growth | Schedule beside the value.
- Notes sit under the field column. Loan reporting category and originate-to-sell use the same rows.
- When the step is narrow (Assumptions panel open, small screens), labels stack above their fields; the results chart keeps its own column whenever the step is at least 560px wide.
- Loan-production panels (separate payment and prepayment rates) keep their two-column layout for now.

Customer acquisition:

- Channel editor: Acquisition channel and method on their own labelled rows; every driver row (pool, conversion, spend, CAC, FTEs, productivity, compensation, AUC) on one label column; path as Flat | Growth | Schedule; a growth path shows its growth rate and period on a second line ("Growth 5.00 % per year"); linked-source dropdowns stay inside the editor; Remove channel moves to the editor header.
- Feed settings: feed name, opening customers and opening AUC on the label column; the attrition block (attrition, path, timing) aligned with them.

Validation: tests_r434_field_system_products (Python wrapper + Playwright harness) checks non-mutation across every step of every product, label alignment and sizes on lending and deposits, the lifted yield caption and its path buttons writing the product, compact rate-type switch, stacking when narrow, the channel editor's label column, header remove, name and path edits writing the channel, containment, and the feed settings layout. Full suite compared against the r433 baseline.

ZIP contains delivery/foundry-full.bundle. BUILD_STAMP = foundry-r434-field-system-products.
