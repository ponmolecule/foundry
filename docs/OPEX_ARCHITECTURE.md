# Operating Expense Architecture

## Doctrine

Foundry models reusable economic mechanics, not engagement labels.

Every operating-expense assumption has an explicit unit contract. Projection cadence may
implement that contract, but it must not define it accidentally. Expense recognition and cash
settlement are separate economic axes.

## Primary entered expense path

An Operating Expense category retains the compact primary authoring path introduced in r51:

- Flat
- Growth
- Explicit

Recurring flows own a natural amount period (`month`, `quarter`, or `year`). Growth owns its
own rate period, resolution (`step` or `smooth`), and anchor. Equivalent natural-unit inputs
must resolve to equivalent economics independent of engine cadence.

## Optional linked components

A category may add one or more linked components under **Advanced**. Linked components are typed by the units of the upstream Series and the coefficient they consume. Two core contracts are:

- `monetary / flow upstream Series × entered dimensionless rate Series`
- `Workforce Count Series × entered amount per FTE per natural period`

The second contract is intentionally **not** represented as a percentage. An expense quoted as `$X per employee per month/quarter/year` keeps that unit explicitly and is periodized once before multiplying resolved active headcount.

The safe upstream registry remains deliberately narrow:

- fee income
- gain on sale
- net servicing fees
- total noninterest income
- transaction Fee Stream quantity / throughput, referenced by stable `quantity_series_id`
- Workforce Count, referenced by a persisted role `series_id` or Workforce-owned aggregate `total_count_series_id`

Transaction Fee Stream quantity is the same native-period flow resolved by the Fee Product engine before pricing is applied. Workforce Count is the resolved active headcount owned by Workforce Compensation. Operating Expense observes those Series read-only; it does not recompute, own, or alter their trajectories. Balance/account stream quantities are intentionally not exposed under the ordinary flow-rate contract because their dimensional semantics differ. These drivers are upstream of Operating Expense and avoid an endogenous Opex circularity.

For Workforce Count, the coefficient is a periodic-flow amount per FTE with Flat / Growth / Explicit motion and Month / Quarter / Year amount units. Thus `$12,000/FTE/year`, `$3,000/FTE/quarter`, and `$1,000/FTE/month` are economically equivalent in a monthly or quarterly engine. The aggregate Workforce Count Series is computed from the same role-level active counts used by payroll; it is not a separately authored staffing forecast.

The architecture does not accept arbitrary formulas or workbook cell references.

A common generic shape is therefore:

`entered recurring base + Σ(typed additive components)`

Typed additive components include ordinary `upstream Series × rate` links and a shared
`cost_pool_charge` component. A cost-pool charge resolves a referenced eligible-cost pool, applies
its recovery percentage and markup path, and contributes the resulting downstream charge to NIE.
The pool itself is direction-neutral and non-posting: the same primitive may be consumed by a Fee
Product when the modeled bank earns the charge. Its linked, entered, and balance-derived pool
components remain calculation inputs rather than separate Opex postings.

New authoring follows this additive model. The short-lived r67 `calculation.kind = cost_pool` shape is
read only for backward compatibility: it retains its original exclusive semantics so a dormant
entered-expense draft saved in r67 does not unexpectedly become active. New configurations do not
create that shape.

This covers many vendor, platform, servicing, administrative, shared-service, and other mixed
fixed/variable expense contracts without adding engagement-specific expense types.

## Recognition versus cash settlement

Category-level recognition belongs to the **entered recurring expense trajectory only**:

- Same as trajectory (default)
- Monthly
- Quarterly
- Semiannual
- Annual

Cash settlement is a separate axis for that same entered recurring expense:

- Same as recognition (default)
- Monthly
- Quarterly
- Semiannual
- Annual

Payment timing differences produce balance-sheet timing balances:

- payment before recognition -> Prepaid operating expenses (asset)
- recognition before payment -> Accrued operating expenses (liability)

Additive components do not inherit these category timing controls. A self-timed component such as
`tiered / banded` owns its own observation lag, event cadence, and first event period; ordinary linked
components retain their native same-period timing. Mixed categories are therefore compositional: a
recurring entered expense may use its own recognition/settlement schedule while additive components
continue on their own timing contracts. The authoring UI hides recurring-expense timing controls when
the entered trajectory is economically zero, while preserving any stored settings for later reuse.

## OCC simplifying-rate treatment

OCC remains an existing regulatory-assessment input, not a new Opex ontology.

Foundry continues to accept the configured annualized OCC bp rate as a simplifying pricing
assumption. It now applies that input on a semiannual contract:

- H1 assessment uses the Dec-31 / opening measurement base
- H2 assessment uses the Jun-30 measurement base
- each semiannual assessment is `measurement base × annualized bp rate / 2`
- the assessment is recognized over its covered half-year
- cash settlement occurs in March for H1 and September for H2
- timing differences surface through prepaid/accrued Opex balances

Foundry does **not** claim that this simplifying bp input reproduces the full statutory OCC
tier schedule. The correction here is to use the user-entered simplifying rate consistently
with the semiannual assessment period instead of rebasing and dividing it every engine period.

## Generalization guardrails

Do not add source-model labels, workbook formulas, or special payment-date expense types to the
core. New features should represent mechanics that plausibly recur across materially different
engagements.
