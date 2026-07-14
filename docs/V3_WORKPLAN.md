# Foundry v3 Work Plan — Influences Integrated (v1, 2026-07-14)

Companion to PROJECT_PLAN.md (the check-off sheet). This is the reasoning and the granularity.
Influences integrated: Roman's engine (already the spine), Patrick's workbook (lifecycle +
presentation), the parallel-build capital tab (adopted PC-25/26), governance rulings (drafted),
pilot calendar (Jul 24 / Jul 29 / Aug 11).

---

## Part I — CharterIQ substrate surgery: where Foundry needs it, and whether it blocks

| # | Foundry consumer | Needs from substrate | Needed by | Fallback until then | Blocked? |
|---|---|---|---|---|---|
| I-1 | Peer cohort real data (watermark retirement) | De novo trajectory extract per PEER_EXTRACT_SPEC v1.0→1.1 | Aug window (post-checkpoint) | Synthetic 43-bank fixture, watermarked | **No** |
| I-2 | UBPR peer-group baseline (Ruling 4 fallback) | UBPR PG assignment + PG distribution stats | With I-1 | Omit; rulings not yet ratified | **No** |
| I-3 | Retrodiction overlay v0 (C-track) | 2–3 real de novo Call Report histories | Jul 29 | **Direct FFIEC CDR pull** (raw filings suffice; surgery irrelevant) | **No** |
| I-4 | Live benchmark strip for warnings (pilot scope) | Percentile service or extract refresh | Aug 11 phase | Synthetic percentiles, watermarked | **No** |
| I-5 | Patrick PEER-tab shapes populated with real figures | Same as I-1/I-2 | Post-pilot | Populate from synthetic w/ watermark for demo | **No** |

**Verdict: the surgery does not hold us up.** Every Jul-24 and Jul-29 deliverable runs on the
engine plus synthetic-watermarked evidence or direct FFIEC pulls. The substrate becomes
load-bearing only at watermark retirement (D-track), which is deliberately post-checkpoint.

**The one real coupling risk runs the other direction:** if the surgery optimizes the new
schema for current-state analytics and drops what the extract needs, D-track gets harder.
**Action I-A (P, this week): hand the substrate workstream a requirements memo** — the new
schema must preserve: (1) full quarterly history to 2010, not just latest quarter; (2)
charter/established dates; (3) terminal status + date (failed-list & structure-change joins);
(4) SOD office counts by year; (5) UBPR peer-group assignment; (6) an extract-job path that
can emit PEER_EXTRACT_SPEC's two tables + manifest. Six bullets; the spec is the contract;
peers.py stays the only seam.

---

## Part II — What Patrick's model teaches, and the translation of each lesson

| # | Lesson (from the artifact itself) | Translates into Foundry as |
|---|---|---|
| II-1 | **Applications live in calendar months** — monthly cadence, dated events, a start month | Now: monthly→quarterly input dialect in the intake translator (documented ×3 / expand-by-4). Later: native monthly + calendar-anchored time basis (E-track, gated engine change) |
| II-2 | **The model starts before the bank does** — pre-opening expense schedule, application fees, Day-1 seeds, min Day-1 capital check | `pre_open` config block; opening equity derived = raises − cumulative pre-open burn; Day-1 seed balances; a PRE-OPEN readiness check on Overview |
| II-3 | **Capital arrives in tranches** | Staged capital-raise events in the equity rollforward (engine additive) |
| II-4 | **The deliverable's shape is the regulator's shape** — RC/RI/RC-C/RC-R tabs, ABR, CONC | Schedule-output dialect = his tab shapes (worksheets in hand); ABR tab; CONC diagnostics under REG_PARAMS |
| II-5 | **Cost realism has a vocabulary** — FTE×comp, named lines, asset-indexed FDIC/OCC assessments | Structured NIE module replacing/augmenting abstract overhead |
| II-6 | **Fee businesses are per-account / per-transaction** — and his own doctrine says take them flat monthly for v1 | Translator: net $ fee lines now; native per-account/per-tx fields later (Solstice dialect kin) |
| II-7 | **One control surface, banker-legible** — CONTROL panel idiom | Configuration tab absorbs it: identity block, cadence, engaged-modules view |
| II-8 | **RWA as simple assumption buckets** | The 5-bucket weight table is the pilot RWA stack's input shape |
| II-9 | **Balance-driven core validated** — his dialect ≈ ours | The 85% is empirical: ~90% of his 165 inputs map to existing config fields via unit conversion |
| II-10 | **Anti-lessons** — scattered literals, zero-wire toggles, hidden-tab stubs, file-state | Already answered by REG_PARAMS, T6-gated modules, registry/roster. Do not import. |

---

## Part III — Three-bucket inventory (granular)

### A. Have and good — keep, showcase (no work except demo framing)
A1 Deterministic engine of record; SHA-256 config/run hashes. A2 39-gate suite; 9 frozen
fixtures ±$1k/line/qtr; jsdom UI probes. A3 Freeze→re-verify registry (the live REPRODUCED
demo). A4 Config front door: JSON + banker workbook, fail-closed both ways. A5 Per-quarter
override grids (strictly supersets Patrick's flat scalars). A6 Product mechanics: MSR w/
3.22(d), FV election, OTS, warehouse, GOS, FTP view. A7 Stress engine: dials, per-scenario
constraint tests, capital-shortfall estimate. A8 Challenge layer: reasonableness + COUPLED
structural/percentile + PEER flags. A9 Peer methodology: pre-registered, kernel-weighted,
insufficiency machinery + rulings draft. A10 Examiner book. A11 REG_PARAMS versioned+cited +
pending-rule watch (gate-enforced). A12 Caveat register. A13 Call Report line mapping on
every row. A14 Capital derivation reconciled ≤2bp to engine. A15 Ladder (v2/v2.1/v3 intact).
A16 Gated API + /docs.

### B. Patrick has, we don't — adopt (size S/M/L · target · notes)
| ID | Item | Size | Target | Notes |
|---|---|---|---|---|
| B-1 | Monthly-input dialect (flat $/mo originations & deposit adds; annual-step rates) | M | **Jul 24** | Translator-level: ×3 to quarterly $, $-adds→growth via override grids, rate steps→quarterly path; every mapping written into the config |
| B-2 | Pre-opening phase (expense schedule, app fees, Day-1 seeds, min-capital check) | M | Jul 24 lite / Jul 29 full | Lite: opening capital net of documented pre-open burn + seeds. Full: `pre_open` block + Overview check |
| B-3 | Staged capital raises (3 dated rounds) | M | **Jul 29** | Equity events at quarter t; fixture + gate; enables "raise round 2 in Q6" answers |
| B-4 | RWA / standardized stack (5 weight buckets → CET1/T1/Total/PCA, RC-R shape) | M-L | **Jul 29** | Pilot scope; per-product bucket tags in config; PCA ladder from REG_PARAMS |
| B-5 | ABR schedule (avg balances & rates, UBPR-style) | S | Jul 29 | All series already computed; new white tab |
| B-6 | CONC diagnostics (CRE/TRBC, C&I, brokered, LTD) | S-M | Jul 29 | Ratios + thresholds into REG_PARAMS w/ sources; flags on breach |
| B-7 | Structured NIE (FTE×comp by year; named lines; FDIC/OCC asset-indexed assessments) | M | Jul 29 subset (assessments) / Aug (full) | Engine additive expense lines |
| B-8 | Per-account / per-tx fee vocabulary (5 rails, BaaS, service charges, trust) | S now / M native | Jul 24 (as net $ via translator) / Aug (native) | His own flat-monthly doctrine blesses the interim |
| B-9 | Schedule output in his tab shapes — RC + RI first | M | **Jul 24** | Patrick's worksheets are the row map; RC-R rides B-4; RC-E after |
| B-10 | Identity/engagement metadata block (client, engagement ID, preparer, version) | S | Jul 24 | Config fields + Configuration tab header |
| B-11 | Deposit maturity structure (CD ladders) | M | **Decision Aug 11** | ALM realism vs scope; caveat until decided |
| B-12 | AOCI / AFS modeling | L | **Decision Aug 11** | Caveat-registered today; interacts with B-4 (AOCI opt-out) |
| B-13 | BHC double-leverage view | — | Parking lot | Stub even for Patrick |

### C. Have, but tweak per Patrick (granular)
| ID | Tweak | Size | Target |
|---|---|---|---|
| C-1 | Configuration tab absorbs CONTROL idiom: identity block (B-10), cadence line, **engaged-modules view** (which Tier-2 modules this config activates — our honest version of his toggles) | S-M | Jul 24 |
| C-2 | Ratios tab gains ABR framing (or ABR ships as its own tab per B-5; pick one, not both) | S | Jul 29 |
| C-3 | Fee inputs: expose simple flat-$/quarter fee path alongside %-of-balance (his doctrine as a first-class input, not just a translator artifact) | S | Jul 29 |
| C-4 | Rate sidebar: accept annual-step entry that expands to the quarterly path (input convenience, engine unchanged) | S | Jul 29 |
| C-5 | Opening balance seeds: Day-1 cash/premises/other-assets as explicit config fields (ties B-2) | S | Jul 24 lite |
| C-6 | Caveat register cross-linked from Configuration (scope visible where the client looks) | S | Jul 29 |
| C-7 | Demo config: keep canonical OTS+MSR, add a "Patrick-translated" second resident for the roster (the ultimate B-1 test artifact) | S | Jul 24 |

---

## Part IV — Sequenced build (merges into PROJECT_PLAN tracks)

**Sprint 1 → Jul 24 demo (track B).** Order: B-10/C-5 (config fields) → B-1 translator
(Patrick workbook → config; monthly dialect; fee-net conversion; B-2 lite pre-open netting)
→ C-1 Configuration/CONTROL idiom → B-9 RC+RI schedule shapes → completion/gap flags
(no-loans conversation) → Prairie translation (existing plan) → roster v0 (needs volume) →
demo dry-run script built on the seven contrasts (PEER, tax, SENS, MORT, CHECKS/re-verify,
no-loans open, CBLR-drift reserve). Gate rule unchanged: every box lands with a green run.

**Sprint 2 → Jul 29 checkpoint (track C).** B-4 RWA/PCA → B-3 staged raises → B-5 ABR →
B-6 CONC → B-7 assessments subset → C-2/C-3/C-4/C-6 tweaks → retrodiction v0 (I-3 via
direct FFIEC pull) → hardening for the unsupervised window.

**Sprint 3 → Aug window / Aug 11 (tracks D/E).** Substrate integration on the surgery's
timeline (extract load at peers.py, real freeze event, watermark retirement, UBPR baseline)
→ rulings ratification → native monthly/pre-open engine decision → DTA/valuation-allowance
layer (spec already four items: 80% cap, temp-diff DTA w/ 25% threshold, VA release, state
parameterization) → B-11/B-12 decisions.

**Standing dependencies:** Railway volume (roster, durable registry) — P, this week.
Substrate requirements memo (I-A) — P, this week. Patrick workbook go — **given by this plan.**
