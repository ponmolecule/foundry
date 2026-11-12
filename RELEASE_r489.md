# Foundry r489 Shared assumptions and explicit funding

This release combines Claude r488 (b219178) shared-assumption editing with the completed funding change (a4b473da). The prominent Edit assumption panel and its consumer-scope disclosure are preserved.

Automatic borrowing is no longer an implicit balancing action. The default funding_shortfall_policy is show_shortfall for new and existing configurations that omit the setting. An underfunded model reports its signed cash position and funding requirement breach, including the opening position. Negative cash is an unfunded plan diagnostic, not an available overdraft or a funded asset position. Equity and entered borrowing are not adjusted to hide the deficit.

The alternative automatic_borrowing must be explicitly selected. Its generated financing is disclosed separately from entered borrowing schedules. Scheduled facilities continue to draw, accrue interest and mature under their existing rules.

## Authoring and review

Configuration > Securities > Funding and balance-sheet settings > Funding shortfall offers Show shortfall — no automatic borrowing (default) and Explicitly allow automatic borrowing. The policy also round-trips through the input workbook CONTROL sheet.

A global warning identifies the first opening or forecast cash requirement breach and peak dollar shortfall. An unfunded base plan is not presented as meeting modeled constraints. Every scenario has a funding feasibility test. The calculation audit adds Funding Diagnostics with opening and forecast cash position, cash requirement, cash-floor/target shortfall, unfunded cash below zero, automatic debt and entered debt. API funding amounts explicitly use dollars; audit monetary amounts use $000s.

An unsatisfied cash allocation cannot manufacture cash or debt. In no-auto mode, actual allocations are limited to available cash, original requests remain auditable, and the aggregate requirement breach remains visible. Negative cash does not earn negative cash interest. The bank cash position itself retains the deficit; it is not silently floored to zero.

## Engagement migration

This release changes financing behavior; it does not replace saved forecast assumptions with source balances. For a model intended to derive cash, change the interest-bearing cash component treatment from Part of bank cash to Remaining bank cash, remove reliance on separately pasted income balances in favor of the intended calculation, and reconcile the entire opening balance sheet. Review securities purchases/targets and explicit financing policies independently. Source forecast balances are comparison evidence, not calibration targets.

## Validation

New regression tests cover both engines, monthly and quarterly timing, opening and forecast deficits, optional automatic debt, entered facilities, cash floors, scenario feasibility, no negative-cash income, allocation shortfalls, audit periods/units and input-workbook round-trips. Existing settlement, tax, component inclusion and statement-link tests were also exercised.

All nine parity fixture financial outputs (balance sheet, income statement, ratios and products) match r487 exactly when automatic borrowing is explicitly selected. Eleven full-output snapshots were updated for the intentional default policy and new diagnostics; the historical r458 manifest remains retained.

Broad unittest discovery before the final edge-case checks: 428 tests; 9 failures and 15 errors, all present in the r487 baseline run. Baseline: 414 tests; 11 failures and 15 errors. Two stale historical snapshot failures were replaced by the current release snapshots. Browser integration is not verified: Chromium is unavailable in this environment. JavaScript syntax and funding-warning rendering checks pass. See the delivery validation report for final targeted test count.
