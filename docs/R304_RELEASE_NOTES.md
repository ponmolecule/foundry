# r304 — named Other Assets

Built directly on r303, commit 98242c5527d6404d048cd630c2fc2c3bd42faeaa. This is a fast-forward build.

## What changed

Configuration → Securities & balances now has an Other Assets section beside Other Liabilities. Flat mode retains the historical scalar balance. Formula / level mode has an opening stock, an entered base, and arbitrary named components, each a sum of source × multiplier terms. Entered levels support Flat, Growth and Explicit schedules; linked drivers currently include total bank fee income, Workforce headcount and Fixed Asset levels. This is balance-sheet authoring, not a product.

A monetary income flow can optionally use Days outstanding. Its ending stock is:

    period flow × authored multiplier × days outstanding / (annual day basis / periods per year)

The annual day basis is entered, defaulting to 360. It therefore gives a denominator of 30 monthly, 90 quarterly and 360 annually. This convenience is optional; an entered balance or ordinary multiplier need not use revenue or days. The component name carries no engine behavior. No client names, source cell addresses, client fee rates or receivable-day assumptions are baked into the model.

Example: monthly fee income of $49,538.40, 25 days outstanding, 360 annual day basis and multiplier 1 produces a $41,282.00 receivable. No fee income is recognized again. The stock is a non-earning asset and consumes funding through the existing cash/securities/borrowing allocation. A falling stock releases funding. Interest, where enabled, responds through the existing funding calculations.

Named components and totals appear on the Balance Sheet. The audit adds Other Assets, including sources, day inputs, effective multipliers and calculated amounts; All Series includes their public series. The editable assumptions workbook adds ASSM_OTHER_ASSETS. Call Report other assets and the existing standard 100% other-assets RWA bucket include the new stock.

The tiered bank-asset preview now labels the opening observation Open and the next observation M1/Q1 correctly. It states that observation lag is applied in the expense calculation. No expense-lag economics changed.

## Boundaries

- Existing configurations are not migrated automatically. Switching modes retains the saved formula setup.
- Entered base is seeded from the old flat amount. Set it to zero when components replace that amount.
- Total Other Assets cannot be negative. Signed terms can represent contra adjustments.
- Income links are limited to total pre-expense fee income. Self-dependent Net Income and current interest income are rejected rather than introducing a circular calculation.
- Days outstanding is an average daily flow convention. Quarterly income × days / 90 is not a reconstruction of individual monthly invoices or collections. Use explicit ending levels when that convention is insufficient.
- This is not invoice aging, impairment, bad-debt or detailed collection scheduling. Those are separate economics; stock authoring does not manufacture them.
- Other Liabilities and its existing headcount-based Accounts payable component are unchanged. This release does not turn it into an OpEx/DPO calculation or claim the engagement is reconciled.
- Named components use the existing Other Assets regulatory default, not individually authored risk classifications.

## Validation

See R304_VALIDATION.md. Existing full output and fingerprints are preserved. Newly enabled Other Assets deliberately changes results and run fingerprints for that engagement.
