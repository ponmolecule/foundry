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

A category may add one or more linked components under **Advanced**. A linked component is:

`typed upstream Series × entered dimensionless rate Series`

The safe upstream registry remains deliberately narrow:

- fee income
- gain on sale
- net servicing fees
- total noninterest income
- transaction Fee Stream quantity / throughput, referenced by stable `quantity_series_id`

Transaction Fee Stream quantity is the same native-period flow resolved by the Fee Product engine
before pricing is applied. Operating Expense observes that Series read-only; it does not recompute,
own, or alter the fee driver. Balance/account stream quantities are intentionally not exposed under
this contract because their dimensional semantics differ. These drivers are upstream of Operating
Expense and avoid an endogenous Opex circularity. The linked rate is stored separately from the
driver and is auditable. The architecture does not accept arbitrary formulas or workbook cell
references.

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

Recognition timing determines when the economic expense trajectory hits Noninterest Expense:

- Same as trajectory (default)
- Monthly
- Quarterly
- Semiannual
- Annual

Cash settlement is a separate axis controlling when the recognized expense is paid:

- Same as recognition (default)
- Monthly
- Quarterly
- Semiannual
- Annual

Payment timing differences produce balance-sheet timing balances:

- payment before recognition -> Prepaid operating expenses (asset)
- recognition before payment -> Accrued operating expenses (liability)

Custom settlement is currently limited to pre-resolvable entered expense paths. A linked
endogenous revenue component settles with recognition. Prepaying a future revenue-linked
charge would require a separate forecasting contract, so Foundry fails closed rather than
inventing one.

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
