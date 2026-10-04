# r272 — Shared source catalog and balance-linked OpEx

Built directly on r271 (ae3d3f3). This release adds source discovery and a typed balance observation to the existing Formula / driver component. It does not create an engagement-specific FDIC primitive or change existing assessment defaults.

## Analyst workflow

In Operating expense → Expense categories, add a category and a Formula. Use a linked factor's Browse / search action to find the deposit pool's Retained on-book balance. Select End balance. Multiply by an entered percent factor of 0.15, with time basis Per Year. Keep the recurring entered expense at zero. Set the built-in FDIC assessment rate under Assessments & other NIE to zero when this formula replaces it. The linked expense posts once, in OpEx.

An annual decimal rate of .0015 produces retained balance × .0015 / periods per year: $400,000 produces $50 monthly or $150 quarterly. Nothing is charged on swept-out balances unless the analyst deliberately selects that separate stock.

## Discovery architecture

`source_catalog.py` is the shared discovery facade over typed publishers. The lightweight `/api/v2/source-catalog` route returns metadata, without running the projection and without adding fields to engine results or run fingerprints. The console's OpEx, cross-fee quantity, deposit balance/activity/share, lending-funded-flow, customer-count and cost-pool-balance selectors use this metadata while retaining their original consumer contracts. Existing local selectors remain a cold-cache fallback; Browse/search always requests current metadata. A source does not become universally admissible just because it is discoverable.

The catalog describes product/stream labels, stable identity, stock/flow/count/share units, supported measures and consumer eligibility. It covers existing fee quantities, acquisition balances/counts, workforce counts, cost pools, funded lending flow, individual lending/deposit book balances, total deposits and pool retained/swept/available balances. Statement residuals are visible as ineligible current-period OpEx inputs. Products receive a persisted source_catalog_id on authoring; no position or product name is used to identify new balance links. Renaming/reordering preserves links. No IDs are injected by engine execution.

Browse/search is available on Formula linked factors, cross-fee quantity links, deposit links and activity links, and funded-flow lending links. Compatibility and the fee DAG's existing reachability rules restrict selection. Category-aware discovery disables direct acquisition and balance paths which would return to the expense being authored. Invalid/missing links still fail closed in server validation; browsing remains available while a broken fee link is being repaired.

## Timing and accounting

Current deposit observations are taken after retention allocation, before current OpEx. Equity-budget pools observe prior equity and prior OpEx, so that lagged feedback is not an algebraic loop. A same-period expense → customer acquisition → activity → deposits → same expense loop is rejected. Beginning, ending and average retained/swept stocks use real opening balances. Available program balance supports ending observation only. Annual factors reuse existing periodization, recognition and settlement. Profile B ordinary book stocks also use this contract; pool modes remain Profile A only.

Audit component detail uses the same source observations and original unrounded engine balances when an exact snapshot is available. Public outputs remain in $000s; Formula evaluation remains in dollars. Deleting a balance-owning product or the last pool member warns about dependent references, and confirmed removal preserves those broken references for fail-closed validation.

## Limits

This is a shared catalog of supported typed publishers, not unrestricted linking to every output row or a general spreadsheet language. Existing limitations on balance/count fee-stream consumers, monthly aggregation, managed-notional authoring and cost-recovery remain. The broader deposit-card visual cleanup is not part of this build. The deposit capital-cap binding case and full financial-statement reconciliation remain engagement validation tasks.
