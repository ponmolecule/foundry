# r407 — Beginning-balance product stream costs

Adds Beginning of period to the existing own-balance measure selector for loan and deposit streams. Existing streams keep their selected measure; streams without a measure retain the historical average default. The choice applies to both stream revenue and balance-based operating cost.

For monthly models, beginning is the prior month-end. Ordinary quarterly models use the quarter beginning. Repayment-profile loans with canonical monthly replay accrue each month's beginning balance and sum within a quarter. The selected rate remains annual and is periodized by the engine. No expense is moved automatically: when replacing an existing Opex formula, reconcile and remove the old line, and check gross-up eligibility.

Validated against a beginning-balance Opex formula with an original-funding repayment profile in monthly and quarterly runs; browser authoring, r405 cost tests, r406 layout tests, and repayment-profile regressions pass.
