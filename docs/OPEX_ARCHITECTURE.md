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

When another module consumes an Operating Expense category as a stable Series, the link resolves
the category's complete **upstream-resolvable** economics rather than only its entered recurring
base. In particular, Customer Acquisition acquisition-spend links include deterministic
`Workforce Count × amount/FTE` components. Components that require main-engine runtime metrics
(for example fee-income-, AUC-, fee-quantity-, tiered/banded-, or cost-pool-dependent amounts)
cannot be moved upstream safely and therefore fail closed instead of being silently omitted. This
keeps the linked Series equal to the source economics the user actually authored.

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

### Entered service-capacity component

Some outsourced, affiliate, contractor, and shared-service contracts are priced from an independently
authored service-capacity quantity rather than bank Workforce Count. Foundry represents that mechanic
with a deterministic additive `service_capacity` component:

`service FTE × $ / hour × hours / service FTE / natural period`

The three operands are independently authored. Service FTE and hourly rate are level Series with
Flat / Growth / Explicit motion. Hours per service FTE is a natural-period quantity with Flat / Growth /
Explicit motion and an explicit Month / Quarter / Year period. Foundry periodizes the hours assumption
exactly once before multiplying. Thus `2 FTE × $170/hour × 2,080 hours/FTE/year` resolves to
`$58,933.33/month` in a monthly engine and `$176,800/quarter` in a quarterly engine, with identical
annual economics.

Service FTE is deliberately **not** Workforce Count. It represents externally supplied capacity and
does not affect bank headcount, payroll, compensation statistics, or downstream Workforce-linked
drivers. Because all three operands are deterministic entered Series, a category containing only this
component (plus other upstream-resolvable components) may itself be consumed safely as an upstream
Operating Expense Series.

This component does not attempt to derive service FTE from transaction workload. Workload-derived
capacity remains a separate, unresolved mechanic until its quantity-period semantics are explicit.

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
`tiered / banded` owns its own observation lag, event cadence, first cash-event period, and (optionally)
its own expense-recognition contract. Historical/self-timed components default to **At cash event**,
which preserves the pre-r117 behavior. A component may instead choose **Accrue evenly over cadence
interval** and provide the first covered model period. Foundry then calculates one assessment amount
for the cadence interval, recognizes equal expense in each covered engine period, settles the full
amount on the configured event, and carries the timing difference as Prepaid operating expenses or
Accrued operating expenses. The observed assessment base must already be available at the start of
the covered interval; otherwise validation fails closed rather than looking ahead to a future balance.
Ordinary linked components retain their native same-period timing. Mixed categories are therefore
compositional: a recurring entered expense may use its own recognition/settlement schedule while
additive components continue on their own timing contracts. The authoring UI hides recurring-expense
timing controls when the entered trajectory is economically zero, while preserving any stored settings
for later reuse.

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

For the source-faithful tier schedule, use the generic tiered/banded component rather than the
simplified bp shortcut. In a January-start monthly model, the ordinary OCC cadence translates to:

- Event cadence = Semiannual
- First cash event = M3 (then M9, M15, ...)
- Expense recognition = Accrue evenly over cadence interval
- First covered period = M1 (then M7, M13, ...)
- Observation lag = 3 months, so M3 observes opening/Dec-31 and M9 observes M6/Jun-30

That configuration recognizes one-sixth of each semiannual assessment in each covered month,
settles the full assessment at the cash event, and carries the timing difference through accrued
or prepaid operating-expense balances. The ordinal fields remain generic so a non-January model
can translate the same economics without embedding calendar-month names in the engine.

## Generalization guardrails

Do not add source-model labels, workbook formulas, or special payment-date expense types to the
core. New features should represent mechanics that plausibly recur across materially different
engagements.
