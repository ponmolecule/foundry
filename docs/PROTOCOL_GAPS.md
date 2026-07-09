
## PC-5 — Faithful replication (iteration 1 of the three-iteration plan)
**Directive:** replicate the predecessor HTML surface faithfully; the client pushes that first.
PC-4 violated it (fourth recorded scope-narrowing/scope-inflating incident): Config and Warnings
tabs, Sched/Code columns, CBLR/capital cards, preset chips, and securities/OBS sidebar sections
were not in the artifact; the Products and Stress surfaces were reconstructed from memory instead
of transcribed. PC-5 corrects by transcription: tab set (Products | Balance Sheet | Income
Statement | Ratios | Product Detail | Stress Testing | Assumptions & Notes), three-card sidebar
with quarter-labeled SOFR path, Products tab with Add-Product modal (preset grid + custom line),
line-level balance sheet, Per-Product Contributions plus per-product quarterly schedules with the
FTP toggle and both memo texts, scenario-comparison stress tab driven by the sidebar Stress
Scenario Settings, and flags/defaults/methodology notes. Theme per client refinement: Foundry navy
for all chrome including the cover band; black-on-white only where numbers reside.
**Parked (not lost):** Sched/Code columns, per-product BS detail rows, balance identity row,
per-quarter override grids, CBLR/capital cards → iteration 2 (JSX improvements, each with an
explicit case). Config tab, freeze/registry surface, workbook upload UI, securities/OBS sidebar
composers → iteration 3 (Foundry-native). Server endpoints for all of these remain in place and
tested; only the surface was narrowed to the faithful contract, which the UI-parity checklist now
encodes with tokens drawn from the transcription rather than from memory.

## PC-6 — Foundry v2.1 (iteration 2, approved scope only)
Client approved JSX items 1 (Sched/Code), 3 (per-quarter override grids), 8 (CBLR cards) with
the constraint that nothing degrades faithful replication and all additions are additive.
Implementation: one console file; every enhancement is gated on `window.V21`, which only the
`/v2.1` route sets — `/v2` remains byte-identical faithful PC-5, so deployment is a choice
between two live surfaces of the same engine. Presentation of items 1 and 3 transcribed from
the archived JSX; codes sourced from the tested `callreport.py` mapping rather than the JSX's
simplified codes. Items 5 (per-product P&L) and 7 (RC-L schedule) parked pending explicit
request; items 2, 4, 6, 9 parked without a scheduled case.
