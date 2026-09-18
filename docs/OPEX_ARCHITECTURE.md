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

## Advanced additive components

Advanced Operating Expense authoring is intentionally limited to three structural families:

1. **Formula / driver component**
2. **Tiered / banded component**
3. **Cost-pool / cost-recovery component**

The menu is structural, not engagement-shaped. Foundry does not add a new component type merely
because a source workbook uses a new business label. Historical linked-component and
`service_capacity` storage shapes remain readable/editable for backward compatibility, but new
authoring uses Formula / driver for those same multiplicative economics.

### Formula / driver component

Formula / driver is a constrained typed factor chain, not a free-form spreadsheet formula language.
It composes stable upstream Series and entered factors with multiplication or division:

`linked or entered factor × factor × factor ÷ factor ...`

Each entered factor keeps Foundry's ordinary **Flat / Growth / Explicit** trajectory grammar. A factor
that owns a natural time unit additionally carries an explicit Month / Quarter / Year period and is
periodized exactly once. A dimensionless rate or unit price carries no hidden time period. This
distinction is what lets one primitive represent several recurring economic contracts without
collapsing their causal structure into an explicit final-dollar schedule.

Representative contracts include:

- ordinary legacy link: `upstream Series × rate`
- conventional service capacity: `service FTE × $/hour × hours/FTE/year`
- payment processing: `base quantity × transactions/base/month × $/transaction`
- failed processing: `base quantity × incidents/base/month × $/incident`
- cross-border processing: `remittance volume × cost rate`
- complaint handling: `call quantity × $/call`

For the payment-processing example, `transactions/base/month` owns Month as its natural period while
`$/transaction` does not. A quarterly engine therefore converts 12 transactions/base/month to 36
transactions/base/quarter but leaves $0.05/transaction unchanged. Likewise, a percentage cost applied
to a native-period remittance-volume Series is a same-period multiplication; Foundry does not invent
an annual `/12`.

The safe upstream registry remains deliberately narrow and stable-ID based. Formula / driver may
observe the existing compatible Opex sources, including Fee-stream quantity Series, Workforce Count,
CAC AUC with an explicit balance measure, and the established safe revenue metrics. Operating Expense
observes those Series read-only; it does not recreate their trajectories or take ownership of them.

The component may also be entirely entered. For example, `500 calls/month × $8/call` can be authored
as two entered factors, preserving the quantity and unit-cost economics separately. If a factor path
is irregular, Explicit belongs on that factor rather than replacing the whole relationship with a
pasted expense schedule. A fully explicit final expense remains the ordinary category-level escape
hatch when the source relationship is genuinely exceptional and not worth generalizing.

Conventional service capacity is therefore no longer a distinct *new-authoring* species. Its service
FTE is still deliberately **not** Workforce Count: it represents externally supplied / affiliate /
contractor capacity and does not affect bank headcount, payroll, compensation statistics, or
downstream Workforce-linked drivers. Historical `service_capacity` configurations retain their
released economics and editor for backward compatibility.

Formula / driver does **not** attempt to derive service capacity from workload. The unresolved
Compliance source case (`operational activity -> workload hours -> implied service FTE -> cost`) stays
out of this contract until its quantity-period semantics are explicit. This is a deliberate boundary,
not an invitation to add a Compliance-specific component type.

When another module consumes an Operating Expense category as a stable Series, the link resolves the
category's complete **upstream-resolvable** economics. Formula / driver components are reusable
upstream only when every linked operand is itself safely resolvable at that point in the causal graph.
Components requiring main-engine runtime metrics fail closed rather than being silently omitted.

### Tiered / banded component

Tiered / banded remains separate because its arithmetic is structurally different from a factor
chain: the applicable base/marginal rate changes across thresholds and the component can own event
cadence, observation lag, and recognition timing. It is not merely a complicated Formula / driver.

### Cost-pool / cost-recovery component

Cost-pool / cost-recovery remains separate because it aggregates eligible costs owned elsewhere, then
applies recovery and markup economics. The pool is direction-neutral and non-posting; only the final
downstream charge posts to NIE. This ownership/aggregation contract is structurally different from
a direct factor chain.

The short-lived r67 `calculation.kind = cost_pool` shape remains read only for backward compatibility.
New configurations do not create that exclusive shape.

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
