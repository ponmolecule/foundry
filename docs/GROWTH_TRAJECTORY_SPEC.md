# Foundry Growth & Workforce Trajectory Contract

## Purpose

Foundry's computational cadence (monthly or quarterly) must not dictate the cadence or timing
of a business assumption. A monthly model can legitimately contain a 3% annual step, a 3%
annual smooth CAGR, a quarterly step, or an explicit monthly schedule. This contract provides
one canonical resolver for those meanings while leaving financial rates/APRs and other
specialized concepts alone.

## Canonical growth specification

Optional `growth_spec` objects use:

```json
{
  "rate": 0.03,
  "period": "year",
  "method": "step",
  "anchor": "model_year",
  "anchor_month": 7
}
```

- `rate`: proportional change for the stated period.
- `period`: `model_period`, `month`, `quarter`, or `year`.
- `method`:
  - `smooth` — mathematically equivalent compounding at the native engine cadence.
  - `step` — apply the full rate only when the chosen boundary is crossed; hold flat between.
- `anchor` (step only): `model_period`, `model_year`, `calendar_year`, `fiscal_year`, or
  `hire_anniversary`.
- `anchor_month`: 1–12, used only by `fiscal_year` (calendar year is January by definition).

Examples in a monthly model:

- 3% / year / smooth -> native monthly rate `(1.03)^(1/12)-1`.
- 3% / year / step / model_year -> M1–M12 flat; M13 +3%; M13–M24 flat.
- 3% / quarter / step -> M1–M3 flat; M4 +3%; etc.

A step period that is shorter than the computational period is invalid (for example, a monthly
step inside a quarterly model). Likewise, a fiscal-year step in a quarterly model must land on
a native calendar-quarter boundary. Foundry must not invent intra-quarter timing that the engine
cannot represent.

## Backward compatibility

`growth_spec` is opt-in. Existing fields keep their exact meaning when no spec is present:

- NIE `trajectory=linear` + `growth_per_period` remains per-engine-period compounding.
- legacy `growth_q` remains a calendar-quarter assumption converted through `timebase.py`.
- managed-notional and fee-stream legacy growth fields remain unchanged.
- legacy NIE `fte_by_year` + `loaded_comp_annual` remains supported and byte-identical.

New UI authoring should write the canonical schema; old configurations need not be migrated to
run correctly.

## Scope

### Uses the shared growth resolver

1. Detailed operating-expense categories (`nie_detail.categories`).
2. Simple corporate overhead (`overhead_growth_spec`).
3. Fee-stream proportional driver quantities (`driver.params.growth_spec`).
4. Managed-notional proportional trajectories (`managed_notional.growth_spec`).
5. Workforce compensation escalation.
6. CAC feeder annual growth internally, without changing its user-facing annual semantics.

### Deliberately excluded

- Pre-opening expenses: pre-M1/pre-Q1 burn is aggregated at opening.
- Loan/deposit/security APRs, yields, spreads and benchmark rates.
- Core loan/deposit balance-growth fields in this release; changing those semantics would be
  unnecessarily disruptive.
- Fee-rate `annual_change`: it is already explicitly annual pricing behavior and remains its own
  rate-axis concept.
- Explicit schedules: exact paths always win over inferred growth.

## Workforce authoring

The current `FTE Y1/Y2/Y3` construct is legacy-compatible but no longer the primary authoring
model. New workforce configuration is a compact one-position-per-row table:

```json
{
  "workforce": {
    "default_payroll_load_rate": 0.25,
    "default_salary_growth_spec": {
      "rate": 0.03,
      "period": "year",
      "method": "step",
      "anchor": "hire_anniversary"
    },
    "roles": [
      {
        "role": "Compliance Analyst",
        "annual_comp": 95000,
        "hire_period": 17,
        "end_period": null,
        "salary_growth_spec": {"rate": 0.04, "period": "year", "method": "step", "anchor": "hire_anniversary"},
        "payroll_load_rate": 0.28
      }
    ]
  }
}
```

- New authoring treats one row as one position. The legacy `count` field remains readable for backward compatibility but is not exposed in the primary UI.
- `hire_period` and optional `end_period` are native model periods and can extend beyond the
  current horizon; out-of-horizon rows simply contribute zero during the run.
- Compensation is annualized and divided by `periods_per_year` only after its trajectory is
  resolved.
- `default_payroll_load_rate` is workforce-specific (`salary * (1 + load)`). The UI calls this **Benefits & payroll** because it represents benefits, payroll taxes and employer burden added on top of base compensation.
- Existing NIE `other_gross_up_rate` remains a separate subtotal-level mechanism using
  `sub * r/(1-r)` and is **not** reinterpreted as payroll benefits.
- A 48-role spreadsheet is therefore a 48-row paste, not 48 bespoke configuration cards.

## UI principles

- Operating Expense has two mutually exclusive authoring modes: **Simple overhead** and
  **Detailed**. Simple carries one aggregate overhead path; Detailed builds the same economic
  output from Workforce Compensation, Operating Expense Categories, and Assessments & Other
  NIE. Switching modes is non-destructive in the browser: dormant detailed assumptions are
  preserved while Simple is active.
- Preserve Operating Expense's batch-paste workflow. A pasted category batch can share common
  Growth defaults; users can load a 3% group, a 5% group, and a Flat group separately.
- `Linear (base + growth)` is renamed to `Growth`; the old storage shape remains readable.
- New Growth controls expose rate + period + Step/Smooth, with an anchor only when relevant.
- Workforce defaults are true inherited defaults. A blank role-level Escalation or Payroll
  Load means "use the workforce default"; a populated row value is an explicit override.
- Manual workforce entry and spreadsheet paste share one canonical conceptual record:
  `Role | Annual Comp | Start | End | Escalation | Benefits/Payroll`.
  Each row is one position. Header-aware paste may omit optional columns or reorder them.
  Legacy `Count` / `Payroll Load` headers remain accepted on import but are no longer advertised. The recommended compensation
  header is `Annual Comp ($000s/FTE)`; generic `Annual Comp` remains raw-dollar compatible.
  Headerless legacy paste order remains accepted for backward compatibility.
- Spreadsheet guidance describes the user action (paste directly from Excel/Google Sheets or
  CSV), not the transport delimiter. Users are never asked to type tab characters.
- FDIC and OCC assessment defaults are displayed as actual values (5.0 bp/yr and 1.5 bp/yr)
  rather than blank fields with hidden fallback semantics.
- Specialized fee-product axes remain intact; only the existing `Proportional growth`
  trajectory becomes cadence-aware.

## Release invariants

1. A configuration containing none of the new fields must reproduce the baseline economics.
2. Explicit schedules are not rewritten or smoothed.
3. Regulatory quarter concepts and contractual quarter terms remain quarter-based.
4. The resolver produces native-cadence absolute paths; downstream economics consume those
   paths rather than reinterpreting the user's growth cadence.

## Workforce activation contract

Growth and activation are separate concerns:

- **Activation** determines when a role/cohort begins to exist.
- **Growth** determines how compensation evolves after the resolved hire period.

Existing rows with `hire_period` remain the simple/default grammar. A role may instead carry an
optional metric activation rule:

```json
{
  "activation": {
    "type": "metric",
    "metric": "managed_notional_end",
    "source": "Custody",
    "operator": ">=",
    "reference": "fixed",
    "value": 1000000000,
    "timing": "same_period"
  }
}
```

Canonical fields:

- `metric`: an approved modeled metric. Initial registry:
  - `managed_notional_end` — end-of-period AUC/AUM / managed notional for a named product.
  - `efficiency_ratio` — NIE / revenue, stored as a fraction for activation comparison.
  - `net_income` — native-period net income dollars.
- `source`: required only when a metric can exist in multiple named streams/products (currently
  managed notional). Product names must resolve uniquely. In the browser, source is folded into
  the metric choice (for example, `EOP AUC / AUM — Custody`) so the trigger editor remains
  **metric + comparator + value** rather than exposing a separate one-option source dropdown.
- `operator`: `>=`, `>`, `<=`, or `<`.
- `reference`:
  - `fixed` — compare with `value`.
  - `prior_period` — compare with the same metric one completed native period earlier, multiplied
    by `multiplier`.
  - `prior_year` — compare with the same metric one model year earlier (`periods_per_year` native
    periods), multiplied by `multiplier`.
- `timing`:
  - `same_period` — only permitted for pre-workforce independent observables whose current-period
    value is known before NIE is solved (EOP managed notional).
  - `next_period` — uses a completed period and activates in the following period. Required for
    endogenous financial metrics such as efficiency ratio and net income to avoid circularity.
  Browser authoring derives this timing automatically from metric dependency safety rather than
  asking the user to choose it.

Activation is sticky: the first period whose rule is satisfied becomes the resolved hire period.
From that point forward the role is ordinary workforce and uses the same salary escalation,
payroll load and optional end-period machinery as a fixed-period hire.

Examples:

- `hire_period=36` — unconditional M36/Q36-style native-period hire.
- `EOP AUC [Custody] >= $1.0B, same_period` — hire in the first native period meeting the threshold.
  For the engagement testcase with a monotonic AUC path, this is exactly the client's rule:
  count the N periods below the breakpoint, then hire in period N+1.
- `efficiency_ratio < 50%, next_period` — observe the completed period; hire in the next one.
- `net_income >= 2.0 × prior_year, next_period` — compare the completed period with the same native
  period one year earlier and hire in the next one.

This is intentionally **not** a general rules language. No arbitrary formulas, AND/OR expression
trees, or iterative circular solver are introduced. New approved metrics can be added to the
registry without changing the workforce schema.

## First-class managed-notional observability

Managed AUC/AUM was already rolled internally as average-period and end-of-period native-cadence
series. Those series are now promoted to public product outputs when the product carries managed
notional:

- `managedNotionalAvg`
- `managedNotionalEnd`
- `managedNotionalSource`
- Public `run_v2` output labels the converted paths as `$000s`; activation rules remain stored
  in configuration-native dollars and are evaluated against the pre-conversion engine series.

The CAC feeder also exposes the cadence-neutral alias `auc_end_by_period`; its historical
`auc_levels_q` key remains available for compatibility. This makes EOP AUC/AUM a stable observable
that workforce activation and future modules may reference without reimplementing the AUC rollforward.

## Bulk-entry clear behavior

Any bulk-entry surface with a Paste/Load action also exposes a **Clear** action beside Load for the
dataset it owns. In this release that rule covers:

- Pre-opening expenses.
- Workforce roles/cohorts.
- Operating-expense categories.

Clear affects only the corresponding loaded dataset, closes its transient paste box, and leaves
unrelated configuration untouched. When data exists, the browser asks for confirmation before the
bulk delete.
