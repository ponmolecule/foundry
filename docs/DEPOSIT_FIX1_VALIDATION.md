# r231a_fix3 validation build

Last good deployment and rollback baseline: r230 (`1c3e67d`). This delivery's main branch
contains r230 → r231a → r231a_fix1 → r231a_fix2 → r231a_fix3 history and can fast-forward from r230. r231a or r231b
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

Full inventory: 56 test entry points (52 Python modules plus four web/tests*.cjs scripts);
46 passed, 10 failed. Baseline r230: 52 entry points (48 Python plus four CJS), 42 passed,
10 failed. The same entry points fail in both; no additional failure entry points were introduced.
Counts are scripts/modules, not individual assertions. All deposit integration, UI, fix1, identity, audit reconciliation, loan
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
- web/tests_authoring_stability.cjs: standard invocation cannot find the default Playwright browser.
  A supplemental run using the available Chromium executable reaches an assertion: Load should
  clear the draft, but preserves "100\t200\t300". This assertion fails identically on r230 and fix2.

Identity: all three named r230 fixture fingerprints pass without removing result fields.
Frozen verification: actual registry_q.verify against the r230 core fingerprint passes.
Rendered browser: source switching, persistent expansion, live Load, monetary scaling, Clear,
Close and EFFR Product Detail heading pass with no JavaScript errors.

## fix2 acceptance checks

The omitted fee basis now uses average in both imported and on-screen pool definitions.
Period-end is an explicit choice. The existing opening swept stock behavior remains unchanged.

Switching to pool mode creates a new pool if none exists, selects the sole existing pool,
or creates an independent pool if several exist and no valid pool is already assigned.
Joining the sole pool starts at zero category share when other members exist, preserving the
existing allocation. Author the desired category shares together afterward; they must total 100%.
Every transition requests one preview after attaching the product to its valid pool.
The integration test replays five snapshots through the actual preview API; all return HTTP 200.

## fix3 labels and guidance

Pool editor, Product Detail and audit labels distinguish outbound "Swept out (off-book)"
and "Fee on swept-out balances" from inbound Sweep / Program deposits. Audit series keys
are unchanged. The source field asks for gross program balance before retention or capacity
limits. Deposit presets, calculation formulas and fee defaults are unchanged from fix2.
