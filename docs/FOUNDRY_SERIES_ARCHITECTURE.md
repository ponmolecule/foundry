# Foundry Series Architecture — causal authoring contract

## North Star

Foundry models the **causal structure** of a bank model; it does not reproduce the source
workbook's layout. A source workbook may use seven annual columns, monthly tabs, or a single
scalar assumption. Those are authoring shapes. Foundry resolves them into canonical model-period
series without making the surrounding module look like a spreadsheet.

The reusable vocabulary is deliberately small:

1. **Series** — something that changes through time.
2. **Equation** — a closed, domain-specific relationship between series.
3. **Link** — one module consumes a series owned by another module.
4. **Module / product** — owns assumptions and organizes the causal graph for the user.

There is intentionally **no arbitrary formula builder**. Flexibility comes from composing a small
set of auditable equations with generic time-varying operands, not from allowing unconstrained
expressions.

## 1. Series

A Foundry Series carries:

- **Source** — Enter assumption, Link to another Foundry series, or Derived from a closed equation owned by a module.
- **Trajectory** — Flat, Growth, or Explicit.
- **Cadence** — Year, Quarter, Month, or native model period where appropriate.
- **Resolution** — Step or Smooth where a coarser source cadence must be resolved into the model
  cadence.
- **Extension** — Hold / Zero / Error for explicit paths beyond the authored source horizon.
- **Units** — supplied by the consuming domain (count, rate, $000s, $000s/customer, etc.).
- **Identity / ownership** — a stable `series_id` and owning module, independent of display labels.

`Derived` is not a formula-builder escape hatch. The generic Series resolver refuses to evaluate
Derived formulas. A module may publish a Derived series only after computing one of its closed,
validated domain equations; downstream modules consume that materialized result by stable ID.

A seven-year source-model path is therefore just an **Explicit / Year** trajectory on the driver
that actually has that path. It does not turn the entire module into a seven-column input grid.

Legacy scalar/growth fields remain readable. The absence of a new Series spec preserves their
historical economics.

## 1A. Periodic flow units in Configuration

For recurring Configuration Operating Expense, source cadence is an economic unit rather than an
engine property.  A periodic flow carries `value + period` (or Explicit `values + period`) and is
resolved centrally before downstream economics consume it.  Therefore `$360k/year`, `$90k/quarter`,
and `$30k/month` are the same flow assumption, independent of whether the engine computes monthly
or quarterly.

Growth is orthogonal: `3%/year` remains `3%/year` whether the base is authored per month or per year.
Step/Smooth and anchor govern the trajectory, not the amount unit.  Legacy Opex without the new
`flow_spec` keeps its exact old native-cadence behavior; once materialized for new authoring, that
legacy cadence is frozen explicitly rather than re-inferred from a later model cadence.

This is deliberately a Configuration-Opex refinement, not a global rewrite of Product-tab
loan/deposit cadence mechanics.

## 2. Equations

Each domain owns a small closed vocabulary of defensible equations. For Customer Acquisition the
initial set is:

- `Pool × Conversion` → new customers.
- `Spend ÷ CAC` → new customers.
- `FTE Count × Productivity` → new customers.
- `Explicit New Customers` → new customers supplied directly as a series.

Channel names are labels only. `Affiliate`, `Direct / BD`, `Branch`, `RIA referrals`, or a future
channel the engine has never heard of are configurations of the same equations.

The same pattern applies elsewhere: Workforce expense uses Count × Compensation × benefits/load;
Fee Products use their closed stream shapes; modules own equations while generic Series own motion
through time.

## 3. Links and ownership

A Link points to a **stable `series_id`**, never a display name or spreadsheet cell.

Examples:

- CAC Spend may link to an Operating Expense category.
- CAC FTE Count may link to a Workforce population's Count series.
- Fee Product managed notional may consume the Customer Acquisition AUC output.
- Account Fee streams may consume the Customer Acquisition customer-count output.

The owning module remains the single source of truth for trajectory. If CAC links to `Operating
Expense / Business Development`, CAC does not create a second growth assumption for that spend.
Renaming `Business Development` does not break the link because the stable ID does not change.

## 4. Link safety

Links fail closed when they are missing, ambiguous, unsupported, or circular.

In particular, CAC may not link upstream to a metric-triggered Workforce Count when that trigger
could itself depend on AUC or financial outputs downstream of CAC. The user must break the cycle
with a fixed/entered upstream path or another independent source.

This is deliberate model-risk behavior: Foundry does not silently iterate an undeclared circular
system.

## 5. Workforce Count and Compensation

One Workforce row represents **one economically homogeneous population**, not necessarily one
named employee.

`Count` and `Compensation` are Foundry Series. Each may be Flat, Growth, or Explicit. Payroll consumes
the resolved native-period count and annual compensation/FTE trajectories:

`Workforce expense = Count × annual compensation/FTE × (1 + Benefits / Payroll) / ppy`

Legacy `annual_comp + salary_growth_spec` remains authoritative when no Compensation Series is
authored, preserving historical configurations exactly.

Use one row while timing, compensation, escalation, benefits/load and activation economics are the
same. Split rows when aggregation changes the economics.

This restores the useful Count concept without returning to a rigid FTE-Year-1/FTE-Year-2/FTE-Year-3
staffing table.

## 6. Customer Acquisition authoring

A Customer Acquisition feed contains N arbitrary user-named channels. For each channel the user:

1. chooses **How are customers acquired?** (the equation), then
2. gives each operand its own Series dials.

Example:

- Channel: `Direct / BD`
- Equation: `Spend ÷ CAC`
- Spend source: `Link` → Operating Expense / Business Development
- CAC source: `Enter assumption`
- CAC trajectory: `Growth` or `Explicit`
- AUC/customer source: `Enter assumption`
- AUC/customer trajectory: `Flat`, `Growth`, or `Explicit`

An Explicit schedule opens locally on the operand that needs it. The module does not expose a
spreadsheet-wide Year-1…Year-N input surface.

The channel outputs are module-owned Derived series and feed one common customer/AUC roll-forward.
The feed publishes stable Derived Series for both AUC and total customer count. Customer count is
resolved on the same canonical monthly grid and remains owned by CAC: downstream consumers must not
create a second Flat/Growth/Explicit client forecast. An Account Fee stream may consume the stable
customer-count Series directly; monthly billing uses the monthly level, while quarterly billing uses
the arithmetic mean of the three canonical monthly levels so equivalent per-client pricing preserves
annual economics across cadences. The fee's per-account price trajectory remains independently owned
by the Fee Product.

AUC is resolved first on a **canonical monthly period-end grid**, regardless of whether the selected
engine/presentation cadence is monthly or quarterly. Quarterly native balances are sampled from
canonical M3/M6/M9/M12; the monthly path remains available for downstream calculations whose
economics depend on each month's exposure. The resolved AUC then becomes a canonical managed-notional
series for downstream Fee Products. The stock owner publishes EOP observations; consumers choose the
measure they need. `period_average` is derived canonically as `(prior month-end + current month-end) / 2`,
and a quarterly period average is built from the three underlying monthly average exposures rather than
from two quarter-end points. Fee Products prefer the stable AUC `series_id`, while legacy name-based
references remain readable.
For explicit source cadence finer than the acquisition equation cadence, flow operands such as Spend
and Explicit Customers sum; level/rate operands such as CAC, Pool, Conversion, Count, Productivity,
and AUC/customer average.

Operating Expense may observe a CAC feed's stable AUC Series as a linked component. The consumer
explicitly chooses **Period end** or **Period average**; missing measure on an r64/r65 configuration
migrates as Period end so existing economics do not change. This remains the ordinary
`upstream Series × multiplier` mechanic rather than a bespoke expense type. Because AUC is a stock,
its multiplier owns a natural Month / Quarter / Year period. For example, a `0.01% / Year` EOP-based
fraud-loss provision accrues each canonical month as `month-end AUC × 0.01% / 12`, while an average-AUC
expense first derives the monthly `(prior EOP + current EOP) / 2` exposure. Quarterly presentation sums
the three monthly accruals in either case. A category already feeding the selected CAC feed through
Acquisition Spend may not link back to that feed's AUC, because that would create
`Opex → CAC → AUC → Opex` circularity.

## 7. Release invariants

1. Existing configurations with no new Series/Link fields preserve baseline economics.
2. A linked series has one owner; consumers do not duplicate its trajectory assumptions.
3. Display-name changes do not break stable-ID links.
4. Unsupported or circular links fail closed.
5. Source cadence and projection cadence are separate concepts; for recurring Configuration
   flows, equivalent Month/Quarter/Year natural-unit inputs resolve to identical economics.
6. Explicit paths are properties of individual drivers, not reasons to reproduce source workbook
   grids.
7. New engagement names should normally require configuration, not engine branches.
## Fee Product recurring Flat Amount

Fee Product Flat-basis Amount follows the common trajectory grammar without changing basis semantics. `rate.params.flat_amount` may be Flat, Growth, or Explicit and carries a natural Month / Quarter / Year period. Explicit authoring uses a pastebox and stores raw dollars while the UI consistently accepts `$000s`. Legacy `amount_per_period` and legacy `flat_amount` objects without a trajectory retain their exact prior economics.

## 8. Fee Product Account and derived-stock paths

The five fee bases remain the ontology; richer source trajectories do not create new bases.

- **Account** represents `count × fee per account/mandate/relationship`. Count may be Flat, Growth,
  or Explicit. Explicit counts are natural-period **end-of-period levels** with Step or Smooth
  resolution. Smooth is linear interpolation and is not rounded by the canonical engine. When the
  model cadence is coarser than the source-level semantics, Foundry resolves the level path on a
  conceptual monthly grid and averages it into the model period so economics remain cadence-stable.
- **Balance** may derive a stock from another stock with a stock multiplier, e.g.
  `Reserves = 30% × Avg AUC`. This is a stock transformation, not a transaction-flow coefficient.
  The stock multiplier may be Flat, Growth, or Explicit.
- Account per-unit pricing and Balance annualized pricing may each be Flat, Growth, or Explicit.
  Revenue start/end/ramp is a separate timing gate and never rewrites the underlying level path.

Legacy fee configurations without these opt-in path objects retain their existing economics.
