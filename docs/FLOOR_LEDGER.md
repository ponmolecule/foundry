# FLOOR_LEDGER — conformance to docs/FLOOR.md
**Generated 2026-07-16 against build 9aa3710 · statuses: SAT (satisfied, with evidence) · PART (partially) · OPEN (not built) · DEF (documented deferral per PRODUCT_ONTOLOGY)**
**Rule of use: an OPEN row is a build-queue item; a DEF row must cite its fence; nothing exits this ledger silently.**

| F | Origin | Status | Evidence / gap |
|---|---|---|---|
| F-001 | P | PART | Wizard S1 captures client/regulator/date; engagement id + prepared-by + version echo on outputs incomplete |
| F-002 | P | SAT | Configuration tab is the master surface: 13 module lamps DERIVED from presence (D-P13 fixed for real), structural editors (pre-open, raises, borrowings, books, NIE, fees) live there; sidebar = iteration knobs only (user design ruling 2026-07-16) |
| F-003 | P | SAT | Full PCA well-cap set (CET1 6.5/T1 8/Total 10/Lev 5) + CBLR tiering in REG_PARAMS with 12 CFR citations; floor's 9/8 CBLR reconciled to the Apr 2026 final rule 8/7 (91 FR 22973) per the registry doctrine (T41a/d) |
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
| F-033 | R | SAT | OBS enters RWA at the 12 CFR 324.33 default 50% CCF; per-exposure maturity CCFs registered (20%/50%), applied when maturities exist — disclosed (T41) |
| F-034 | R | SAT | Six presets + custom creation (parity) |
| F-035 | R | SAT | parseProduct defaults + disclosure log (parity) + defaults-provenance ledger (TEST_CASES #10) |
| F-036 | P | SAT | Payment rails with real volumes + growth, fee income and rail costs both booked (D-P11 fixed; T44b) |
| F-040 | R | SAT | fixed/float, index+spread (parity) |
| F-041 | R | SAT | Editable SOFR path, FOMC SEP sourced, longer-run glide (parity); products consume it (D-P2 fixed by architecture) |
| F-042 | both | SAT | Average-balance accrual (parity) |
| F-050 | both | SAT | Rollforward floored at zero (parity) |
| F-051 | both | SAT | ALLL + provision=ΔALLL+NCO, AC-only (parity) |
| F-052 | P | SAT | Designated AFS/HTM books (both engines, HTM shock-immune per prior gate), AOCI = AFS x sens/4 accumulating into equity, BS tab + RC 2.a/2.b/26.b rows, sidebar editors (T38) |
| F-053 | P | SAT | Straight-line premises depreciation, expense in NIE, floored at zero, both engines; RC 6 from the live series (T39). Other-assets base: flat config value, disclosed |
| F-054 | R | SAT | OTS warehouse, holdQtrs, half-quarter conventions, AC/FVO GOS timing, HFS no-ALLL (parity; HFS memoranda convention disclosed in schedules) |
| F-055 | R | SAT | MSR full mechanics (parity) |
| F-056 | R | SAT | FVO DCF, day-one to opening RE, FV P&L routing (parity) |
| F-060 | both | SAT | Deposit rollforward; no decorative maturity inputs exist (D-P9 satisfied by absence) |
| F-061 | P | SAT | Scheduled draws (name/quarter/amount/rate/term), straight-line amortization, avg-balance interest, funding-side in the plug, both engines; RC 16 combines residual + scheduled (T40); D-P12 fixed |
| F-062 | R | SAT | Cash-floor plug + fixed-point simultaneity (parity) |
| F-063 | both | SAT | Static other-liab, disclosed |
| F-070 | both | SAT | Named fee modules — interchange, payments, service charges, trust, BaaS, GOS(products) — every one growth-capable (D-P10 fixed; T44a/c) |
| F-071 | P | SAT | nie_detail: FTE-step comp (per-year steps gate-checked), category lines, Patrick's sub×r/(1−r) gross-up kept verbatim; both engines (T43a) |
| F-072 | P | SAT | FDIC on avg consolidated assets − avg tangible equity (12 USC 1817(b)(2)(A)) + OCC on assets, rates in REG_PARAMS w/ citations, hand-checked to the penny (T43c; D-P14 fixed) |
| F-073 | R | SAT | Product opex vs corporate overhead split (parity) |
| F-080 | R | SAT | NOL tax engine, DTA disclosed (parity; D-P3 fixed) |
| F-081 | P | SAT | Equity = paid-in + retained + AOCI, tie-gated to zero every quarter, both engines; RC 23/24 + 26.a + 26.b tie to 27.a (T38b/g) |
| F-082 | P | SAT | Staged raises, true quarter mapping, both engines, FIW carry (D-P8 fixed) — T34/T35 |
| F-090 | both | SAT | CBLR tiering with reachable branches (meets / grace 7% floor / below), election honored, leverage on averages MSA-deducted; 2026 calibration governs with the reconciliation note (T41d/g; D-P4/5 fixed) |
| F-091 | P | SAT | Standardized RWA (0/20/50/100/150/250 weights incl bank-exposure share of cash — D-P6 fixed), CET1/T1/T2 (ALLL capped 1.25% RWA)/Total, four ratios vs PCA thresholds, AOCI opt-out honored; RC-R Part II real rows; white-tab section (T41a-c, T31f) |
| F-092 | R | SAT | 12 CFR 3.22(d) MSA threshold deduction (parity) |
| F-093 | R | SAT | CBLR eligibility guards OBS>25%, $10B (parity flags) |
| F-094 | R | SAT | Capital shortfall estimator w/ stated approximations (parity) |
| F-095 | R | SAT | Non-modeled deduction notes carried (parity methodology) |
| F-100 | P | SAT | Nine-ratio CONC panel (CRE/RBC 300, C&D/RBC 100 w/ real input honored, C&I mix, consumer mix, LLL 15%, wholesale, non-core, LTD band, burden); missing inputs STATED never zero-filled (D-P16b); severe breaches flag on Overview (T41e/f) |
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
| F-141 | P | SAT | Trust: AUM rollforward w/ growth, avg-AUM bp fee; the activation lamp derives from module presence (T44a) |
| F-142 | P | SAT | Interchange: count × ticket × rate − network fees, growth path (T44a/c) |
| F-143 | P | SAT | BaaS: programs × accts/program × rev/acct/mo with growth (per the floor-overrides ruling) |
| F-144 | P | SAT | Mortgage banking pipeline→HFS→GOS satisfied by F-054/055; mapped explicitly here |
| F-145 | P | PART | Card engine M4 config depth (utilization/rewards) beyond shipped revolving mechanics |
| F-146 | P | SAT | Peer benchmark superseded by live substrate (placement + corridor + retrodiction); his paste-in zone is the before picture |

**Scoreboard: 49 SAT · 7 PART · 6 OPEN · 1 DEF. Ruling 2026-07-16: floor overrides ontology. Waves 1-3 closed (engine, regulatory, income granularity).**
**Defect coverage en route:** D-P3/5/8/9/13(spirit)/17 fixed or moot; D-R1/12(partial) fixed; D-P1 fixed by architecture (stress = re-runs). Remaining defects ride their F-rows.
