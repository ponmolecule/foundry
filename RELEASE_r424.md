# r424 — Deposit balances from existing Account streams

Built on r423. The existing Customer-count source dropdown in customer-linked deposit balance authoring now includes eligible Account streams. The existing amount-per-customer editor remains, in $000s. The equation is published count × balance per account × optional balance share. No revenue is copied, count is not re-acquired and no intermediary monetary stream is required.

The source registry follows Account dependencies and permits roots in entered counts or Customer Acquisition. Missing/ambiguous sources, wrong types, incomplete horizons and bank/deposit-balance dependency chains fail closed. IDs survive renames/reordering. Source selection preserves per-account amount assumptions.

For this new source type the published native-period level is used without resampling. Quarterly Account output may already average monthly counts; this is not reconstructed as a quarter-end count. Amount/share assumptions sample period end. The interface and Index state this limitation. Use monthly cadence for monthly source reconciliation. Existing acquisition-linked deposit behavior, including monthly calculation before quarterly aggregation and the period-average option, is unchanged.

Audit rows report published counts and per-account amounts truthfully at their source cadence; native-quarterly diagnostics are not labeled monthly. Calculation details continue to expose raw dollars per account, while UI inputs use $000s.

Validation: five new tests pass, including full monthly/quarterly engine and audit runs, monthly equality with the existing CAC deposit method, stable identity, rejection cases and period-end amount sampling. Existing customer-deposit tests (5), weighted amount reuse tests (5), source-picker harness and JavaScript syntax checks pass. No browser visual check was available. No save endpoint changes or engagement-specific data were added.
