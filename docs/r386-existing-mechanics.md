# r386: existing mechanics with optional detail

## Implementation boundary

This release builds on r385 (the r382 application baseline). It does not restore the r383 shared-deposit registry workflow or its separate expression-tree expense driver. It does not add a new pricing engine or a product-specific Operating Accounts template.

| Economic need | Implementation |
|---|---|
| Acquisition and attrition | Existing Customer Acquisition feed and gross channel flows. |
| Customer-linked deposits | Existing customer count × dollars per customer equation. |
| Differing amounts across a population | Optional local breakdown in the existing dollars-per-customer field; uses the pre-existing weighted-assumption evaluator internally. |
| Reuse that amount in another deposit component | A typed link to another deposit's dollars-per-customer assumption, without a separately created shared-input object. |
| Deposit portions | Optional entered balance share on each existing deposit product. |
| Different rates for the portions | Existing deposit products and their existing pricing controls; no blended rate must be calculated externally. |
| Ordinary income, onboarding, servicing, operations, fraud, acquisition costs and bounties | Existing streams, acquisition flows, expense formulas and cost multipliers. |
| Net eligible financial base | Optional flat Add/Subtract base items in the existing Formula component, compiled/evaluated by that component's existing factor machinery. |
| Actual interest, linked index rates and channel attribution | Read-only observations in the existing source catalog/factor selector, with source/cycle checks. |

No engine default contains practice sizes, product labels, tier proportions, partner percentages or source workbook row references.

## Deposit authoring

The existing customer source and count measure remain. Under Balance per customer choose:

- **Enter amount**: the existing ordinary entered amount/path.
- **Use a weighted breakdown**: local rows with label, actual dollars per customer and population weight (%), using existing Flat/Growth/Explicit controls. Add and remove rows directly. No registry entry or separate creation dialog is involved. Weights must total 100% each month and represent the selected active population's mix, not an independently changing new-acquisition mix.
- **Link another deposit’s amount**: select an existing customer-linked deposit. Only its per-customer amount is linked. The consumer retains its own customer source, count measure, balance share and pricing. Links use stable IDs and reject missing or cyclic dependencies.

**Apply a balance share** optionally scales the calculated balance. A second product can link the first's per-customer amount and apply a complementary share. Its source's share is not applied a second time. There is no assumption that every product using an amount is a partition of one book; the author determines the shares and ownership.

Inactive amount-method inputs are retained when switching methods, including through configuration save/reload. No automatic conversion of existing engagements occurs. New controls retain the precision of supplied dollar amounts and weights.

Amounts, shares and customer observations resolve monthly before native deposit aggregation. Existing interest measurement rules still apply to each product's resulting beginning/end balances. A quarterly model uses its authored native interest measure; this release does not promise that a nonlinear quarterly calculation equals the sum of three monthly calculations.

## Existing Formula: optional Add/Subtract base

Create or open a normal expense Formula and choose **Use an add / subtract base**. Its prior factor chain is retained as one base item, not reinterpreted. Each base item has a name, Add/Subtract sign and a financial source chosen from the existing catalog. A newly selected balance can be multiplied by an entered annual rate or a linked EFFR/SOFR/Prime rate. A current-period financial flow, such as actual deposit interest expense, is already accrued and is not divided again.

The ordinary Formula factors apply to the summed base. There is no recursive expression tree, arbitrary code or second expense posting path. The base has at most 32 flat items. Existing factors and ordinary formulas retain their prior behavior.

New read-only factors/observations:

- **Deposit interest expense**: actual product interest, including any minimum-interest top-up; never separately posted by the observer.
- **Reference rate**: the same resolved curve used by the engines, including engagement schedules/scenarios. Choose annual accrual per model period or use the annual rate as a factor.
- **Gross acquisition share**: one channel's current or cumulative gross acquisitions divided by its own feed's total gross acquisitions. It does not subtract attrition or include opening accounts. The zero-denominator policy is visible: zero share or input error. Legacy straight-line feeds do not become eligible gross-flow sources.

An optional positive-balance condition observes one or more selected balances; the Formula applies only if their selected measure totals above zero. Missing sources fail closed. Negative expenses remain possible; no zero floor is silently imposed. Source accounting questions remain in the clarification log.

## Operating Accounts authoring map

This is an authoring example, not a new runtime template:

1. Use the existing practice acquisition feed containing Direct and EMR. Do not create another acquisition feed.
2. Create the existing MMDA / Savings deposit product **Operating Accounts — Lower Tier**, opening zero, count measure Period end. Author the supplied four amounts and weights as its local breakdown. Apply a 5% balance share.
3. Create **Operating Accounts — Upper Tier** using the same acquisition feed. Link its per-customer amount to Lower Tier and apply 95%. Use existing pricing controls to enter the independently supplied rate paths (lower: 1.25%, 0.95%, 0.65% thereafter; upper: 3%, 2.7%, 2.4% thereafter). Interest measure is Average (begin + end). Do not infer that the two fixed source schedules are floating spreads merely because their current paths parallel Fed Funds.
4. Reuse the existing account/transaction streams and costs for checks, wires and other per-account charges. Their population is the full practice count, not the 5% lower-tier deposit balance. Author each posting once. Existing gross total/Direct/EMR acquisition flows support onboarding, Direct CAC and partner bounty respectively. Preserve the supplied inflation/exponent logic using the existing cost-multiplier authoring pattern.
5. Fraud is based on the sum of the two selected ending Operating Account balances. Do not use total bank deposits: HSA and other deposits also exist in this engagement. Choose No rate — balance only for each of those two base items; apply the annual fraud rate once in the Formula factors after the sum.
6. For partner revenue share, use one existing expense Formula: Add ending Lower Tier balance × linked Fed Funds annual accrual; Add ending Upper Tier balance × the same linked rate; Subtract actual Lower Tier deposit interest; Subtract actual Upper Tier deposit interest. Apply the entered participation percentage and the existing feed's cumulative gross EMR acquisition share. The positive-balance condition selects those two Operating Account balances, not total bank deposits.
7. Reconcile and save before proceeding. The new feature tests are not a claim that the user's engagement data has already been entered or reconciled.

## Audit

The existing Calculation Audit Workbook exposes local per-customer component amounts, weights, weighted contributions, balance shares and the final deposit balance in Product Calculations. Opex Component Detail includes signed base item amounts and final expense; monetary detail is raw dollars where stated. Operating Expense retains the final component series in $000s. The main product previews continue to show their own calculated outputs.
