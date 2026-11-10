# r480 — Pasted schedules must match the horizon

Console only. No engine, validation or saved-input change.

Before r480, a schedule pasted with the wrong number of values was silently made to fit. 59 monthly values on a 60-month horizon were stored as 60, with M60 copied from M59; 61 values were cut to 60. The status line still said "59 values loaded". Several paths behaved differently again: periodized flows were left short and the engine filled the gap with zeros; fee paths stored whatever was pasted; only the lending funded-flow schedule required an exact count.

**At paste.** Every series paste now requires exactly the number of values the horizon needs at that schedule's cadence (on a 5-year horizon: 5 yearly, 20 quarterly, 60 monthly). A mismatch is refused:

> 59 values pasted. A 60-month horizon needs exactly 60. Nothing was loaded; the saved schedule is unchanged.

The pasted text stays in the box so it can be corrected. This applies to all 27 paste paths: fee drivers, rates, coefficients, multipliers, cost factors and cost recovery; lending flow and funded-flow schedules; deposits, interest-bearing balances, other assets and liabilities, fixed assets and pre-opening (shared series editor); securities; workforce count and compensation; operating-expense categories, formula factors, service levels, capacity and linked amounts; cost-pool components and markups; CAC channels and attrition.

**Saved schedules.** A schedule whose length no longer matches the horizon (for example after the horizon was extended) is flagged instead of hidden:

- the summary chip turns amber: "59 of 60 mo · …";
- the preview count reads "59 of 60" and a note names the gap: "M60 not entered. Schedule has 59 of 60 month values." or "M61–M62 beyond the 60-month horizon.";
- missing periods appear in the grid as "not entered"; periods beyond the horizon are struck through.

The model still runs on a flagged schedule with the engine's existing rule for that path (hold the last value for cadence series, zero for periodized flows), so behaviour of existing models does not change; the gap is now visible.

**Cadence changes.** Changing a schedule's cadence (e.g. Month to Quarter) no longer pads or cuts its values with the last value. An empty schedule is still seeded; an entered one keeps its values and is flagged until it is re-pasted at the new cadence.

Schedules saved before r480 that were padded at paste time cannot be told apart from fully entered ones; they hold 60 values and are not flagged.

Validation: web/tests_r480_schedule_length.cjs (10 checks: every paste handler calls the guard; 59, 61 and 60 values on a 60-month horizon; quarterly and yearly counts; saved short and long schedules flagged on chip, count, note and grid; cadence change keeps values; workforce count, opex category paths).
