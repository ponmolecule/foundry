# r410 — Separate formula creation from expense transfer

The Formula costs panel now presents two distinct collapsed actions: Move an existing Operating Expense formula, and Create a new formula cost. Moving explicitly explains that it creates the named stream itself and lists only Formula components. Creating is described as starting a formula from scratch.

The transfer endpoint refuses an existing same-name stream in the target product (case-insensitive, surrounding whitespace ignored), including blank formula placeholders and other stream types. The rejection explains how to inspect the existing stream and leaves the entire draft unchanged. No existing stream is overwritten, merged, or deleted. Existing duplicates require manual inspection and removal of unwanted blank formulas.

No save behavior or expense arithmetic changed. A successful transfer still reconciles financial totals and preserves the selected product and stream.

Validation: full Products browser test verifies cancel/blank/duplicate creation, duplicate transfer without mutation, a subsequent valid reconciled transfer, and navigation stability. Six backend tests cover same-name rejection, non-mutating transfer, financial reconciliation and source links; the transfer HTTP and formula/syntax regression checks pass. Collapsed action layout visually inspected.
