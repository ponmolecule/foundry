# FLOOR_LEDGER — conformance to docs/FLOOR.md
**Generated 2026-07-16 against build 9aa3710 · statuses: SAT (satisfied, with evidence) · PART (partially) · OPEN (not built) · DEF (documented deferral per PRODUCT_ONTOLOGY)**
**Rule of use: an OPEN row is a build-queue item; a DEF row must cite its fence; nothing exits this ledger silently.**

| F | Origin | Status | Evidence / gap |
|---|---|---|---|
| F-001 | P | PART | Wizard S1 captures client/regulator/date; engagement id + prepared-by + version echo on outputs incomplete |
| F-002 | P | PART | Taxonomy picker + product presence = derived activation (satisfies D-P13 in spirit); Patrick's 24-toggle surface represented by product/module presence — documented equivalence needed |
| F-003 | P | PART | REG_PARAMS carries CBLR; full five-threshold set with citations not yet enumerated |
| F-004 | both | SAT | $000s throughout; declared |
| F-005 | R | SAT | Config-as-JSON, engagement store, FIW round-trip, Prairie load pattern (D-R1 fixed) |
| F-010 | P | SAT | Pre-opening phase (quarterly-converted; T37) |
| F-011 | P | PART | Quarterly canonical index SAT; annual=Σquarters check exists in gates, not surfaced; inline year-rollup presentation absent |
| F-012 | P | PART | Quarterly native (D-P17 moot); annual/quarterly VIEW toggle absent |
| F-013 | both | PART | 12Q default SAT; Patrick's inline annual presentation OPEN |
| F-020 | P | SAT | Category expense schedule, sidebar-edited, Examiner Book display (T37) |
| F-021 | P | SAT | Cushion vs min Day-1, SUFFICIENT/INSUFFICIENT flag in results + display (T37d/e) |
| F-022 | P | SAT | Burn expensed into opening RETAINED deficit, both engines; waterfall seeds the asset side (T37a-c) |
| F-030 | R | SAT | Products→lines, per-line aggregation (RC/RC-E builders tie-checked) |
| F-031 | P | PART | Roman's 5 loan + 3 deposit lines shipped; brokered/sweep/institutional deposit types absent (D-R9) |
| F-032 | P | OPEN | Insurance bucketing (<$250K/≥$250K) as assumption (D-P7 fix) |
| F-033 | R | PART | OBS notional+fees SAT; CCF mechanics OPEN (with F-091) |
| F-034 | R | SAT | Six presets + custom creation (parity) |
| F-035 | R | SAT | parseProduct defaults + disclosure log (parity) + defaults-provenance ledger (TEST_CASES #10) |
| F-036 | P | OPEN | Payments product module (per-tx fee/cost, real volumes) — D-P11 fix |
| F-040 | R | SAT | fixed/float, index+spread (parity) |
| F-041 | R | SAT | Editable SOFR path, FOMC SEP sourced, longer-run glide (parity); products consume it (D-P2 fixed by architecture) |
| F-042 | both | SAT | Average-balance accrual (parity) |
| F-050 | both | SAT | Rollforward floored at zero (parity) |
| F-051 | both | SAT | ALLL + provision=ΔALLL+NCO, AC-only (parity) |
| F-052 | P | OPEN | AFS/HTM split + AOCI line (D-R6) |
| F-053 | P | OPEN | Depreciation schedule (D-R7); other-assets base statement |
| F-054 | R | SAT | OTS warehouse, holdQtrs, half-quarter conventions, AC/FVO GOS timing, HFS no-ALLL (parity; HFS memoranda convention disclosed in schedules) |
| F-055 | R | SAT | MSR full mechanics (parity) |
| F-056 | R | SAT | FVO DCF, day-one to opening RE, FV P&L routing (parity) |
| F-060 | both | SAT | Deposit rollforward; no decorative maturity inputs exist (D-P9 satisfied by absence) |
| F-061 | P | OPEN | Borrowings as scheduled instruments (D-P12); waterfall borrowings are overnight-residual only |
| F-062 | R | SAT | Cash-floor plug + fixed-point simultaneity (parity) |
| F-063 | both | SAT | Static other-liab, disclosed |
| F-070 | both | PART | Generic fee terms SAT; named module set (interchange/BaaS/trust/service) with growth drivers OPEN (D-P10 fix) |
| F-071 | P | OPEN | NIE category granularity + FTE step model (D-R8) |
| F-072 | P | OPEN | FDIC (correct base) + OCC assessments (D-P14 fix) |
| F-073 | R | SAT | Product opex vs corporate overhead split (parity) |
| F-080 | R | SAT | NOL tax engine, DTA disclosed (parity; D-P3 fixed) |
| F-081 | P | PART | RE tracked; common/surplus/AOCI component split OPEN (needs F-052) |
| F-082 | P | SAT | Staged raises, true quarter mapping, both engines, FIW carry (D-P8 fixed) — T34/T35 |
| F-090 | both | PART | Leverage on averages per Roman (D-P5 avoided); CBLR 9%/8% two-tier reachable branches via REG_PARAMS OPEN |
| F-091 | P | OPEN | Standardized RWA + four ratios + Tier2 cap (D-P6 fix); RC-R currently labeled proxy |
| F-092 | R | SAT | 12 CFR 3.22(d) MSA threshold deduction (parity) |
| F-093 | R | SAT | CBLR eligibility guards OBS>25%, $10B (parity flags) |
| F-094 | R | SAT | Capital shortfall estimator w/ stated approximations (parity) |
| F-095 | R | SAT | Non-modeled deduction notes carried (parity methodology) |
| F-100 | P | OPEN | CONC panel: full 10-ratio concentration/diagnostic set with REG_PARAMS thresholds (incl. real C&D input — D-P16b) |
| F-110 | R | SAT | Stress = full re-runs, credit/rate/combined + four overlays (parity); Patrick's S1/S2 annual presentation shape OPEN (PART overall) |
| F-111 | R | SAT | Breach callouts, matrices, stressed-out-earns-base honesty flag, calibration provenance (parity) |
| F-112 | P | OPEN | SENS-style one-variable low/base/high sensitivity |
| F-120 | P | OPEN | In-app CHECKS panel surfacing named assertions + master status (gates exist off-app; D-R15) |
| F-121 | R | PART | Roman's full flag catalog in examiner voice SAT (parity); bands recomputed from live CharterIQ percentiles, dated+cited, OPEN — the 85/15 centerpiece (D-R12) |
| F-122 | both | PART | Integrity (gates) and viability (flags) both exist; the two-class distinction not surfaced in-app pending F-120 |
| F-130 | R | SAT | FTP toggle, mismatch center, presentation-only memo (parity) |
| F-131 | R | SAT | Product Detail contribution view (parity) |
| F-132 | P | PART | Overview tab exists; Patrick's 8-metric x 3-year quick-stats shape + CBLR-aware capital metric OPEN |
| F-133 | both | PART | Roman's 6-sheet export SAT (parity); Call-Report-named schedule EXPORT (beyond on-screen Examiner Book) OPEN |
| F-134 | R | SAT | Zero suppression (parity + schedules omission convention) |
| F-135 | R | SAT | Methodology prose (parity) + BUILD_NOTES/ENGINE_SPEC/TEST_CASES lineage |
| F-136 | R | SAT | Debounced live recompute, badge update, input preservation (parity) |
| F-140 | P | DEF | BHC — pilot fence per PRODUCT_ONTOLOGY (Patrick's own stub-not-build) |
| F-141 | P | OPEN | Trust as a real fee module w/ AUM growth (fixes D-P13) — BUILD per 2026-07-16 floor-overrides-ontology ruling |
| F-142 | P | OPEN | Interchange detail (count x ticket x network split − network fees) |
| F-143 | P | OPEN | BaaS module — BUILD per 2026-07-16 floor-overrides-ontology ruling (ontology fence lifted) |
| F-144 | P | SAT | Mortgage banking pipeline→HFS→GOS satisfied by F-054/055; mapped explicitly here |
| F-145 | P | PART | Card engine M4 config depth (utilization/rewards) beyond shipped revolving mechanics |
| F-146 | P | SAT | Peer benchmark superseded by live substrate (placement + corridor + retrodiction); his paste-in zone is the before picture |

**Scoreboard: 32 SAT · 13 PART · 18 OPEN · 1 DEF. Ruling 2026-07-16: floor overrides ontology.**
**Defect coverage en route:** D-P3/5/8/9/13(spirit)/17 fixed or moot; D-R1/12(partial) fixed; D-P1 fixed by architecture (stress = re-runs). Remaining defects ride their F-rows.
