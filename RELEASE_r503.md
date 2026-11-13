# r503: Corrections from the r499 to r502 review

Built on Claude r502 (a5f11a4). This is a corrective release. It fixes all eight findings in the review, and each fix has a regression test built on the reviewer's own case. The architecture is unchanged.

## Engine and calculations

**The engine changed in one place: a new, opt-in funding policy, `contingency_facility`.** Base results and existing policies are unchanged:

- The r488 output-hash manifest still holds.
- A direct comparison against r502 gives identical results for the stress test bank, and for both profiles under automatic borrowing.

**Calculations changed in three places:**

- the delay operation;
- reverse-stress statuses;
- the liquidity tests.

Each is described below.

## Fixes

### 1. Delay follows what an input is

Every input now has an explicit economic class: flow, stock, quantity, price, rate or other. The class comes from a fixed contract keyed on the field name. It is no longer inferred from whichever rewrite happens to reproduce the base.

How a delay fills the gap follows from the class:

- **Flows:** nothing happens during the delay (zero).
- **Stocks, quantities, prices and rates:** they hold their prior level.
- **Inputs outside the contract:** the user must choose a fill before the delay will run.

In the Builder, the class and the fill are visible and the fill can be changed. The run's disclosure records both, and whether the fill was the class default or a choice.

Reviewer's case: a monthly origination count of 1, 2, 3, 4, 5 delayed two periods is now 0, 0, 1, 2, 3.

### 2. Reverse stress never reports "no breach" from failures

- **Failures are recorded as failures.** An evaluation that fails, or that has no capital measure with an applicable threshold, is recorded as failed, never as "no breach".
- **New statuses.** "Search failed" means no evaluation produced a result. "Inconclusive" means there was no breach where it could be measured, but some evaluations failed.
- **Limitations** state how many evaluations failed.
- **No formal record for a failed search.** It cannot be promoted to formal evidence.

### 3. The contingency line is a constrained facility

The management action now uses a facility that the engine enforces in the funding calculation, in both engine profiles:

- no draws before the period the line becomes available;
- no draws above the commitment;
- any shortfall beyond that stays unfunded, and the action says so;
- drawn balances are priced at the line's own rate (the borrowing rate plus the line's spread);
- the general borrowing rate is left alone.

Reviewer's case: a shortfall far larger than a 20,000 ($000s) line available from period 12 draws nothing before period 12, never more than 20,000, and leaves the rest unfunded.

### 4. No book is skipped in the liquidity tests

Each test checks every input it needs, for every book. The daily run needs the day-1 rate as well as the later rates. If any book is incomplete, the test is not calculated and the missing inputs are named. It is never a "complete" result with that book left out.

### 5. No extrapolation past day 30

- **The 30-day path stops at day 30.** The days-2-to-30 run-off is spread over those 29 days and nothing more.
- **Longer runs need their own assumption.** A 60 or 90-day run requires a separate after-day-30 rate per book; without it, the test is not calculated.
- **Conservation is enforced.** Run-off over the whole run cannot exceed 100% of the balance.
- **Reviewer's case:** a book of 100 with nothing after day 30 now loses 100 over 90 days, not about 307.

### 6. One answer on whether the line can be used, in every view

The intraday test, the daily run and the LCR all use the same check of whether the line can be drawn at the stress month. When it cannot, the LCR line-draw table is labeled "hypothetical", a sensitivity rather than an available source. The intraday test and the daily run leave the line out.

### 7. The same cash cannot be counted twice

The following are refused:

- resources whose shares of one balance-sheet line add up to more than 100%;
- an entered resource declared "part of projected cash" (or securities) that is larger than the unallocated balance;
- a deposit product in two books;
- a book on total deposits alongside books on individual products.

Entered resources now say where they sit: outside projected cash and securities, or part of one of them.

### 8. Report rows are joined by key

Base and stressed statement rows are matched by their reporting key, never by position, and the union of rows is kept:

- **HTM and held-for-sale** appear when either case holds a balance; the other case shows its own computed zero.
- **A row on one side only** is shown as unavailable on the other, not as zero.

## Also addressed from the review

- **Reporting settings have their own identity.**
  - Each run keeps the reporting settings in force when it ran, with a fingerprint.
  - The report flags when settings changed since the run, and can be rebuilt on the settings the run used.
  - Each exported submission package is recorded with the run, the settings it used and their fingerprint, and the workbook carries a reporting-settings sheet.
- **LCR scope is stated.**
  - The LCR is labeled a simplified management calculation.
  - A "Rule rate" tag means the engagement chose the rule's category for a balance, not that the balance has been shown to qualify.
- **Post-draw capital is labeled an illustration.** The balance-sheet adjustment is not a rerun; fees and drawn interest run through Results › Management actions.

## Not in this release

Ranking proposals from each engagement's concentrations, dependencies and fixed commitments remains future work. The scenario classes and coverage checks from r500 stay as they are.

## Validation

- `foundry/v2/tests_r503_corrections.py`: 43 checks pass, one block per finding, using the reviewer's cases.
- `web/tests_r503_corrections_ui.cjs` passes.
- Updated for the new contracts:
  - `tests_r499_stress_reporting.py`: group rows are keyed, and HTM is a conditional row;
  - `tests_r500_scenario_design.py`: the delay discloses its class.
- The r498 to r502 stress tests (Python and console) and the r501 reverse-stress and actions tests still pass.
