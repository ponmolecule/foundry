# r478 — Pre-opening income

Build time: 2026-11-09 14:47:10 CST (America/Chicago).
Built on r477 (0b189d85), retaining r475 preview changes and all asset/liability links.

Capital structure & pre-opening now has named Pre-opening income rows, separate from expenses. Click Add income, enter a category and a nonnegative total in $000s. Saved pre_opening.incomes amounts are raw dollars. No engagement inputs are migrated or baked in. For the current reconciliation, an earned interest row of 10,470.365100 $000s represents the supplied Year 0 total; existing expense rows still need the separately identified $8.14 reconciliation.

Income less expenses enters opening retained earnings and capital/funding once, in both engine profiles. Income is not reposted to forecast periods. Forecast interest may change economically with funding balances. CAPEX remains a cash use and capitalized asset, not an expense. These are manually authored recognized pre-opening totals; tax/expense recognition before opening remains separately authored rather than automatically calculated on income rows.

The capital sufficiency summary includes income, expenses, net income, gross and net cash uses. Existing burn_total remains gross expenses for compatibility. Opening cash can still be allocated or borrowed under configured funding policies; income is not a forced independent cash deposit on top of fixed opening balances.

FIW has an editable ASSM_PREOPEN_INCOME sheet, including import round trips. Audit workbooks include a Pre-opening table with named amounts and totals in raw dollars; Config Snapshot also preserves inputs. Income values reject negative, nonnumeric and nonfinite inputs. Omitting incomes preserves the expense-only calculation.

Validation: 12 Python tests across new pre-opening behavior, fixed assets and responsive asset/liability regressions. New checks cover both profiles, opening retained earnings, capital sufficiency, income-only inputs, FIW edits and imports, audit export, invalid inputs and legacy totals. Node checks verify add/remove controls, dollar scaling, rendered authoring markup and complete inline-script syntax. Visual browser testing is unavailable due the previously established Chromium launch restriction.
