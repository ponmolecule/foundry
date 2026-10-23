# Operating Accounts reassessment from r382

## Decision and baseline

The user rejected the r383 authoring approach, not the requirement for live, assumption-driven modeling. r384 fixed lifecycle problems in that approach; it is also withdrawn as part of restoring r382. r383/r384 remain preserved by their Git tags. Their runtime and UI changes are removed in r385. The source clarification log remains.

No engagement configuration is automatically rewritten. The user will enter Operating Accounts afresh. Existing work completed through r382, including the reconciled HSA product, remains supported.

## What the r382 code actually supports

| Need | Existing path | Boundary |
|---|---|---|
| Active practice count with acquisition and attrition | `deposit_balance.customer_balance`, CAC stable count source | Ready; do not author another acquisition feed. |
| Dollars per active customer | Existing deposit customer-count × entered amount | Ready for one entered amount/path; it does not accept a weighted shared assumption. |
| Weighted assumptions with live amount and weight paths | `shared_assumptions.SharedAssumptions`, already used by lending | Arithmetic already exists. Deposit consumption is the gap, not a missing new calculation language. |
| Two independently priced deposit portions | Two deposit products with their own pricing and balance sources | Possible, but manually folding practice mix and tier share into each multiplier hides assumptions. Four bands × two tiers creates eight products solely to express a calculation. Neither is a satisfactory primary workflow. |
| Ordinary fees and costs | Existing Account/Transaction/Flat streams, gross acquisition flows and expense formulas | Ready; reuse these. |
| Partner attribution | Existing per-channel gross flows | Published flows are available; an expense consumer does not currently offer cumulative observations and a channel/total ratio. |
| Partner margin | Existing balance catalog, expense factors, reference curves and product interest calculations | The underlying data exists, but r382 expense formulas do not observe actual deposit interest or reference curves and support only factor multiplication/division. Recreating those values in duplicate schedules weakens linkage. |

## Alternatives rejected

- Pasting computed balances, expenses or a forecast of final results: breaks live dependencies.
- Supplying a manually calculated weighted/portion multiplier: does not keep the source assumptions separately editable or inspectable.
- Creating dummy lending products or off-book earning assets to access an editor: wrong financial object and accounting risk.
- Building a forest of zero-priced fee streams or eight deposit products solely to route quantities: excessive authoring and internal knowledge.
- Substituting active-account share for cumulative gross-acquisition share, or using one net rate on one exposure basis: potentially changes source economics.
- Assuming a constant partner share merely because the current engagement's acquisition coefficients appear constant: duplicates a derived relationship and fails when those assumptions change.

## Proposed workflow — for review, not implemented in r385

### Deposit balance: work inside the existing customer-linked balance field

Keep the current population selector and balance-per-customer field. Add an optional **Use a breakdown** action immediately beside that amount. It expands a short table of label, dollars per customer, and population weight. Existing Flat/Growth/Explicit editors handle each input. Show the weighted result in place. Reuse the existing weighted-assumption resolver internally.

The simple one-amount case must look and behave exactly as r382 does. A local breakdown belongs to its product; no shared-assumption registry, naming dialog, new intermediate product, or separate creation lifecycle is required for ordinary entry. Reuse across products, if later justified, should be a secondary link operation rather than the first thing users must understand.

For pricing, the recommended bounded extension is an optional **Split pricing** table inside the existing Pricing section: portion label, share of deposit balance, and the existing fixed/floating rate controls. One deposit product owns the balance and the summed interest expense. A simple deposit still has one ordinary rate and no table. These are allocated balance portions, not per-account dollar-threshold tiers; the UI must say so.

The engine must calculate each portion's beginning and ending balance separately before applying the selected exposure measure and rate. It must not multiply an averaged total balance by the current share when shares change. Shares must sum to 100% each period; no hard-coded number of portions. The source's constant 5%/95% split is then an authored instance, not a built-in default. This requires pricing calculation work, not merely new labels, and has not yet been built.

### Partner cost: a business contract, not an expression tree

Reuse the existing expense category and formula/driver authoring path where possible. The user should describe an agreement: attributable population, eligible earnings less selected costs, participation percentage, observation measures and negative-payment policy. Ordinary users should not need nested operator nodes, abstract unit declarations, stable IDs or manually assembled cadence conversions.

The recommended bounded extension is to the existing **Formula / driver** component, not a separate expression-tree component:

- An optional base table can **Add** or **Subtract** named financial observations. A balance row may carry a linked rate and natural period; an actual expense-flow row needs no annualization. The existing factor chain applies to the summed base.
- Publish read-only resolved reference rates and actual product deposit-interest flows through the existing typed source catalog. This avoids copied rate paths and duplicate posting.
- Offer a **Customer acquisition share** factor: choose an existing feed, a channel and Current gross / Cumulative gross observation. Derive the fraction from channel acquisitions divided by that feed's total acquisitions. Make zero-denominator handling explicit; do not silently substitute an active-account share. This is a reusable source observation, not a product-specific partner formula.
- The participation percentage remains an ordinary entered factor. Preserve the existing component's negative-result behavior; add an optional zero floor only as an explicit authored contract term if separately justified.

For the present source this becomes: Add ending deposit balance × linked Fed Funds annual accrual; Subtract actual deposit interest expense; Multiply by the live cumulative acquisition share and entered participation percentage. No fictitious earning asset or duplicate interest-income posting is needed. The table and factors use existing selectors and Series editors rather than arbitrary nested operator nodes.

This is a proposed implementation boundary, not a claim that r382 already has these source observations or arithmetic. Cycle checks, native cadence, selected balance measures, solver retries and audit provenance must be tested before release.

## Acceptance criteria before another enhancement build

1. A user can describe the balance and agreement using familiar economic inputs, without knowing Foundry module internals.
2. Acquisition, attrition, amount, mix and pricing changes propagate through real links.
3. Simple deposits retain the compact r382 path.
4. No source workbook labels, tier counts, percentages or formulas are engine defaults.
5. Monthly timing and mixed exposure bases are explicit and independently tested.
6. Existing r382 configurations retain their results.
7. The source's unresolved interpretation questions remain in the clarification log; implementation does not silently decide them.


## Implemented decision: r386

The implemented choice reuses two existing deposit products and their existing pricing; the proposed new split-pricing engine was not built. Per-customer detail is local to the first product and linked by the second, with ordinary balance shares. The existing Formula receives a flat Add/Subtract base and the missing read-only observations. No separate expression-tree tool or shared-deposit registry is restored. See `docs/r386-existing-mechanics.md` for the current implementation and authoring map.
