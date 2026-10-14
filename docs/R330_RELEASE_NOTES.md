# r330 — Entity-level Other income and authoring clarity

Built as a clean continuation of r329. No template or engagement data is changed.

## Other income

Configuration now has a separate Other income module. Add a named line, choose Other income or Dividend income, and enter a Flat/Growth/Explicit amount path. The amount period is explicit. A Linked quantity alternative consumes an upstream monetary-flow fee quantity with an explicit income-per-dollar multiplier; it never borrows an existing fee stream revenue or cost. Unsupported sources fail closed.

Entered amounts resolve monthly before quarterly SUM aggregation. Each line posts once to `otherIncome`, outside fee products and cash interest, and feeds pretax income, the configured tax ledger, retained earnings and the existing cash/funding solve. Noninterest-income totals, efficiency ratios, Call Report income and peer revenue include it; fee-only and net-fee metrics retain their narrower scope. Income Statement, All Series and a new Other Income audit worksheet expose the amounts. The setting and all new result fields are absent for historical configurations.

## Deferred authoring fixes

- Fee roles distinguish Driver, Revenue, Cost, and Revenue + Cost. This does not change posting.
- Explicit workforce compensation has its amount interpretation and Total/Per-FTE controls inside the schedule editor. The top editor summarizes the schedule instead of presenting a competing base input. Pasted annual rates remain annual rates unless the user changes their interpretation; existing stored values and calculations are untouched. The preview shows conversion of the first amount to a model-period amount before benefits/load.
- Discard & switch retains its target and dialog on failed loading, reports errors, and hides the guard only after a successful switch. A successful switch uses the saved configuration and preserves the selected content tab. This hardens previously silent unsuccessful loads; the original user incident could not be reproduced from a saved failing session.

No subsidiary consolidation or investment accounting is inferred from the descriptive Dividend income classification. No engagement-specific product name, rate, schedule or workbook address is built into the engine.
