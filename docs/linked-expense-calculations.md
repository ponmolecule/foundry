# Reusable linked expense calculations (r383)

Operating Expense categories retain their existing recurring amount, Formula, Tiered bands and Cost pool options. **+ Linked calculation** adds an optional, separately named component. Only its final monetary result posts to that category. The operands are read-only observations, not additional income or expense postings.

## Authoring

Open a category's additive components and choose **+ Linked calculation**. Give the calculation a name. Each step has an operation and an optional descriptive name. Nested steps remain collapsed until opened; open state is local UI state, not an engagement assumption.

Available operands:

- **Entered assumption**: Flat, Growth or Explicit path; units are factor/rate, money in $000s, or count. The optional natural period converts an amount/factor exactly once: annual / periods per year, monthly × 12 / periods per year, quarterly × 4 / periods per year. Schedule cadence and natural period are separate choices. No conversion is the default.
- **Linked balance**: a stable catalog source with beginning, ending or average (begin + end) measure.
- **Reference rate**: EFFR, SOFR or Prime from the model's resolved curve, including engagement schedules and scenario shocks. It is an annual decimal rate. To accrue it, multiply by an entered factor of 1 with natural period Year (1/12 monthly, 1/4 quarterly).
- **Deposit interest expense**: one product's actual current-period interest expense, including any minimum-interest top-up. The stable product ID survives renaming.
- **Gross customer flow**: an eligible acquisition feed or channel's gross acquisitions/losses, observed either for the current period or cumulatively since forecast start. Cumulative gross acquisitions exclude opening accounts and do not subtract attrition. Straight-line legacy feeds do not become eligible gross-flow sources by being referenced here.

Operations: Add, Subtract, Multiply, Divide, and If positive / otherwise. Every binary operation has two explicitly grouped operands. The conditional has a condition, positive branch and otherwise branch; only the chosen branch evaluates. Division defaults to an input error on zero; returning zero must be explicitly chosen. Negative monetary results are preserved, with no implicit zero floor.

Matching units are required for addition/subtraction and conditional result branches. Division of matching units gives a factor. Multiplication requires a dimensionless operand. The final result must be money. Expressions are bounded to 12 levels / 128 nodes and do not accept arbitrary Python, spreadsheet formulas or current expense/equity feedback.

## Cadence and audit

A monthly model evaluates monthly observations. A quarterly model evaluates quarterly observations and current/cumulative quarterly gross flows. Applying a nonlinear ratio or conditional once per quarter is not the same as summing three monthly evaluations. Use monthly cadence to reproduce monthly source logic; there is no silent monthly reconstruction.

Calculation Audit Workbook → **Operating Expense** contains the final component amount in $000s. **Opex Component Detail** contains every evaluated operand/operation, named path, raw value, units and final expense. Monetary operands on that detail sheet are raw dollars. Unchosen conditional branches do not appear as evaluated observations.

Existing categories and formulas are not migrated or rewritten. Profile A and Profile B use their actual deposit-interest calculations. Existing Profile B restrictions on deposit balance authoring still apply.
