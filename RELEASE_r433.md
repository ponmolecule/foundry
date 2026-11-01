# r433 — Field system for product authoring (fee-stream editor)

Built on r432 (ef9f799). Presentation only: no calculation, configuration-shape or save changes. Every value still flows through the existing setPath / select handlers.

The fee-stream editor's four steps (Activity, Pricing, Timing, Costs) now share one field layout:

- Labels sit in one 150px right-aligned column; the stream definition box is inset so its labels end on the same edge.
- Fields are sized to what they hold: names 320px, dropdowns 240px (or fitted to their longest option), amounts 150px, 32px tall.
- Path, cadence and step/smooth dropdowns with up to four choices become segmented buttons beside their value (Flat | Growth | Schedule, Month | Quarter | Year). The dropdown stays in the page, hidden, and the buttons drive it, so accessible names and existing handlers are unchanged. Compact phrases with several dropdowns (2.00 % per Year · Step at Model year) keep their dropdowns.
- A constant account count is one row: path segments, then the count.
- Participation share is its own modifier row under the count it scales, with Remove inline.
- Schedules are entered in a year × period grid: period-end count, stock % of source, flow coefficient and participation share. A cell writes its period key (blank removes it); paste remains available as an action.
- Results live only in the right-hand column at 980px+ container width; the in-form duplicate is hidden. Below 640px the form stacks to one column.
- Nested editors (shared cost pool, weighted breakdown) keep their own layout.

Validation: tests_r433_field_system (Python wrapper + Playwright harness) checks render non-mutation across all steps of six streams, label alignment, control widths and heights, the results column, grid edits and blank removal, segmented path switching, the count row, participation share grid storage (75 → 0.75) and removal, cadence segments, and the narrow layout. Full suite: no new failures against the r432 baseline (51 of 258 failing; r432 had 52 of 256. tests_r417_reporting_integrity.cjs passes on r433; it is timing-sensitive under load).

Next (release 2): the same rules for lending, deposits, fee products and customer acquisition.

ZIP contains delivery/foundry-full.bundle. BUILD_STAMP = foundry-r433-field-system.
