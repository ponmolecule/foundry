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
model. New workforce configuration is a compact role/cohort table:

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
        "count": 2,
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

- One row may represent one position or a cohort (`count > 1`).
- `hire_period` and optional `end_period` are native model periods and can extend beyond the
  current horizon; out-of-horizon rows simply contribute zero during the run.
- Compensation is annualized and divided by `periods_per_year` only after its trajectory is
  resolved.
- Payroll load is workforce-specific (`salary * (1 + load)`).
- Existing NIE `other_gross_up_rate` remains a separate subtotal-level mechanism using
  `sub * r/(1-r)` and is **not** reinterpreted as payroll benefits.
- A 48-role spreadsheet is therefore a 48-row paste, not 48 bespoke configuration cards.

## UI principles

- Preserve Operating Expense's batch-paste workflow. A pasted batch can share common Growth
  defaults; users can load a 3% group, a 5% group, and a Flat group separately.
- `Linear (base + growth)` is renamed to `Growth`; the old storage shape remains readable.
- New Growth controls expose rate + period + Step/Smooth, with an anchor only when relevant.
- Workforce supports Paste roles and Add one manually. Batch defaults reduce repeated columns;
  row-level values may override them.
- Specialized fee-product axes remain intact; only the existing `Proportional growth`
  trajectory becomes cadence-aware.

## Release invariants

1. A configuration containing none of the new fields must reproduce the baseline economics.
2. Explicit schedules are not rewritten or smoothed.
3. Regulatory quarter concepts and contractual quarter terms remain quarter-based.
4. The resolver produces native-cadence absolute paths; downstream economics consume those
   paths rather than reinterpreting the user's growth cadence.
