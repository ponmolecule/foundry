# r387 deposit authoring

## Existing data

Upgrade in place. Keep the two Operating Account products and any amounts, weights, source links, shares and pricing overrides already entered. Rendering does not create or replace a schedule. A previously entered period override remains in force until explicitly cleared.

## Compact breakdown

Under Balance per customer → Use a weighted breakdown, enter a label, raw dollars per customer and percent population weight per row. The total below shows the weight sum and weighted amount. Use the ellipsis beside an amount or weight for its existing Flat/Growth/Explicit path editor. Done returns to the compact table. A scheduled weight must total 100% with the other weights every month; the flat summary is not a substitute for engine validation of scheduled weights.

## Fixed deposit pricing

Under Pricing choose Fixed. Rate paid (annual %) is directly below it in the same group.

- Flat: a constant annual rate.
- Growth: the existing base and growth assumptions.
- Explicit: source cadence plus Step/Smooth where relevant; paste annualized percentage values and Load (replace). The last supplied rate carries forward. Loading collapses the paste box to a saved preview; View / edit schedule reopens it.

For Operating Accounts — Lower Tier choose Explicit, Year, Step and paste:

    1.25  0.95  0.65  0.65  0.65

For Operating Accounts — Upper Tier choose Explicit, Year, Step and paste:

    3.00  2.70  2.40  2.40  2.40

These are percentages, not decimal fractions. Interest balance measure remains Average (begin + end). Opening balance remains zero. The lower share stays 5%, the upper share stays 95%, and the upper product links only the lower product's per-customer amount.

## Period exceptions

Open the product's Per-month overrides (or Per-quarter overrides at quarterly cadence).

1. Select the field. Its value units are displayed.
2. Set From and Through period and the value; Apply to range writes that value to every period in the inclusive range.
3. Clear range removes only the selected field's overrides in that range, restoring the baseline or schedule there.
4. For varying exceptions, expand Paste consecutive period values, choose From, paste a row or column and Apply pasted values. Through is not used for paste. A zero is retained; empty tab-separated Excel cells clear the corresponding overrides. A plain text list can use spaces, commas or semicolons. A batch beyond the forecast or containing invalid text is rejected before any values are written.
5. Read the compact range summary to review existing exceptions. Inspect / edit individual periods retains the original grid if needed.

Rates are percent units. Money overrides are $000s. Existing stored values are not converted or migrated on display. New schedules do not erase old exceptions: clear obsolete rate overrides if the schedule should govern those periods.

## Preserved accounting

This release changes authoring and adds entered deposit-rate paths through the existing resolver. It does not alter practice acquisition, attrition, weighted balance amounts, 5%/95% balance shares, interest measurement or the Operating Accounts cost/revenue-share formulas. Source clarification items remain open.
