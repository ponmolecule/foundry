# r475 — Schedule previews keep numbers whole

Presentation only. No engine, validation or saved-input change.

Entered schedules (for example an Interest-bearing balance term or an income balance basis entered as 60 monthly values) showed their values squeezed: the compact strip let cells overlap, and the expanded grid wrapped decimals onto a second line (547,174.65 / 167).

- **Expanded grid.** Column width is set from the longest full-precision value in the schedule, and values never wrap. 547,174.65167 shows on one line in every cell. The grid scrolls if a single column is wider than the drawer.
- **Compact strip.** Cells size to their content and never overlap. Values are display-rounded (547,174.65) with the full value on hover (M1: 547,174.65167). The strip shows six cells when there is room, four (first two, last two) at medium widths, and two (first, last) when narrow.
- **Summary chip** ("60 mo · 547,174.65 → 3,971,664.28 $000s") uses the same display rounding; the full first and last values remain in its tooltip.
- **Copy values.** The open grid has a Copy values button that copies every value at full precision, one per line, without thousands separators, ready to paste into Excel or back into the paste box.
- **Narrow pages.** Formula-term rows (Interest-bearing balances, Other assets, Other liabilities) now stack the schedule drawer under the label below 900px, instead of squeezing it into the 112px label column. Series controls wrap instead of running past the card edge.

The shared preview (`_explicitPreviewHtml`) is used by every entered schedule in the console, so the same fix applies to fee, lending, deposit and workforce schedules.

Validation: web/tests_r475_schedule_preview.cjs (6 rendered checks: no wrapping or clipping in the grid at 1440 and 900px, strip cells unclipped with full-value tooltips, chip rounding, copy content and clipboard write, responsive strip at 700/480/320px containers, quarterly schedules).
