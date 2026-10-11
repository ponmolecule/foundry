# r316 — Monthly repayment cohorts, including r315 gross-up eligibility

Lineage: r313 `900890f` → r314 `73b1170` → r315 `feb12c0` → r316. Deploy the final full-history bundle directly; no intermediate deployment is needed. No new product family is added.

## Repayment authoring

Lending → Flow-based lending + fees → Repayment model now offers the existing **Average exposure days** and opt-in **Monthly repayment curve**. Nothing changes until selected. The card keeps bounded controls, a visible age/percentage preview, and Load (replace), Clear and Close actions. It preserves/restores the prior average-days credit/runoff settings when toggled through the console.

1. Choose Monthly repayment curve. Enter repayment percentages by monthly age; age 0 is the funding month. The fractions must total 100%. There is no prefilled 60-day curve.
2. Choose the loss basis explicitly. Annual % of balance can use beginning exposure (excluding new funding), or beginning plus new funding, before repayments. Lifetime % of funded principal requires a separate loss-recognition curve totaling 100%.
3. Use Flat/Growth/Explicit for the loss-rate path. A lifetime rate is locked at each funding cohort; changing later funding quotes does not rewrite earlier cohorts. Credit loss factors remain available.
4. Enter opening retained/distributed cohorts when applicable. Empty lists explicitly mean zero exposure. Original principal must equal historical repayments + historical charge-offs + outstanding. Set the next monthly age; Foundry does not infer seasoning from a scalar opening balance. Lifetime-loss opening cohorts require their original loss quote.
5. Choose Reserve % of balance or Remaining profile expected loss. The latter forecasts remaining entered losses on surviving cohorts, using known future loss/factor paths and holding the final entered rate/factor beyond the model horizon. It is a mechanical modeled allowance under those assumptions, not a complete CECL estimation or accounting-policy assessment.

Monthly buckets do not imply known transaction dates. The curve's age-0 treatment expresses within-funding-month repayment; no daily purchase pattern, exact contractual due date or statement-cycle interpretation is invented. Monthly interest measures remain beginning/end/endpoint-average observations; quarterly interest uses the average of the corresponding monthly observations with the native-quarter rate. This is not a daily time-weighted interest calculation.

## Principal and credit identities

For each retained cohort and monthly total:

`beginning + retained funded − charge-offs − repayments = ending`.

Each curve entry is a scheduled fraction of original principal. The conditional paydown is `fraction_at_age / (1 − cumulative_prior_fractions)`, applied after charge-offs to surviving principal. This prevents charged-off principal from also repaying. Interim identities include remaining exposure. Fully extinguished cohorts have historical/forecast repayments plus charge-offs equal their original principal, without additional adjustments.

Annual balance losses are `selected monthly exposure × annual rate × loss factor / 12`. Lifetime-volume losses are `original retained funded principal × cohort's lifetime quote × timing fraction × loss factor`. Losses above available exposure are rejected, not clipped. Provision continues to equal net charge-offs plus change in allowance (recoveries remain zero under this implementation).

Retained and distributed shares are applied to funded principal. Distributed cohorts use the repayment curve but have no bank credit losses; their balances remain off-book. Held-aside funded volume is excluded from exposure as under the current flow model. Quarterly runs sum monthly flows and preserve ending stocks; profiled funded-flow and distributed/retained-balance fees also sum monthly economics. Balance-price audit factors retain annual-rate units, and percent-of-revenue cost factors retain percentage units.

## Practical checks (engine dollars)

A monthly $1,000 flow with curve `[0%, 0%, 100%]`, no opening exposure and no losses gives ending balances $1,000 / $2,000 / $2,000 and repayments $0 / $0 / $1,000. This illustrates the selected monthly curve; it does not establish that every contractual 60-day card has this profile.

With 12% annual beginning-balance losses, month-2 charge-offs are $10. The first cohort repays $980.10 in month 3 after losing $10 and $9.90; its repayments plus losses equal $1,000. Remaining modeled allowance is $19.90 in month 1 and $29.80 in month 2.

With 4% lifetime loss and timing `[0%, 100%]`, month-2 charge-offs are $40, future loss allowance is $40, and the first cohort eventually repays $960. A new funding quote of 8% applies to the next cohort, not the first one.

With growing monthly flows $1,000/$1,100/$1,200, 75% retention, 2.2% funded-flow fees and 12% annual distributed-balance fees, first-quarter fees are $86.10. Throughput costs at 0.89% are $29.37. A 12% yield on monthly ending retained exposures earns $40.50. All three equal the sum of the monthly runs.

## Audit and compatibility

Product Detail adds Principal repayments. Audit adds **Repayment Monthly** and **Repayment Cohorts**, including exposure, loss quote, factor and denominator so charge-offs can be recomputed. Monetary workbook fields use $000s; the detailed public profile payload uses engine dollars. Gross-up authoring/audit from r315 is included; see its notes.

All five complete legacy fixture result objects are identical to r314, with no field stripping, and all three current run-hash pins match. Absent optional settings produce no additional audit/output keys. R314's opt-in monthly fee diagnostic aggregation is also corrected to retain annual balance-price and percentage-of-revenue cost units; economic fee/cost posting remains unchanged for those already-supported paths.

## Explicit unsupported combinations

- Shared capacity caps plus repayment profiles are rejected. The existing average-days/shared-cap method remains available; a profile never bypasses a cap silently.
- Annual-loss × exposure-term allowance is rejected for profiled balances; use an explicitly supported allowance method.
- Fair-value/term-amortization/mortgage-banking structures, competing legacy runoff/loss rates, Profile B and fee/funding sources lacking canonical monthly operands are rejected. Legacy model-period fee schedules and revenue ramps need natural-period paths / funded-flow timing instead.
- DFAST's absolute annual-balance overlay is supported for annual-balance profiles. Applying it to a lifetime-volume profile on a mapped DFAST loan category is rejected: no volume-to-balance loss conversion is invented. Ordinary loss multipliers apply to either supported basis. Recoveries, commitments and unused-line capital remain separate work.
- Guide Me does not author repayment profiles automatically.

The actual charge-card engagement has not been supplied for an early-month funding/capital comparison. The build supplies the generic mechanics; the spec owner still must establish the 60-day convention, 4% loss denominator and appropriate reporting classification before entry or source reconciliation.
