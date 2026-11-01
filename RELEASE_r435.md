# r435 — Use of space, loan-production panels, product schedule grids, product settings

Built on r434 (90ff7cc). No calculation or configuration-shape changes. Schedule cells write through the same conversion as the existing paste path, proven by test.

Use of space:

- Two ends of one range share a row: Rate bounds (Floor | Cap) on deposit and floating-rate pricing; Revenue months (Start | End, "never" shown in an empty End) on fee-stream Timing; Opening book (Customers | AUC) in acquisition feed settings.
- A path no longer has its own row: "Fee path", "Markup path" and similar move beside the value they shape, with the "per" period after it (Fee ($000s/account): Flat | Growth | Schedule · 0 · per Month | Quarter | Year). Three rows become one.
- Kept stacked on purpose: index beta and spread, op cost % and op cost fixed, charge-offs and ALLL reserve. They are separate settings, not one range.

Loan-production panels (separate payment and prepayment rates) now use the label column on every step, including when opened in the narrow layout; their 120-layout test passes.

Product schedules (yield, rate paid, loan-production paths and any other explicit Series on lending, deposit and off-balance-sheet products) are period grids instead of the "View / edit schedule" panel. A cell writes value ÷ 100 for rates, the typed value for counts / multiples / dollars / days, and × 1,000 for $000s amounts, then resizes the series exactly as paste does. Paste values… and Clear remain on the grid; Load closes the paste box.

A row that holds a schedule grid keeps its label at the top, beside the path.

Product settings panel (Edit settings): product name, balance method, opening balance, measurement, product type and reporting category on one label column.

Tests changed for the new layout (assertions on stored values unchanged): tests_r381_deposit_pricing now expects "Rate bounds" in place of the two rows; tests_r389_authoring opens paste from the grid and reads loaded values from the cells.

Validation: tests_r435_space (py + node): grid vs paste storage equivalence for seven unit kinds, inside and beyond the entered values; the yield grid replacing the old panel and writing 7.25 as 0.0725; Rate bounds side by side writing the cap; settings labels on one edge; fee path beside the fee and still writing; Revenue months; opening book writing opening customers. Full suite (before the final label-alignment CSS line): no new failures against the r434 baseline (51 of 262 failing; r434 had 51 of 260; the two new modules pass). After that line: the field-system, layout, deposit and count-breakdown browser tests rerun and pass.

ZIP contains delivery/foundry-full.bundle. BUILD_STAMP = foundry-r435-space-and-schedules.
