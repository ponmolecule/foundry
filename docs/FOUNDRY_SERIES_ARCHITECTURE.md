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

The channel outputs are module-owned Derived series and feed one common customer/AUC roll-forward;
the resolved AUC then becomes a canonical managed-notional series for downstream Fee Products.
Fee Products prefer that stable AUC `series_id`, while legacy name-based references remain readable.
For explicit source cadence finer than the acquisition equation cadence, flow operands such as Spend
and Explicit Customers sum; level/rate operands such as CAC, Pool, Conversion, Count, Productivity,
and AUC/customer average.

## 7. Release invariants

1. Existing configurations with no new Series/Link fields preserve baseline economics.
2. A linked series has one owner; consumers do not duplicate its trajectory assumptions.
3. Display-name changes do not break stable-ID links.
4. Unsupported or circular links fail closed.
5. Source cadence and projection cadence are separate concepts.
6. Explicit paths are properties of individual drivers, not reasons to reproduce source workbook
   grids.
7. New engagement names should normally require configuration, not engine branches.
## Fee Product recurring Flat Amount

Fee Product Flat-basis Amount follows the common trajectory grammar without changing basis semantics. `rate.params.flat_amount` may be Flat, Growth, or Explicit and carries a natural Month / Quarter / Year period. Explicit authoring uses a pastebox and stores raw dollars while the UI consistently accepts `$000s`. Legacy `amount_per_period` and legacy `flat_amount` objects without a trajectory retain their exact prior economics.
