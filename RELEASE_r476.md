# r476 — Responsive statement links for Other Assets

Built directly on r475 (519825a7), preserving its schedule preview changes.

Other Assets → Formula / level → component → Linked series now offers Bank · Total interest income and Bank · Total noninterest expense. Existing entered levels, schedules, fee income, workforce and fixed asset sources remain available. No saved engagement inputs are migrated or replaced.

Observe flow selects Current period total (default, preserving existing behavior) or Quarter to date total. QTD sums only committed prior months in the current modeled quarter plus the current month. In a quarterly model it is the current quarter total. In a monthly model it builds during the quarter and resets next quarter; it does not forecast future months or hold a future quarterly total across the quarter. Use entered schedules when that exact path is required. QTD requires monthly or quarterly cadence. Days outstanding uses current-period flow only; choosing QTD removes day conversion, and choosing Days outstanding restores current-period observation.

For the discussed formulas, create Interest receivable using Total interest income, QTD, multiplier 0.25; create Prepaid expense using Total noninterest expense, QTD, multiplier 0.30 (2.5% × 12). These are balance calculations; they do not post income or expense again. Opening balance remains separately authored. Total NIE includes workforce, other operating expense, depreciation, product operating expense and fee operating costs; it excludes credit provisions and taxes.

Profile A resolves responsive asset stocks inside the existing funding/income/equity/tax iteration, with an additional asset-stock convergence check. Only final period observations enter QTD history. Profile B observes its existing beginning-balance interest methodology. Audit traces retain the selected observation and resolved operands; the Other Assets workbook identifies period versus QTD flow units.

Validation: 22 Python tests across Other Assets, Other Liabilities, balance components, managed securities and tax integration; Node handler/source/syntax checks and r474 cadence checks. New coverage includes monthly QTD reset, both engine profiles, source equations including all NIE components, response to changed yield, invalid observations and unavailable history. Browser visual verification attempted but Chromium cannot launch here (socket permission denied).
