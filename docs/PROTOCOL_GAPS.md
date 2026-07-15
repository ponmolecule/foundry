
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

## PC-7 — Client-directed presentation divergence (skin only)
Client reviewed v2.1 against the predecessor side by side and issued a new styling directive
superseding "100% faithful" for visual presentation only: keep every structural element the
checklist enforces (tabs, rows, labels, memos, sidebar, modal) but render to a Capital IQ
standard with the Foundry palette — full-width tables, white-on-navy header band with gold
rule, warm ivory zebra with row hover, horizontal-rule grid instead of full cell borders,
champagne grand-total bands, gold-ruled section titles, brighter sidebar labels. Applied
identically to the v2 branch and main so both deployment options carry it; the faithful
STRUCTURE checklist is unchanged and still green on both.

## PC-16 — v2.2 phase 1 (iteration 3, items 1 / 7 / 2)
Client approved all seven Foundry-native items. Phase 1 ships the pure-additive trio behind a
V22 flag served only by /v2.2 (which also enables the V21 layer; /v2 and /v2.1 untouched):
config front door surface (scenario JSON download/upload; banker workbook download/upload over
the existing gate-tested endpoints), run registry (freeze -> notarized config+hashes on disk,
list, re-verify that re-executes the frozen config and must reproduce hashes exactly), and the
API made usable (FastAPI auto-docs, previously exposed UNAUTHENTICATED in production — closed
and gated behind basic auth this commit). Registry storage lives under FOUNDRY_DATA_DIR; without
an attached volume the surface banners that frozen runs die on redeploy rather than implying
durability. Gate gains a v2.2 section including a live freeze->re-verify roundtrip.
Correction to the record: earlier claim that a freeze endpoint already existed server-side was
wrong — config/workbook endpoints existed; freeze/registry/verify are new in this commit.
Remaining iteration-3 items: 3 (coupled rules), 6 (lifecycle), 5 (roster), 4 (peer evidence).

## PC-18 — Naming: the top rung is Foundry v3
Client ratified the ladder: /v2 (faithful HTML replication) -> /v2.1 (+ approved JSX items
1/3/8) -> /v3 (+ Foundry-native layer). The former /v2.2 route is renamed /v3 with /v2.2 and
/v22 retained as aliases; the layer flag is window.V3 (window.V22 honored for back-compat).
Each rung remains an intact, separately shareable surface of the same engine.

## PC-19 — v3 Overview: the v1 front page on the v2 engine (items 3 surface + 6 partial)
The Overview tab is transcribed from web/index.html (kcards grid, coded flags with the v1
class taxonomy, constraint-tests-every-scenario table) and rendered from the v2 payload:
readiness (open items / hard stops from base-scenario constraint tests), min base leverage,
breakeven quarter, Q12 assets/deposits, cumulative NI. Correction to the record: item 3
(coupled-inconsistency rules) was already implemented server-side in challenge_q.py
(COUPLED-01/02, structural versions) — the earlier claim that it was unbuilt was wrong; this
commit surfaces it and adds a gate assertion that pf_a_base fires a COUPLED flag. The v1
peer-percentile versions of the coupled rules return when the evidence layer (item 4) loads
real cohort data. Overview is the default tab on /v3 only.

## PC-25 — Stale-memory incident: CBLR calibration; versioned regulatory parameters adopted
A parallel-model build carried the correct current CBLR calibration where Foundry carried the
pre-2026 one from memory: the interagency final rule (91 FR 22973, FR Doc. 2026-08298,
effective 2026-07-01) lowered the CBLR requirement from 9% to 8% and revised the grace period
(4 consecutive quarters above a 7% floor, max 8 of the prior 20). Verified against the Federal
Register, OCC Bulletin 2026-15, and GAO B-338364 before adoption. Corrective doctrine, taken
from the other build's design: foundry/v2/regparams.py is a versioned, cited parameter set;
regulatory values resolve from it, never from memory; the payload carries the version block;
the surface prints it; the gate fails on a missing version block, a CBLR check not resolving
to 8%, or stale "CBLR 9" framing in the console. Checks gained the trading-assets criterion
(structurally zero here, caveat-registered) and a grace-period state summary. The 9% in
fixture configs is preserved as what it always was — a client chartering commitment — and the
embedded methodology prose was corrected with a bracketed rule-update note rather than
silently rewritten. Larger adoptions from the parallel build (capital derivation rows,
threshold chart, per-quarter qualification grid, management-target tier) remain proposed,
not built, pending client approval.

## PC-25b — Process incident: heredoc broke a conditional chain; red gate got committed
The PC-25 commit was initially created despite a failing parity gate: a heredoc used to write
this very ledger terminated the shell's &&-chain, so the commit ran unconditionally after the
gate failure (and the ledger write itself was skipped). Third output-handling failure of the
engagement, after a grep and a tail each masked a nonzero exit. Standing rule adopted: gates
and commits run as separate steps with explicit exit-code echoes; no heredocs inside
conditional chains; every "green" claim in a reply must correspond to an echoed exit code.

## v3.1 step 1 (input-spec branch) — two records
(1) DISCOVERY, credit to gate T18: v1 engine results are order-sensitive to config mappings
(sort_keys round-trip flips solstice 0ff7ac65dd0b -> b187771ff064 with zero semantic change).
Store now preserves insertion order verbatim; order-canonicalization deferred as a documented
decision since it would re-freeze goldens. ENGINE_SPEC §12 states the determinism scope.
(2) PROCESS SLIP, recurrence of the PC-25b class: step-1 commit was created unconditionally
after a red T18 (chain used echoed exits but no conditional). Standing rule reaffirmed and
this fix lands by amending that commit only after green gates, run as separate steps.
