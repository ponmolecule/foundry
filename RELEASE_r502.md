# r502: Liquidity stress, trust banks first

Built on Claude r501 (c0c590b). Implements r502 of the shared release plan, following the approved mockup: Stress Testing > Liquidity, with Results, Setup and LCR detail.

## Engine and calculations

The engine and the base calculations are unchanged. Liquidity stress reads a projection and never changes it.

- Liquidity settings live in `liquidity_stress`, beside the stress scenarios and outside the base.
- They are excluded from the configuration hash, the run hash and the base fingerprint, like the stress keys. Existing hashes do not move.
- A test confirms the engine result is identical with and without the settings.

All new arithmetic is in `foundry/v2/liquidity.py`. Amounts are $000s throughout.

## What can leave: redemption books

One book per kind of client claim:

- **Client custody cash:** balance from the deposit products the user ticks, at the stress month.
- **Fund share settlement:** the bank's settlement advances, repaid after a settlement lag (an inflow in the 30-day run).
- **Stablecoin:** prospective. No engagement issues one yet, so it shows as "Not in this engagement" with an Add button.
- **Other deposits.**

Each book has:

- day-1 and days-2-to-30 run-off by severity (severe, moderate);
- day-1 timing as nine hourly weights, 08:00 to 17:00;
- an LCR category, or an override;
- a calibration record: draft, reviewed or approved, with its source.

## What the bank can use, and when

Each resource has:

- a balance, from projected cash or securities, or entered;
- the time on the stress day from which it is usable;
- a haircut;
- an HQLA level (1, 2A, 2B or none).

The contingency line has its commitment, usable time, cutoff, the month it becomes available, its repayment term, and the HQLA pledged when it is drawn.

## The tests

- **Stress day, intraday.**
  - Minute by minute on one day in the chosen month (the lowest-cash month by default).
  - Reports the lowest cushion and its time, each shortfall window, and which resource closes it.
  - Says when the line comes too late or cannot be drawn before its cutoff.
- **30-day run (or 10, 60, 90 days).**
  - Daily closing liquidity, the lowest close and the binding day, and survival days.
  - Shows whether the line is needed, and the draw.
- **LCR.**
  - Shown as a management measure below $100B in total assets, where the rule does not apply. At $100B or more it is flagged "rule may apply".
  - HQLA with Level 2 caps.
  - Each outflow row is tagged with where its rate comes from: the rule (for example 25% on operational custody cash) or an engagement assumption.
  - Inflows are capped at 75%.
  - The line draw is shown before and after, both repaid after 30 days and due within 30 days. Tier 1 leverage and CET1 / RWA are shown alongside.
- **Stablecoin reserve adequacy.** When a stablecoin book exists: reserve coverage after haircuts, and same-day reserves against day-1 redemptions.

## Applicability

Each test has three separate statuses: Applies?, Foundry calculates?, and Inputs. A missing input is never filled with an invented value: the test is not calculated, and the missing input is named. For example, without a days-2-to-30 rate the 30-day test stops, while the intraday test, which needs only day-1 inputs, still runs.

## Runs

- **Projection:** a liquidity run reads the base projection or any current stored stress run (its archived stressed balance sheet).
- **Records:**
  - "Run liquidity stress" stores a liquidity record. On the base, the baseline is archived; on a stress run, it links to the parent.
  - The record goes stale when the base, the liquidity settings or the parent scenario changes.
  - Runs lists it with a "Liquidity" label.

## Console

- **Rail:** Liquidity sits under "3 · Understand".
- **Results:**
  - What applies.
  - The stress-day chart: cumulative outflows against usable resources by hour, with the shortfall shaded.
  - The 30-day bar chart.
  - The line-draw table.
- **Setup:** book cards, the resources ladder, the line, which day to stress, and LCR.
- **LCR detail:** the HQLA and outflow tables with rule and engagement tags.
- **Empty state:** when nothing is set up, "Start from a draft" applies a template with every rate flagged as a draft.

## Validation

- `foundry/v2/tests_r502_liquidity.py`: 60 checks pass. They cover:
  - base and hashes untouched;
  - template and structural validation, with refusals by name;
  - balances read from the projection at the stress month;
  - hand-computed intraday windows and cushion;
  - hand-computed 30-day run, line and settlement lag;
  - hand-computed LCR, inflow cap and Level 2 cap;
  - line draw on LCR and leverage;
  - missing inputs, stablecoin and line availability;
  - endpoints, records and staleness, and the stress-run projection.
- `web/tests_r502_liquidity_ui.cjs` passes.
- `web/tests_r499_stress_reporting_ui.cjs` was updated for the new rail item.
- The r498 to r501 stress tests and the Lab tests still pass.
