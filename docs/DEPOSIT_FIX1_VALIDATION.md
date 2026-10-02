# r231a_fix1 validation build

Last good deployment and rollback baseline: r230 (`1c3e67d`). This delivery's main branch
contains r230 → r231a → r231a_fix1 history and can fast-forward from r230. r231a or r231b
does not need to be deployed first. No deployment has been performed by this build process.
The ZIP has the existing delivery/foundry-full.bundle structure; deploy the exact filename supplied.
A rollback to r230 requires the existing explicit version-switch/rollback workflow: pulling an older
bundle does not move a newer main branch backward. Keep the r230 delivery and engagement backup.

## Manual validation in a disposable engagement

Amounts below are $000s. Use monthly cadence. Retained deposits and swept balances have independent
opening stocks. Opening swept balances remain off-book; they do not increase deposit liabilities.

1. Existing engagement: open the same r230 configuration and recompute. The configuration and run
   hashes should match r230. Verify an r230 frozen run; it should still match. Do not edit inputs first.
2. New pool: create one category with 100% category share, source ending balances 1,000 / 2,000 /
   3,000 for the first three months, maximum retained share 50%, no capacity limit, annual sweep fee
   12%, average fee basis, opening swept balance 0. Expected retained and swept balances each:
   500 / 1,000 / 1,500. Expected fee basis: 250 / 750 / 1,250; fee: 2.5 / 7.5 / 12.5.
3. Existing off-book stock: change opening swept balance to 500. Expected fees: 5 / 7.5 / 12.5.
   Select period-end fee basis: expected fees 5 / 10 / 15 regardless of that opening stock.
4. Retained interest: opening retained deposit 100, ending retained 500, fixed annual paid rate 12%,
   average interest basis: M1 expense 3. Switch to end basis: M1 expense 5. Opening swept stock
   should not affect these interest amounts.
5. Two categories: shares 25% / 75% in the same pool. Total retained, swept and sweep fees must
   equal the pool totals; no duplicated fees. Give one EFFR and another Prime floating pricing:
   Product Detail headings must display those indices. Duplicate names must not swap indices.
6. Audit: Product Calculations and All Series include beginningSweptBalance, sweptBalance,
   sweepFeeBasis and sweepFee under deposit_retention_pools.<pool id>. For case 2, confirm M1
   0 / 500 / 250 / 2.5 respectively. Fees reconcile to the sum of member sweepFee outputs.
7. Paste: switch source activity to Derived, use its existing Explicit editor, paste a row, Load,
   Clear and Close. Shared settings must remain open while editing; Load enables for valid input.

## Capacity scope

The beginning equity option is an allocation budget, not an enforceable bank capital/assets ratio.
The control now says Equity allocation ratio. Financial formula unchanged. With 30M equity / 13%
and no commitments, it permits 230.769M deposit allocation; 260.769M total funded assets implies
11.504% equity/assets. Use entered capacity if a separately calculated bank-wide limit is required.
This build does not silently substitute a different capital-policy formula.

## Automated verification

Full inventory: 52 executable test modules; 43 passed, 9 failed. The same nine modules fail with the
same conditions in unmodified r230 (39 passed / 9 failed across its 48 modules). No additional failure
modules were introduced. All deposit integration, UI, fix1, identity, audit reconciliation, loan
allocation, cadence-equivalence and series architecture tests pass.

Known baseline failures:
- tests_parity: unmapped ebtda and msrAmort Call Report fields.
- tests_protocol: duplicate .fin-scroll CSS selector.
- tests_cost_recovery and tests_fee_guide: missing distributed_balance test context.
- tests_fee_streams: two historical baseline hash assertions.
- tests_growth_ui: Node argument size exceeds environment limit.
- tests_opex_ui: AUC basis preview assertion.
- tests_pastebox_hardening: four inventory/wiring/preview assertions.
- tests_universal_template: canonical driver/cost coverage assertions.

Identity: all three named r230 fixture fingerprints pass without removing result fields.
Frozen verification: actual registry_q.verify against the r230 core fingerprint passes.
Rendered browser: source switching, persistent expansion, live Load, monetary scaling, Clear,
Close and EFFR Product Detail heading pass with no JavaScript errors.
