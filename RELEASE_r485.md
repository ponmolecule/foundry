# r485 — Loan production: linked deposit balance × percentage

Engine and console. Built on r484. Existing calculations unchanged: all 12 fixture configs give identical results on r484 and r485, config and run hashes included.

## What changed

Loan production (the existing production and repayment method) gains a fourth origination source, "Linked deposit balance × percentage". No new authoring method.

Example (acceptance test fixture, not the live engagement): a deposit named Portfolio Partnerships ends M1 at $29.6m, 1.176471% per month, monthly model. Originations M1 = 29,600,000 × 0.01176471 × 12 ÷ 12 = $348,235. A change to the deposit changes originations in the same run.

Formula, per model period t:

    originations[t] = observed deposit balance[t] × percentage[t] × rate periods per year ÷ model periods per year

Controls:
- Deposit product, stored by its stable source ID (`deposit_id` = the deposit's `source_catalog_id`). Rename and reordering do not change the link.
- Balance observed: beginning, ending or average. Average is the deposit's own (beginning + ending) ÷ 2.
- Percentage, in the shared Flat / Growth / Schedule editor. Stored as a dimensionless fraction.
- Percentage period: Month, Quarter or Year (12, 4 or 1 rate periods per year).

The originations go into the existing production ledger. Payments, prepayments, charge-offs, allowance, provision and deferred fees and costs are unchanged. Charge-offs are applied as before; they are not suppressed. The scenario origination haircut applies to these originations as it does to every other source.

## Rejected sources (run blocks, nothing set to zero)

Missing ID; an ID that matches no deposit; an ID shared by two deposits; a lending product's ID; the bank deposit total; a retention pool or pool series; a deposit that is a retention-pool member (its balance is allocated from bank state inside the period loop); a missing or unknown balance measure or percentage period; negative or non-finite percentages. A switched-off deposit keeps its identity and contributes its switched-off (zero) balance, which is disclosed in the audit.

Deposits are resolved before loans, so the link has no funding feedback.

Per-loan deferred fees and costs need a loan count. With this source (as with entered dollars) use Percent of funded amount; the console says so.

## Audit and public output

Engine (dollars): `loanProductionSource` (deposit ID and name, measure, percentage period, rate and model periods per year, volume multiplier, switched-off flag), `linkedSourceBalance`, `linkedPercentage` (authored, per rate period), `linkedEffectivePercentage` (per model period), `linkedOriginations`.

Public run: balances and originations in $000s (also in `detailExact`); percentages unscaled fractions.

Audit workbook, Loan Rollforward sheet: four new rows per linked product. Balance and originations in $000s. Percentages are fractions formatted as %, with units naming the period and the conversion (for example "authored × 12 ÷ 12").

## Console

- Origination source list adds "Linked deposit balance × percentage" with the four controls and a live formula line. Switching source keeps every source's saved inputs.
- Retention-pool deposits are not offered. A stale or duplicated ID is flagged on the control.
- Deleting a deposit that a loan links to now names that loan before deleting.
- Product results add Linked deposit balance, Percentage (authored and effective) and Linked originations to Numbers.
- The two production and repayment method cards are a radio group: a "✓ Selected" badge, a filled background on the selected card, a 2px focus ring, arrow keys to move between cards, Enter or Space to choose. Leaving Loan production still asks first.

## Not in this release

- Charge-offs: the source workbook omits charge-offs from loan balances. That is a separate, unresolved source issue; Foundry keeps applying them.
- The broader rounding enhancement stays separate.

## Verification

- foundry/v2/tests_r485_linked_deposit_originations.py (10 tests): acceptance case; deposit change; beginning, ending and average; month, quarter and year percentages on monthly and quarterly models; annual and monthly schedules; short schedule blocked and named (r482/r484 rules kept); rename and reorder; 16 invalid-source cases; scenario haircut with ledger identities (payments, prepayments, charge-offs, provision, deferred costs); public and audit scaling; existing sources unchanged.
- web/tests_r485_linked_deposit_source.cjs: method cards (radio roles, Selected badge, focus ring, arrow focus without switching, Enter selects); four controls and formula; stable ID across rename and reorder; pool members excluded; stale ID flagged; non-destructive source switch; deletion warning.
- Existing loan-production tests pass: r369, r372, r395, r418 (Python); r369, r370, r371, r392, r395 (console). r459 fails the same way on r484 and r485 (baseline).
- r482 (17), r483 (7) and r484 (14) schedule checks pass.
- Reference coverage regenerated (tools/reference_scan.py --write); the Selected badge uses the 3px radius rule.
- Differential run of all 12 fixture configs, r484 vs r485: identical, including config_hash and run_hash.
