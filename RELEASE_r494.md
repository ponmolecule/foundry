# r494 — Salary-linked LTI award cohorts

Adds Workforce → Long-term incentives. Select eligible roles; awards use actual annual base salary before role payroll load, including counts, hire dates and salary growth. Enter the award percentage, whole-year cliff and vesting duration. Each annual award starts after its cliff, contributes equal annual installments for the selected duration and then expires. Installments are spread equally across the current model year. Monthly and quarterly runs are supported; complete model years are required.

Historical awards require explicit original amounts and model award years at or before Year 0, or explicit confirmation of none. No client data is seeded. Historical inputs do not change opening assets, equity or retained earnings. LTI posts once to Workforce compensation without applying another bonus/benefit load. Headcount is unchanged. Existing bank cash-flow and balance-sheet settlement rules continue to apply; this is an expense-recognition feature, not a separate deferred-payable or cash-settlement feature.

The latest-run calculation shows eligible salary, new awards, expense and contributing award years. Calculation Audit exposes cohort installments, cliff and duration. Existing compensation pool and r493 cash-interest behavior is preserved.

Validation: 46 focused Python tests, 9 parity fixtures, 344 protocol checks and four Node suites passed. Tests cover cohort expiry, delayed starts, historical awards, selected-role hiring and salary changes, no double payroll load, monthly/quarterly aggregation, both engine profiles, opening balances, configuration immutability, public units and audit evidence. Browser integration and the complete repository test suite were not run.
