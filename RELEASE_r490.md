# r490 — Securities target schedule layout; cadence changes never relabel values

Console only. No engine change. Built on GPT's r489 (5dab29b).

## 1. Target % with a schedule

Securities › Target allocation lays Target timing, First modeled period and Target % in three columns. Flat fits. A Schedule grew inside the third column: "Schedu" and "Montl" clipped, a 60-cell grid squeezed into a third of the width, and a tall empty band beside it.

Now Flat stays inline as before. Growth or Schedule moves Target % to its own full-width row under timing, in a light framed panel. Selects are wide enough to read, the summary and Close sit on one line, and the preview grid sits under Load / Clear across the full width.

## 2. Cadence change relabelled values

Example: 60 monthly values at 30%, cadence switched to Year. The 60 numbers stayed and were read as 60 years: "Y6–Y60 beyond the 5-year horizon. Schedule has 60 of 5 year values."

Rule now, for every level schedule editor (securities, shared Series editor, operating-expense factors and service levels, workforce counts and compensation):

- Convert when the resolved path is unchanged. Coarser to finer repeats each value (5 years → 60 months). Finer to coarser collapses runs that are equal within each period (60 equal months → 5 years). A note says what happened: "Converted 60 month values to 5 year values. The path is unchanged."
- Otherwise do not convert. Values that change within a period, include blanks, do not fill whole periods, use smooth interpolation, or are year-end targets cannot be reinterpreted without a rule. The new cadence starts empty, so the run flags the missing values instead of inventing them (no zero fill). The old values are kept for the session; switching back restores them. The note says why and how to restore.
- An empty schedule still seeds as before.

## Verification

- New: web/tests_r490_target_schedule_cadence.cjs (layout geometry for Flat and Schedule, readable selects, preview placement; conversions month↔year and quarter↔month; varying, blank, partial, smooth and year-end cases left empty; restore on switch back; no zero seeding after a failed conversion).
- Updated to the new rule: web/tests_r480_schedule_length.cjs (check 8) and web/tests_r474_factor_cadence_unit.cjs. Both had asserted that a cadence change keeps values unchanged, which is the behavior that produced the "60 of 5" bug.
- Passing: r412, r413, r430, r441, r451, r475, r481, r482, schedule loaded status, workforce capacity.
- Reference coverage regenerated.

## r491 follow-up (same change)

The full suite caught two tests that lift the series editors into a bare harness without the r490 helpers (tests_managed_securities.py, tests_balance_formulas.cjs). The editors and the seed guard now check the helpers exist before calling them. No behavior change in the console.

Full suite: 329 files, 15 failing. 12 are the long-standing baseline. 3 are new in GPT's r489 and fail the same way on r489 alone: foundry.tests_parity (A.8: 10 constraint tests, expected 5), foundry.tests_protocol (T41f/T42b: a crafted CRE concentration no longer raises the severe flag), web/tests_r414_balance_view.cjs (balance view rows empty, expected [9999, 1, 2, 3]). foundry.v2.tests_r459_component_switches, a baseline failure, now passes.
