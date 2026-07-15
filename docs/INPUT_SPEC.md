# Foundry INPUT_SPEC v0.1 — Prescriptive
**July 15, 2026 · governs Tier-3 input acquisition for v3 · companion to PRODUCT_ONTOLOGY v1.3 and ENGINE_SPEC**
**Lineage rule honored: Roman (interactive, instant recompute) and Patrick (assumption-workbook discipline) weighted equally; both feed one canonical schema.**

---

## 1. Governing principles (normative)

P1. **One canonical schema, three entry modes.** All input modes serialize to the same Tier-3 config JSON (`config_schema_version` pinned; Prairie Digital golden case guards the load path). No mode has private fields.

P2. **Edit-by-exception.** The user asserts identity and strategy; behavior is defaulted. Every field carries `provenance ∈ {user, peer_default, engine_default}` and `reviewed: bool`. Flags fire on material *unreviewed* defaults — never on empty cells, because no required cell is ever empty.

P3. **Never ask what a resolver can derive.** RC mapping, risk-weight defaults, regulator identity (from charter type + state), tax rate (from state), capacity minutes, FTE counts — computed, shown, overrideable; never prompted.

P4. **Never ask what peers can default.** Rates, betas, attrition, ramps, NCOs, coverage ratios, fee schedules default from the selected peer archetype's cohort, cited (the PEER contrast made operational at input time).

P5. **Progressive disclosure.** A field exists in the UI/workbook only if an activated archetype requires it. `start_month` gates activation. Archetype validation rules (ontology §0, outcome 2) run at entry, not at run.

P6. **Typed-input budget (hard):** a two-product community bank plan must be expressible in **≤ 40 user-typed values**; a four-product plan in **≤ 70**. Budget violations are spec bugs.

P7. **Round-trip invariant.** Export-to-workbook → edit → import reproduces the identical config (hash-checked) when no cells changed. Extends the existing Excel round-trip guarantee to inputs.

---

## 2. The three entry modes

### Mode W — Wizard (in-app, Roman lineage)
Stepper: Institution → Capital → Archetype picker → per-archetype driver cards → review. Instant recompute on the review screen (Roman's core virtue preserved). Deviation panel per archetype collapses all defaulted assumptions behind one expander with provenance badges.

### Mode F — Foundry Input Workbook, FIW (generated Excel, Patrick lineage)
**The FIW is emitted per-engagement, never a static template.** Generation requires only Steps 1–3 of the wizard (institution, capital, archetype picks — ≤ 15 typed values). Emitted workbook:
- `CONTROL` — institution + capital fields (Patrick's tab, kept by name)
- `ASSM_<archetype>` — one sheet per activated archetype: driver fields (blank, bordered, required) above a defaults block (pre-filled, provenance-colored, editable)
- `LIMITS` — management-proposed and engagement constraints
- `README` — provenance legend, schema version, generation hash
Import validates against archetype rules; diffs against generation state; only touched cells become `provenance: user`.

### Mode T — Translation import (the demo thesis)
Client's own forecast (any workbook/CSV) uploads to a **mapping session**: user assigns client rows → archetypes/drivers; unmapped banking-layer requirements (funding, capital, deposit pricing) surface as conversational gap flags; Foundry completes the layer with peer defaults. Output: same canonical config + a `translation_log` (row → archetype → conversions applied, incl. monthly→quarterly per the standing conversion rule).

---

## 3. Canonical field schema (prescriptive)

### Tier A — Institution (asked once, 9 fields)
`institution_name` · `charter_type` (state-NM | state-M | national | thrift → regulator resolver) · `state_market` · `opening_date` (defines m0; engine remains quarterly, dates convert at import) · `pre_open_months` (default 12) · `capital_regime` (`cblr_election: bool`; validation against REG_PARAMS) · `peer_archetype` (one of the five cohorts → default source) · `de_novo_period_years` (default 3) · `tax_rate_override` (optional; default = resolver fed+state).

### Tier B — Capital & pre-opening (5 + repeats)
`initial_capital` · `org_costs_pre_open` · `pre_open_payroll_monthly` · `staged_raises[] {amount, month}` · reserved: `sub_debt[]` (activates with M11).

### Tier C — Archetype activations
`archetypes[] {archetype_id, start_month}`. Picker organized by the ontology's archetype list; picking one activates its Tier-D block, validation rules, RC mappings, and peer-evidence requirements.

### Tier D — Per-archetype driver block (4–6 typed fields each; the only per-product questions)
Every activated archetype asks exactly: **driver quantity** (headcount schedule | spend schedule | partner count), **productivity per driver** (accounts/originations per unit), **average size** (balance/loan), **pricing** (rate or index+spread), and where applicable **mix** (segment shares) and **sold/held election**. Illustrative:
- `funnel_deposit`: `marketing_spend_schedule`, `cac_or_conversion`, `avg_mature_balance`, `rate_or_beta_override?`
- `commercial_lending`: `lender_hiring_schedule`, `originations_per_lender_qtr`, `avg_loan_size`, `pricing`, `segment_mix{cre, ci, ...}`
- `revolving_credit`: `penetration_target`, `avg_balance`, `apr`, `interchange_override?`
Everything else in the archetype (attrition, ramp, NCO, coverage, ops minutes, fee terms) = defaults block, edit-by-exception.

### Tier E — Staffing, facilities, opex overlay
Defaulted from the capacity engine + peer opex ratios. User-typed only: `executive_comp_schedule` (optional), `premises_budget` (optional), `major_vendor_items[]` (optional, each with `start_month`).

### Tier F — Limits & scenarios
`management_limits{}` (e.g. CRE % of capital — engagement constraints, never conflated with REG_PARAMS) · scenario library runs from defaults; custom scenario = named multiplier set (M10 hooks).

---

## 4. Validation & provenance (normative)
V1. Archetype rules run at entry (e.g., partner-sourced deposits cannot silently inherit retail decay — ontology outcome 2).
V2. Import produces a **field-level provenance report**; the Overview flags tab consumes `unreviewed peer_default` items above materiality thresholds.
V3. FIW hash + `config_schema_version` recorded in the run manifest (joins the golden-hash discipline).
V4. Mode-T translation_log is a first-class artifact (Examiner Book appendix candidate).

---

## 5. Open decisions
1. Wizard Step-3 archetype picker taxonomy depth for the pilot (full ontology list vs. the ~10 archetypes the shipped mechanics cover).
2. Whether Mode T's mapping session ships for the 24th (a scripted version may suffice for the demo) — Mode W + F are lower risk.
3. Deviation-panel materiality thresholds (which unreviewed defaults flag).
4. Whether `LIMITS` also captures proposed regulator conditions (brokered %, growth caps) for CHECKS-style pass/fail — Patrick-lifecycle absorption item.

---

## 6. Implementation plan (appended per BUILD_BRIEF-v3.1, 2026-07-15)
Rung: `/v3.1`, branch `input-spec`. Engine: zero changes. v3 frozen for Jul 24; nothing
merges to main before the 24th. Build order, each step gated before the next:
1. `config_schema_version` pin in the engagement load path (fail-closed) + JSON engagement
   store at `$FOUNDRY_DATA_DIR/engagements/{slug}.json` (no DB). Gate: stored-then-loaded
   Solstice config reproduces its golden hash; version-tampered file refuses to load.
2. `/v3.1` route scaffold: v3 shell clone + config-source selector (goldens + engagements).
   Gate: goldens render identically on both rungs.
3. Wizard screens 1–3 (Institution 9 fields / Capital / Archetype picker w/ start_month),
   writing to the store; resolver values shown-not-asked with edit affordance.
4. FIW generator (openpyxl; reuse export styling): CONTROL + ASSM_<archetype> per
   activation + LIMITS + README w/ generation hash. Gate: P7 round-trip — generate →
   import untouched → config hash equality.
5. Tier-D driver cards + provenance expanders; FIW import w/ diff report + archetype
   validation (V1); review screen POSTing to the engine.
6. Test additions: Icarus entered via wizard must be caught at entry by validators.
Calendar: Jul 24 demo = v3 as planned (v3.1 not demo-critical; one-slide FIW teaser).
Jul 29 checkpoint = Modes W+F shipped on /v3.1, hardened for unsupervised use.
Aug 11 = Mode T UI + M11–M14 scope conversation.
