# Foundry r369

Previous release: r368 / 2273b9c.

Adds opt-in live loan production and beginning-balance repayment to Profile A (monthly/quarterly). New loan counts may remain linked to gross Customer Acquisition flows and multiply an independently scheduled loan amount. Principal payments and prepayments have separate annual Series. Existing loan mechanics remain unchanged until the new method is selected.

Adds signed deferred origination costs/fees with per-loan or percent-funded basis, an independent multiplier, explicit opening balance, scheduled beginning-balance amortization and prepayment catch-up. Net deferred costs change loan carrying amount and amortize through interest once. Principal remains separately inspectable. This method is balance-rate amortization, not an effective-yield or maturity-balloon model.

Adds scheduled allowance targets, explicit opening allowance and release policy. Charge-offs consistently reduce allowance. Zero provision flooring is an explicit option; source sign errors are not reproduced. Conflicting loan mechanics and unsupported Profile B selection fail with explicit errors.

Numbers dialogs and the Loan Rollforward audit sheet expose all principal, carrying, deferred and allowance movements using unrounded engine diagnostics. UI sections retain Balance → Structure & timing → Pricing → Credit & allowance → Costs & accounting order; the new controls are grouped in the appropriate existing section. No Account adoption feature or engagement-specific calculation is added.

Validation: six new Python tests cover three 60-month source-style patterns, independent recurrence reconciliation, live gross-flow dependence, fee signs, public precision, yearly inflation factors, initial zero targets, provision-release floor, quarterly rates, invalid combinations, stress overlays and audit output. New Node tests exercise actual opt-in controls, source eligibility, units, grouped rendering, non-mutation and disabling. Existing shared-assumption, yield, repayment-profile, linked-loan, allocation, financial stream and product-layout regressions pass. Legacy monthly/quarterly engine outputs match r368 exactly for four fixture runs. Console syntax and whitespace checks pass. Browser pixel QA was not available.

Packaged for deployment; not deployed. See docs/lending_contracts.md for authoring, accounting conventions, cadence semantics and known source reconciliation exceptions.
