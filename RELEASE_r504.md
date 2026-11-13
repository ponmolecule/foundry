# r504: Three corrections from the r503 review

Built on Claude r503 (babb515). A small corrective release; the architecture is unchanged.

## Engine and calculations

The engine is unchanged. Base results match r502 and r503 exactly. Calculations changed in two places: how an input is classified for a delay, and the LCR inputs check.

## Fixes

### 1. Classification reads the whole registered path

r503 classed inputs by the last part of the field name. `loan_rollforward.count_spec` ended in "count", so it was classed as a level and a delay held it (1, 1, 1, 2, 3).

r504 checks a fixed set of rules on the full path first. Each class carries a short reason that the Builder can show.

- **Flows:**
  - `loan_rollforward.count_spec` (new loans per period);
  - anything describing originations, whether a count or an amount;
  - acquisition volume and spend;
  - funded flows and expense flows.
- **Levels:**
  - a workforce role's `count_spec` (active headcount);
  - relationship staff.
- **Prices:**
  - roll-forward loan size;
  - deferred cost and fee per loan;
  - amounts per driver unit;
  - average balance per customer.
- **Other, the user chooses:** a bare "count", "amount", "quantity" or "volume" with no recognised context. Its delay will not run until the user picks a fill.

Reviewer's case: originations of 1, 2, 3, 4, 5 delayed two periods are now 0, 0, 1, 2, 3, and the delayed scenario runs with its checks passed.

### 2. The LCR never reads a missing run-off component as zero

The LCR has its own required-inputs check for each book:

- **Settlement advances and stablecoin books** need both the day-1 and the days-2-to-30 rates, or an entered LCR override.
- **Custody books** need their operational share. A missing share no longer defaults to 0% operational.

With an input missing, the LCR is "not calculated" and names what is missing. The calculation also refuses incomplete inputs when called directly.

Reviewer's case: a settlement book of 100, with day 1 missing, 40% for days 2 to 30 and no override, is no longer calculated at 40%. With a 45% override, it calculates at 45%, tagged as an engagement assumption.

### 3. The Reporting settings sheet is exported

In r503, an early `return` in `add_report_sheets` meant the Reporting settings sheet was never built. The return now comes after the sheet.

The exported workbook carries the sheet with the same fingerprint as the issued-package record, plus the policy minimums with their sources, the window, and the deposit and expense classes. The test opens the exported workbook itself.

## Validation

- `foundry/v2/tests_r504_corrections.py`: 20 checks pass, on the reviewer's own cases (the real `loan_rollforward.count_spec` field, the settlement book, the exported workbook).
- The r498 to r503 stress tests (Python and console) still pass.
- Engine output is identical to r502.
