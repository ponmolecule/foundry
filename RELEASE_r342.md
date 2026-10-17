# Foundry r342

Adds general original-funding portfolio repayment schedules and repairs beginning-balance expense linking. Baseline: r341 / 8749246.

## Repayment basis

Lending → Flow-based lending + fees → Monthly repayment curve now offers:

- Surviving principal: existing cohort paydown behavior, unchanged and the default for existing configurations.
- Original funding: curve percentages schedule gross portfolio paydowns from original monthly funding independently of annual balance losses. The curve starts at age zero and must sum to 100%. Supports natural monthly curves of arbitrary length and opening schedules. Reports the portfolio identity explicitly; it does not claim per-cohort principal conservation.

Original-funding mode requires annual balance losses, reserve-percent allowance, full retention, zero held-aside funding, and no shared capacity transfers. Conflicting settings and negative resulting portfolio balances fail explicitly. No payment or loss is silently clipped to fit a source workbook.

## Beginning-balance expense

Operating expenses → Formula / driver → linked lending balance → Beginning balance is now accepted by validation. Multiply by a periodized rate as usual.

An explicit Expense accrual selector additionally supports Monthly balance × rate, summed. For quarterly runs it uses canonical monthly repayment-profile observations and monthly rates, not a quarter-opening balance or average rate approximation. Missing canonical monthly observations cause an explicit error. Existing model-period formula behavior remains the default.

## Audit and verification

Repayment Monthly includes the selected repayment basis. Formula expense audit notes identify canonical monthly accrual. Tested exact portfolio recurrence, alternative curves, opening schedules, live subscriber-to-purchase links, assumption propagation, monthly/quarterly aggregation, changing monthly rates, public audit generation, incompatible settings and impossible runoff. Existing repayment profiles, account activity, fee quantity links, source catalog, legacy expense formulas, linked lending, shared loan allocation, NIE categories, fee audit, repayment UI and engagement reset checks pass.

No engagement-specific constants or product names were added to engine logic. No user engagement data is bundled. Deploy using the established Git-bundle deployment workflow; the build has not been deployed by this change.
