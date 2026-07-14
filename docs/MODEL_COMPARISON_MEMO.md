# Three Models, One Problem — Patrick × Foundry × Roman (one-page memo)

**Bottom line.** The three artifacts are complementary thirds of the same product: Roman's
model contributed the *instrument mechanics*, Patrick's model specifies the *application
lifecycle and regulatory presentation*, and Foundry is the *engine and governance layer*
that makes both reproducible, evidenced, and multi-client. Nothing conflicts with Foundry's
architecture; Patrick's model adds a roadmap (monthly/pre-open cadence, staged capital) and
a vocabulary (Call Report tab shapes) worth adopting. No rebuild is implied.

| Dimension | **Patrick v1.0** (Excel/Sheets template) | **Foundry v3** (engine + workspace) | **Roman** (HTML/JS modeler) |
|---|---|---|---|
| Object | Client-facing template, formula-live | Deterministic engine of record + API + UI ladder (v2/v2.1/v3) | Single-file browser calculator |
| Horizon / cadence | 3y **monthly** + **12-mo pre-opening**, quarterly/annual rollups | 12 quarters (monthly+pre-open = roadmap via input dialect) | 12 quarters |
| Lifecycle | Pre-open expenses, **3-round capital staging**, Day-1 seeds | Engagement sequence −1..10 as data; opening capital only (staging = roadmap) | None |
| Product mechanics | Balance rollforwards; fee modules; **stubs**: mortgage banking, cards, BaaS, trust | OTS + MSR (3.22(d)), FV election (ASC 825), warehouse, GOS, FTP view, per-quarter overrides | **Deepest**: MSR, FVO/DCF, OTS, stress overlays, FTP |
| Tax | **`=0` placeholder** | NOL carryforward, no-DTA (conservative; Tier-1-exact) | Same NOL convention (donor) |
| Capital | CBLR (**8%** named range) + standardized/RWA section; AOCI opt-out; staged raises | CBLR per versioned cited REG_PARAMS + grace machine + derivation/chart/grid; RWA = pilot scope | Leverage vs 9%-era floor; MSA deduction |
| Reg calibration | Scattered literals — **internally inconsistent** (8% range vs "9%" check text) | **Versioned, cited, gate-enforced** (2026.07.a) | Hardcoded, stale |
| Validation | 10-check panel + master status (open-time) | **39 protocol/parity gates on every commit**; ±$1k/line/qtr fixtures; jsdom UI probes | 44-test harness (build-time, not shipped) |
| Peers | **Paste-in stub**, no source/vintage/cohort defn | Pre-registered bounded-radius cohorts, kernel priors, insufficiency machinery, PEER/COUPLED flags, governance rulings drafted; synthetic data watermarked pending CharterIQ extract | Hardcoded range bands |
| Provenance | None (file state) | **SHA-256 config/run hashes, freeze → re-verify registry** | None |
| Multi-client | Fork the file | One chassis, config front door, T6 no-drift guarantee; roster pending volume | None |
| Stress | Stub (labels only) | Scenario engine w/ dials, per-scenario constraint tests, capital shortfall | Four scenarios, calibrated overlays |
| Schedules | **RC/RI/RC-C/RC-R/DEP/ABR/CONC shapes** — the target dialect | Call Report line mapping on every row; schedule *output* = pilot scope (Patrick's worksheets in hand) | Line-labeled statements |
| Examiner surface | Concentration brackets in labels | Overview flags (coded), examiner book w/ proposed responses, caveat register | 21 inline warnings |
| Ceiling (by its own structure) | Peers pasted, tax =0, stubs await "V2" | Real peer **data** pending extract; monthly/pre-open pending; RWA pending | Every threshold a literal; no source, date, or peer defn |

**Adopt from Patrick (proposed):** monthly/pre-open input dialect → quarterly engine now,
native time-basis later; staged capital events; ABR schedule; CONC diagnostics under
REG_PARAMS; FDIC/OCC assessment lines; his tab shapes as the schedule-output dialect.
**Demo-day geometry:** confirm his framing (his toggles=our modules, his checks=our gates),
then exceed his ceilings with what a spreadsheet cannot do — sourced peers, versioned
regulatory values, hash-verified reproducibility, one chassis for every client.
