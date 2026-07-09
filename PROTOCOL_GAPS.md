# PROTOCOL GAPS

## v2 P0 state (2026-07-08)
- T-PAR is GREEN (PA-1): 9/9 fixtures reproduced within ±$1k/line/quarter by
  foundry/v2 (quarterly balance-driven engines, profiles pf_a/pf_b). tests_protocol
  remains the v1 release gate (27/27); the v2 package imports nothing into v1.
- v2 open items: HTM shock-invariance unit test pending PB rate-scenario work (A.6 partial);
  overrides/FV/tax-semantics/quarterly conventions delivered as parity-mode embryos,
  chassis-native forms due in PB (B.3-B.6).
- Known validate/run seam (step_0a etc.) scheduled for PA item A.13.

## PA-2 (2026-07-09)
- A.13 delivered both sides: v2 fail-closed validator (validate_q, wired ahead of every
  parity run, negative controls in T-PAR) and the v1 validate/run seam closed
  (TOP_REQUIRED extended; T16 guards it; harness now 29/29).
- A.7 delivered: ratio layer with MSR threshold deduction + intangibles, attested
  against predecessor ratios within 0.02pp inside T-PAR.
- A.9 re-phased to PB per reconciliation note (results-dict change moves run hashes).

## PA-3 / PA-4 (2026-07-09)
- A.11/A.12 delivered: v2 challenge layer (two-sided bands, pricing/funding/OTS checks,
  blended-spread viability, COUPLED-01/02). Attested finding: COUPLED-01 fires on the
  default preset plan (13%/q deposit growth priced ~185bp below market) — deliberate,
  mirrors the Solstice precedent; review burden, not a noise gate.
- A.4 attested (OBS notional path + fee accrual). A.14/A.15 delivered: v2 config
  workbook round-trips to identical parity output for all 9 fixtures; results workbook
  ties cell-for-cell to engine output with the canonical config hash on the cover.
- Phase A remaining: A.6 shock-invariance unit (PB rate work), A.8 constraint-tests
  surface for v2 (lands with the run wrapper in PC/API), A.9 (re-phased to PB).

## PB-1 (2026-07-09) — engine 0.3.0
- B.1/B.2/B.3 delivered hash-neutral (goldens v4/v1 reproduced bit-identically before
  the deliberate A.9 change; that verification doubles as the B.8 promotion attestation).
- A.9 delivered (reverse_stress.capital, exact solve) — the one deliberate hash move;
  goldens re-frozen v5/v2 with explained diff in PROTOCOL_RUN_REPORT.
- A.6 completed (securities books in profile A; HTM shock-invariance attested, bookInt
  reported as its own line). B.7 delivered (Call Report mapping; exhibit carries codes;
  completeness checked across all fixtures). B.5/B.6 documented in ENGINE_SPEC §13.
- Remaining before PC: A.8 (constraint-tests surface for v2 — lands with the run
  wrapper), B.4 monthly-chassis FV explicitly deferred per reconciliation note.

## PC-1 (2026-07-09) — the console phase
- C.1/C.2 delivered: /api/v2/preview calls run_v2 exactly (preview IS the run, T-PRV
  attested); invalid configs return structured 422 errors, rendered by the workspace
  as answerable prompts (C.4). A.8 delivered inside run_v2: every constraint evaluated
  in every scenario with sources.
- C.3-C.9, C.11: web/console_v2.html — thin client, zero browser arithmetic (numbers
  arrive from the engine; the page formats). Composer, override grid, statements with
  Call Report codes, ratios, stress + constraint tests, FTP contribution reconciling
  exactly to pre-tax, freeze-scenario returning canonical hashes, exhibit download.
- C.12: T17 provenance gate in the protocol harness (30/30) — and it earned its keep
  immediately by catching fixture-inherited wording in the embedded template.
- Sandbox retired: /sandbox now 307-redirects to /v2. If the interim sandbox patch was
  applied earlier, delete web/sandbox.html on pull (instruction in DELIVERY.md).
- Engineering note for the record: two intended edits to app.py and web/index.html
  silently no-opped because their anchor text had been stashed at P0; caught by the
  HTTP smoke test, fixed by appending anchored on verified content. Lesson kept:
  every replace is now followed by a verification read.
- v2 run hashes have no golden freeze yet (no registered v2 clients); first frozen
  v2 engagement should be accompanied by a goldens entry.

## PC-2 hotfix (2026-07-09) — Windows encoding
Field report from first Windows deployment: T-PAR integrity failed on exactly the
four pf_b fixtures. Root cause: text-mode open() without encoding uses the locale
codec (cp1252 on Windows), which mangles the en dash in predecessor-B product names
before hashing; reproduced deliberately via cp1252 decode. Fix: encoding="utf-8"
declared on every text read/write in tests_parity, tests_protocol (T16), and the
v2 API routes. Also corrected stale T2 label text (said v4/v1 while correctly
comparing v5/v2). No arithmetic touched; run hashes unchanged.
