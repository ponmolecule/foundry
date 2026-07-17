# ARCHITECTURE INDEX — which document governs what
*The one-page conscience. Before building, find your decision's jurisdiction below;
if two documents disagree, the more specific one wins and the conflict gets logged here.*

| Deciding about... | Governing document | Enforced by |
|---|---|---|
| Input surfaces, wizard, FIW, modes, typed-value budget | **INPUT_SPEC.md** (P1–P7; §7 FIW blueprint; §8 bridge ruling) | T17, T19, T21 |
| What products exist / can exist / are refused | **PRODUCT_ONTOLOGY.md** (14 mechanics; four-outcome rule) | taxonomy + fieldlib |
| Client-forecast import (Mode T) | **TRANSLATION_PIPELINE.md** (shapes S1–S4; stages 0–5; refusals) | T-series gates as built |
| Any field appearing, moving, or dying | **INPUT_CONCORDANCE.md** + **APP_TO_PATRICK_MAP.md** ("nobody's orphan") | T19a/b closure |
| Scope buckets, substrate dependencies | **V3_WORKPLAN.md** | — |
| Engine conventions, determinism, quarterly-forever | **ENGINE_SPEC.md §12**, BUILD_NOTES.md | tests_protocol core |
| Dialect bridge (drivers → workspace) | **INPUT_SPEC.md §8** + foundry/bridge.py docstring | T20 |
| Peer benchmark governance | **PEER_GOVERNANCE_RULINGS.md** — **DRAFT, unratified** | pending |
| Regulatory parameters, pending rules | foundry/v2/regparams.py PENDING_RULES (annotate, never encode) | parity gate |
| Strategic frame for the engagement | MODEL_COMPARISON_MEMO.md, PROJECT_PLAN.md | — |
| CharterIQ data window/fields | SUBSTRATE_DATA_BRIEF.md | — |

**The two T-families (do not conflate):** `Stage T-n` (hyphenated) = Mode T build
stages, laid out in TRANSLATION_PIPELINE.md. `Gate Tnn` (no hyphen) = named checks in
the protocol suite, catalogued in **GATE_LEDGER.md** (generated from the suite itself).

**Standing rulings not in any single doc** (logged here so they have an address):
engine QUARTERLY permanently; ALL calendar deadlines dropped — gates are the schedule;
surface text written for the client (no schema/JSON/env vars/source names); attached
file = artifact of record, checked before use; commit only after gates AND live-HTTP
verification for anything touching app.py or interactive UI; baked exhibits are
storyboards only (static, flattened controls); new bakes get new hash-stamped names;
classification is a fact, not a menu; user-defined products are editable (pins are
for imports); Add Product is the single door; build actions on the canvas, analytics
settings in the sidebar with their family.

## Ruling 2026-07-16: FLOOR overrides ONTOLOGY
Where docs/FLOOR.md and docs/PRODUCT_ONTOLOGY.md conflict, the FLOOR wins. The ontology's phase-2 fences no longer gate floor items (F-141 Trust and F-143 BaaS move to the build queue; F-140 BHC keeps its deferral under the floor's own clause and Patrick's stub-not-build call).
