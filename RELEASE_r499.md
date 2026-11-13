# r499: Stress testing, reporting core

Built on Claude r498 (860b98e). Implements r499 of the shared release plan (r499 to r502) with GPT's amendments: run evidence, input registry, one reporting window, primary case, Tables X and Y, capital against three threshold tiers, and the Executive Summary block. The stress tab is reorganized around one job per view.

## Engine and calculations

Base balance sheet, income statement and capital calculations are unchanged. Two presentation conventions in the engine's annual summary changed, on purpose:

- Annual ROA is now annual net income over time-weighted average total assets (mean of each period's opening and closing balance). It was an average of monthly annualized ratios. Annual ROE is added on the same basis with equity.
- Annual efficiency is now annual noninterest expense over annual revenue. It was an average of monthly ratios.

These figures move slightly on the Executive Summary and peer views. They now equal the business-plan exhibit and the stress Tables exactly (tested). A full output diff against r498 over the eleven pinned fixtures shows no other change (annual ROA, efficiency, ROE, the annual note, the quick-stats rows that mirror them, and run_hash); the r488 output-hash manifest is re-pinned accordingly. `stress_reporting` joins `stress_scenarios` outside the base: excluded from config_hash, run_hash and the base fingerprint.

## Evidence

- Supported-input registry enforced in backend resolution and validation. Structural and timing settings (`n_periods`, `periods_per_year`, underscore keys) are rejected by name. Each entry carries units, bounds and permitted operations; a stressed rate outside -100% to 100% or a negative count is rejected by name.
- Each run archives its baseline configuration (once per base fingerprint), the base result (once per base and engine), and its stressed configuration and result. Records are never overwritten. Runs > Details > "Confirm it reproduces from the archive" reruns from the archived base and compares the result hash.
- One reporting window (default: the full projection; `stress_reporting.window_periods` narrows it). Run measures, attribution, Tables and capital all use it. Partial years are flagged and their rates annualized.

## Reporting (Stress Testing > Reporting)

- Primary reporting case: one completed run, stored with the engagement. Stale when inputs or the scenario change; never replaced by the worst case.
- Capital: Tier 1 leverage, CET1/RWA, Tier 1/RWA and Total/RWA from the engine's standardized calculation. Three tiers kept separate: regulatory (well capitalized; CBLR requirement for leverage when elected), charter commitment, bank policy (blank until entered, with source). Lowest ratio and lowest dollar cushion each carry their own date; first breach names ratio, tier and period.
- Tables X and Y: every template row, stressed value and change from base for each year. Stocks at year end, flows summed. Rows the model cannot split say "not separately available". HTM securities and loans held for sale get their own lines when present.
- Deposits: explicit, user-confirmed interest-bearing / noninterest-bearing per product. A rate-based suggestion is shown but never decides. Until all are confirmed the split is not shown and total deposits are.
- Expenses: workforce pay maps to salaries and depreciation to premises automatically; each operating expense category can be mapped (presentation only; totals unchanged).
- Export submission tables: Table X, Table Y and Capital vs Thresholds sheets, from the archive.

## Layout

A rail names each place by purpose: 1 Make a change (Scenarios, Builder), 2 Run (Runs), 3 Understand (Results), 4 Submit (Reporting). Every view opens with its name, one line on what it is for, and its main action. A status line shows the primary case, window and funding. Runs groups Current, Stale and Failed, with the next step when runs are stale. Results shows the comparison grid, the attribution waterfall and the line chart in the open; detail sits behind disclosures. The duplicate page band above the tab is gone.

## Validation

- Full suite: 342 files; the 11 failures are the long-standing baseline. Two new failures in the first pass were fixed: duplicate CSS selectors (merged into the r498 rules) and the pinned output hashes (re-pinned after the diff above).

- `foundry/v2/tests_r499_stress_reporting.py`: 47 checks (registry, bounds, hash exclusion, window, archive and immutability, reproduction, Table identities in both cases and every year, deposit and expense classification, ROAA/ROAE/efficiency equal to the engine, three tiers, cushions and dates, quarterly cadence, endpoints, export, stale primary).
- `foundry/v2/tests_r498_stress.py`: 35 checks still pass.
- `web/tests_r499_stress_reporting_ui.cjs` and the updated `web/tests_r498_stress_ui.cjs`: rail, Runs, Reporting, classification, export, Executive Summary block, stale primary.
- Browser walkthrough against a live server: two severities run, stored with archives, primary set, deposits classified, Table Y, Executive Summary block.

Not in this release: Lab alternative rows in the comparison grid (r501); scenario classes, rate-path and delay operations (r500); reverse stress and management actions (r501); NTB liquidity profile (r502).
