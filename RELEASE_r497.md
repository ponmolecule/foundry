# r497 — Annual state and federal tax authoring

Built on Claude r496 (a2a8a483dfaa41d0b0587de5f572a7fb28e897b2), retaining r495 disclosure controls, r496 aligned tax-source rows, r494 LTI and r493 cash-interest behavior.

## One annual calculation block

Configuration → Tax detail → Calculation blocks → Annual state & federal tax. Choose live taxable income, state rate, federal rate, historical opening federal NOL and utilization limit. Choose tax-year end and whether cumulative state provision reduces federal income. Preview reviews the calculation; Apply selects its output only when the explicit current-provision choice is enabled. The existing reported-tax schedule and every entered source remain available.

The compiler generates actual-YTD state and federal provisions, separate current-period adjustments, tax-year opening NOL, utilization and closing carryforward. Current-year losses net within their own year; prior-year NOL use is limited against positive federal YTD income. Provisions can reverse within a year. Calendar resets are automatic and follow the model opening date and chosen fiscal year. A partial first tax year fails explicitly rather than inventing missing history. Only one such block is allowed; edit it rather than duplicate it. Compatible existing standalone rules are adopted with stable IDs; matched manually entered reset references migrate to the live calendar. No client amounts, rates, labels or product identities are inferred.

Scope: state tax uses positive YTD income without a state loss carryforward. This is an explicit actual-YTD model, not an estimated annual effective-rate election, comprehensive statutory tax engine or source-formula parity claim. Deferred-tax recognition, payment timing and opening balances remain unchanged. The block can expose and explain differences from a source with inconsistent tax posting or observation periods. No pasted forecast tax schedule is required.

## LTI ergonomics

Eligible-role Select all / Clear all controls. Historical award year, original award and Remove align in a responsive row, with Add historical award beneath. Existing selections and economics are preserved.

## Validation

71 focused Python tests pass, including annual tax paths, independent annual totals, monthly/quarterly equivalence, fiscal resets, cohort vesting, funding and cash interest. Existing external-tax and tax-block executable suites pass. Nine parity fixtures and 344 protocol checks pass. Seven Node suites pass: annual tax/LTI UI, existing tax blocks, external tax, LTI, schedule status, r493 cash measure and r488 shared assumptions. A pre-existing r495/r496 duplicate-selector hygiene failure was resolved by consolidating identical selectors in cascade order without changing declarations. Browser integration was attempted but Chromium is blocked by the host socket policy; no visual browser verification or full repository-suite pass is claimed.
