# r482 — Explicit schedules must cover the horizon (engine)

Engine and console. Calculations change only for schedules that were incomplete: those runs now stop instead of filling the gap. (Correction in r483: r482 also flattened the final interval of a smooth schedule that supplied a point beyond the horizon; r483 restores that, and complete schedules then give identical results.)

## What was wrong

r480 refused a mismatched paste but left three gaps:

1. **Blank cells in a paste** were dropped and every later value shifted one period early. `1 [blank] 3` loaded as `[1, 3]`. One blank plus one extra value passed the count check.
2. **The engine filled short schedules silently**, by a different rule per path: Series schedules held the last value; periodized flows (opex categories, linked amounts, capacity) were zero-filled and read a blank as zero; natural-period fee and cost schedules carried the last value forward; model-period rate schedules fell back to the base rate; CAC schedules held; annual balance targets held.
3. So a schedule left short by a horizon or cadence change, or a sparse fee schedule, ran without warning.

## What r482 does

**Engine.** Every explicit schedule the model actually uses must supply a finite number for every period the horizon reaches, at its authored cadence. A missing, blank or non-numeric period stops the run. Explicit zeros are valid. Annual or quarterly schedules in a monthly model are valid at their own cadence. Values beyond the horizon (after the horizon was shortened) are unused and allowed. The saved `extend` setting (hold / zero) no longer fills anything.

Strict resolvers: `series.py` (Series schedules), `periodic_flows.py` (periodized flows), `income_modules.py` (natural-period fee schedules, model-period rate schedules, legacy opex lists, explicit AUC levels), `cost_recovery.py`, `cac_feeder.py`, `balance_components.py` (annual targets). Blocking happens where a schedule is resolved, so a schedule kept dormant for a non-destructive mode switch (for example an account-count schedule while the stream is linked to a CAC count) never blocks.

**Messages name the component.** The resolvers know the cadence and period but not where the schedule lives, so `schedule_completeness.relabel` rewrites each such error using a walk of the saved assumptions:

> Fee product 'Customer-linked service fees' · stream 'Account fee' · unit fee: year schedule has 2 of 3 year values, Y3 missing

> Securities portfolio 'Managed securities coverage portfolio' · sleeve 'Liquidity sleeve Alpha' · yield: month schedule has a blank or non-numeric value at M6

A schedule that feeds several products (a CAC driver used by cost pools, account activity and lending) is reported once, not once per consumer.

**Console paste.** The parser keeps each cell's position. A blank inside the pasted range is refused before the count check: "Y2 is blank. Every period needs a value (enter 0 for zero). Nothing was loaded; the saved schedule is unchanged." Trailing empty cells from a spreadsheet selection and leading or trailing blank lines are ignored.

## Kept as event lists (not padding)

- Managed-notional `explicit_schedule` lumps: additive deltas, so an unlisted period is no change.
- Legacy CAC `new_customers_by_year`: its documented zero-after-list contract, which is also the zero node a switched-off channel becomes.

## Template

The universal template had two sparse schedules. They are now entered in full with the values the old engine used, so every result is identical (only the config hash changes):

- An account-count level schedule keyed Q1, Q4, Q8, Q12 (carry-forward) is entered for Q1–Q12.
- A deposit aggregate assessment rate schedule keyed M1, M13, M25 was being read as one-month changes (M13 and M25 only) with the base rate in every other month. It is entered for M1–M36 with those same values. If the intent was annual step-downs from M13 and M25, that is a data correction to make deliberately; it would change results.

## Tests

New: `foundry/v2/tests_r482_schedule_completeness.py` (17 checks), `web/tests_r482_paste_blanks.cjs`.

Tests that relied on silent filling now enter full schedules with the values the old rule produced, so their expected numbers are unchanged. Tests that lengthen a fixture's horizon use `foundry/v2/testing_schedules.fill_schedules_like_r481` (test-only; production never pads). Three checks asserted the old fill rule and now assert the new one: CAC "explicit hold-last extension", fee "flat explicit schedule carries last amount forward", opex "explicit follows schedule, pads 0".

Full suite on 3125211f: 321 files, 12 failing, the same 12 that fail on r481, r480 and r479. Nothing r482 touches fails.
