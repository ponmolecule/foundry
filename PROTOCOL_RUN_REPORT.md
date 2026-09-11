# Protocol Run Report — engine 0.2.1, July 5, 2026
Executed against GPT_Claude_consolidated_v2. Harness: `python -m foundry.tests_protocol` (22/23).

## Sequence executed
1. **Golden freeze (T2):** pre-refactor Solstice hash frozen (810235cf8fd0).
2. **Tier 2 refactor:** chassis rewritten as a module-dispatch loop. Gate: bit-identical hash.
   First attempt FAILED (two causes, both caught by T2): fee terms pre-summed inside a module
   changed float grouping; a new row field changed output structure. Fixed; hash reproduced exactly.
3. **Evidence upgrades (explained diff -> golden v2, c7f0a357eea6):** CAC prior; coupled-inconsistency
   rules; data-driven constraint evaluators; CRE/capital metric; canonical manifest. Financial numbers
   unchanged; evidence layer only.
   - **Live lesson:** first fixture extension shifted the shared RNG stream and silently regenerated the
     entire reference universe (cohort membership, terminal mix, placements). Fixed with independent
     per-column RNG streams. Production rule: reference data must be stable under extension and
     version-bumped when it is not.
4. **Wholesale funding line (explained diff -> engine 0.2.1, golden v3/v4):** Blackland's identity broke
   at month 24 — the chassis failing closed because loans outran deposits and the securities residual
   floored. Added FHLB-style borrowings to the waterfall (the architecture's wholesale-funding line);
   Solstice unaffected (borrowings identically zero). A later flag-wording edit moved the Solstice hash
   (text is output too — T2 caught it); approved and re-frozen as v4 (fa969b37747c).
5. **Bank 2 (T1/T6):** Blackland State Bank configured and run. All constraints hold in every scenario
   (min leverage 12.0% vs 9%; CRE 286% of capital vs 350% cap; breakeven m23). Cohort: 11 community-
   commercial/CRE-specialist peers, minimal widening — a different evidence base with zero engine
   knowledge of the client. Golden frozen (740bf4dd6830).

## T1 change-classification audit (Blackland)
- **Client configuration (the intended category):** foundry/client_blackland.py — all economics, all
  constraints, all targets.
- **New module code (legitimate under the new-mechanics pass condition):** commercial_lending,
  relationship_deposits, relationship_fees, branch_capacity_expenses; generic examiner-book generator.
- **Engine changes (the honest violations, each a generalization of Solstice-shaped code):**
  1. wholesale funding line in the chassis waterfall (architecturally chassis-resident; triggered by
     this client);
  2. business_flags hardcoded the funnel CAC — generalized to channel-aware linkage;
  3. Durbin flag fired unconditionally — guarded on interchange presence;
  4. runner generalized (cfg parameter, config-driven prior metrics, commitment read from constraints).

**T1 verdict: not a clean pass, and correctly so** — this was the new-mechanics path plus the expected
first-generalization pass. The supported-mechanics bar (zero engine changes) now applies to client #3
within these archetypes.

## Harness results (T2/T3/T4/T6/T14)
- T2: both goldens reproduce. 2/2.
- T3: 10/10 metamorphic checks pass on BOTH clients, every one reporting its exercised mechanism
  (no vacuous passes).
- T4: Icarus — both constraint breaches detected; CAC now flagged at p0; both coupled contradictions
  fire; clean case raises zero breaches. 8/8.
- T6 strong form: Solstice unchanged with the commercial modules registered. 1/1.
- T14: missing-assumption fails closed (KeyError); **negative attrition computes — FAIL, known backlog:**
  the config-schema validation layer is unbuilt. 1/2.

## Open findings
- Config-schema validation (T14) — the one red check.
- deposit_growth_yr1 metric-definition mismatch: fixture values and client computation are not
  identically defined, so Blackland reads p100 partly by construction. Production reference warehouse
  must compute every prior metric identically on both sides, life-stage aligned.
- COUPLED-01 fires on Solstice itself (p0 funding, p56 growth) — retained deliberately; the client's
  answer (checking mix + migration channel) belongs in the assumption book as joint support.
- Full canonical manifest fields present; lockfile digest approximated by requirements hash.

## Golden re-freeze — engine 0.3.0 (PB-1, 2026-07-09)
Explained diff, per T2 discipline. Deliberate hash movement, one cause:
- reverse_stress output gains a third dimension, `capital` (A.9): smallest
  additional opening capital holding the leverage commitment across every
  scenario, solved exactly by bisection over full re-runs (earnings feedback
  included). Solstice/Blackland: 0 additional (commitment holds). Icarus:
  ~47.8M additional — the broken applicant priced.
Financial projections are UNCHANGED: B.1 rate path (fed_funds auto-promotes to
a flat path), B.2 fixed/float rate typing, and B.3 universal scalar-or-vector
drivers were verified hash-neutral before this change (pre-change hashes
reproduced solstice_golden_v4 / blackland_golden_v1 bit-identically — that
verification is also the B.8 schema-promotion attestation).
Goldens: solstice_golden_v4 fa969b37747c -> v5 0ff7ac65dd0b;
blackland_golden_v1 740bf4dd6830 -> v2 54d956a50692.

## r67 verification addendum — Operating Expense cost-pool consumer
The release adds Operating Expense as a second downstream consumer of the shared cost-pool / cost-recovery primitive while retaining Fee Product revenue consumption. Focused regression coverage verifies the source Platform Services expense case ($346,500 Year-1 NIE from $300,000 fixed annual cost, 3% escalation, 0.006% p.a. of Average AUC, 100% recovery, and 5% markup), monthly/quarterly cadence parity, Profile B Opex consumption, dormant entered-flow preservation, missing-pool rejection, downstream self-cycle rejection, and Opex -> CAC/AUC -> pool -> Opex cycle rejection. The Fee Product cost-recovery suite remains unchanged in economic direction and green.

Pre-release full-matrix gate: 30/30 historical test entry points passed. Key suites include 70/70 cost-recovery checks, 58/58 Opex-extension checks, 24/24 Opex UI checks, 21/21 paste-surface hardening checks, 88/88 audit-remediation checks, 9/9 parity fixtures, and 331/331 protocol checks. The first matrix run correctly failed only the paste-surface inventory count after two legitimate Opex cost-pool schedule editors were added; the inventory was expanded to enumerate those controls explicitly, its full behavioral contract passed, and the complete 30-entry matrix then passed from zero.

## r68 verification addendum — compositional Opex + CAC customer-count driver
The release restores the pre-r67 additive Operating Expense architecture by representing a cost-pool / cost-recovery charge as a typed Opex component rather than a newly-authored exclusive calculation mode. Regression coverage verifies ordinary entered expense + cost-pool charge composition, exact Platform Services economics, monthly/quarterly parity, Profile B Opex consumption, missing-pool and cycle rejection, and backward-compatible reading of legacy r67 exclusive cost-pool categories without reactivating dormant entered drafts.

Separately, Customer Acquisition publishes a stable total-customer-count Series beside AUC. Account Fee streams may consume that Series directly while CAC remains the sole owner of client-count trajectory and within-year shape; the Fee Product owns its per-client price path. Regression coverage verifies a `$5,000 / client / year` Account stream at 10 clients = `$50,000` Year-1 revenue and 20 clients = `$100,000` Year-2 revenue, stable annual economics across monthly and quarterly engines, missing-Series fail-closed behavior, UI source selection, and Guide Me suppression of redundant count-path authoring.

Pre-release full-matrix gate: 30/30 historical test entry points passed from zero after updating the paste-surface inventory assertion to the generalized r68 Opex editor. Key suites include 70/70 cost-recovery checks, 59/59 Opex-extension checks, 25/25 Opex UI checks, 32/32 CAC shapeshifter checks, 47/47 Fee Stream checks, 78/78 Guide Me checks, 21/21 paste-surface hardening checks, 88/88 audit-remediation checks, 9/9 parity fixtures, and 331/331 protocol checks. The initial matrix's sole red item was a stale pastebox hardening assertion that still expected the r67 markup callback's old static form; the live per-box activation contract itself was intact. The assertion was updated to recognize the shared typed/legacy callback while still requiring both handlers explicitly, then the complete matrix passed.

## r69 verification addendum — explicit CAC customer-count semantics
The release separates Customer Acquisition's active-client within-year shape from the AUC shape and makes the downstream Account Fee customer measure explicit. New CAC feeds author both AUC and active-client shapes independently; saved r68 feeds without `customer_intra_year_shape` inherit their AUC shape so legacy economics do not move. Account Fee streams may consume `annual_count`, canonical-month `period_end`, or `period_average`; saved r68 streams without a measure retain their former canonical-month EOP interpretation.

Regression coverage includes the 38-client case that exposed the r68 ambiguity. With a smooth active-client ramp and a `$5,000 / client / year` price, `annual_count` produces `$190,000` Year-1 revenue, canonical-month EOP active clients produce `$102,916.67`, and period-average active-client exposure produces `$95,000`; all three interpretations are cadence-stable between monthly and quarterly engines. The test suite also verifies AUC/client shape independence, true opening-customer treatment for period-average exposure, invalid client-shape and invalid count-measure fail-closed behavior, public audit surfacing of all three customer measures, and Guide Me's requirement to state the customer measure rather than infer it from AUC shape or fee period.

Pre-release full-matrix gate: 30/30 historical test entry points passed from zero. Key suites include 88/88 audit-remediation checks, 39/39 CAC shapeshifter checks, 28/28 CAC UI checks, 70/70 cost-recovery checks, 79/79 Guide Me checks, 51/51 Fee Stream checks, 27/27 Fee Suite checks, 59/59 Opex-extension checks, 25/25 Opex UI checks, 21/21 paste-surface hardening checks, 24/24 Series architecture checks, 17/17 Workforce activation checks, 18/18 flags checks, 9/9 parity fixtures, and 331/331 protocol checks. Python compilation, browser JavaScript syntax, `git diff --check`, credential-signature scanning, and the runtime overfitting scan were clean.

## r70 verification addendum — hard-typed AUC cost-pool sources and source preview
The release hardens balance-derived cost-pool components after r69 introduced a sibling CAC customer-count Series. A balance-derived component now carries explicit `source_owner_module = customer_acquisition` and `source_semantic = auc_end` metadata when newly authored, while existing components remain backward-compatible when those metadata are absent. The resolver rejects a CAC `customer_count_series_id` with an explicit semantic error instead of treating it as a candidate managed-notional source. The balance-source catalog exposes only canonical monthly AUC Series and detects any AUC/count stable-ID collision.

The UI now separates the two quantities that were previously easy to confuse: each balance-derived component displays `Latest run · Period-average AUC` or `Period-end AUC` in `$000s balance · before multiplier`, while the pool-level preview remains labeled `resolved eligible cost` in `$000s / engine period`. Regression coverage deliberately supplies AUC endpoints around `$83.3MM/$166.7MM/$250MM` while the same CAC feed exposes customer-count diagnostics `70/140/210` and period-average counts `35/105/175`; the AUC preview resolves `41,666.6665/125,000/...` in `$000s` and asserts that the customer-count values never appear in the balance driver preview.

Pre-release full-matrix gate: 30/30 historical test entry points passed from zero. Key suites include 71/71 cost-recovery checks, 59/59 Opex-extension checks, 26/26 Opex UI checks, 39/39 CAC shapeshifter checks, 28/28 CAC UI checks, 79/79 Guide Me checks, 51/51 Fee Stream checks, 27/27 Fee Suite checks, 21/21 paste-surface hardening checks, 24/24 Series architecture checks, 17/17 Workforce activation checks, 88/88 audit-remediation checks, 18/18 flags checks, 9/9 parity fixtures, and 331/331 protocol checks. Python compilation, browser JavaScript syntax, `git diff --check`, and the runtime overfitting scan were clean.

## r71 verification addendum — authoring UI hardening
The release is UI-only: no financial engine or Series-resolution code changes. Operating Expense category creation now inserts the new object at the top of the visible stack, preserves/reindexes existing Advanced-panel open state, and focuses the new category so the user does not have to discover an off-screen item at the bottom. Cost-pool authoring in Opex uses bounded responsive containers; long source labels, pool names, component controls, action buttons, and AUC previews wrap or scroll inside the card rather than widening the Configuration canvas.

Model-authoring paste / Explicit textareas are covered by a reusable Close/Edit controller when a surface has no native close action. Close is presentation state only and never clears the owning schedule. The controller skips narrative free-text surfaces, persists closed state across re-renders, and decorates dynamically-rendered authoring surfaces. Bank Design Lab sensitivity rows replace the fixed SVG label gutter with responsive wrapped lever labels beside the same centered-baseline swing visualization, so long engagement-specific names remain readable without changing sensitivity calculations.

Pre-release full-matrix gate: 30/30 historical test entry points passed from zero. Key suites include 29/29 Opex UI checks, 22/22 paste-surface hardening checks, 52/52 Growth UI checks, 28/28 CAC UI checks, 8/8 Lab Fee Lever checks, 59/59 Opex-extension checks, 71/71 cost-recovery checks, 88/88 audit-remediation checks, 24/24 Series architecture checks, 18/18 flags checks, 9/9 parity fixtures, and 331/331 protocol checks. Python/browser static syntax and Git-diff hygiene are release gates as usual.

## r72 verification addendum — Opex cost-pool authoring reset + functional paste collapse
User validation of r71 correctly exposed two UI/state misses. First, the generic Close control only hid the textarea itself, so the surrounding paste controls remained visible and Close did not behave like a meaningful collapse. r72 makes generic Close/Edit presentation-only at the local paste-editor level: the editable body collapses visibly, the loaded schedule is preserved, and Edit restores the same editor without mutating model state. Purpose-built native Close controls remain authoritative.

Second, adding a new additive Opex cost-pool component in r71 could silently bind to the first existing global cost pool. If an old/orphaned pool remained after removing a component, its previously entered assumptions could reappear in what the user believed was a new cost-pool entry. r72 changes the authoring contract: `+ New cost-pool / cost-recovery component` always creates and binds a fresh empty cost pool; reuse of an existing shared pool requires an explicit source selection. A regression deliberately seeds an old pool with a 999 input and proves the new component binds to a different empty pool while leaving the old pool untouched.

The Opex cost-pool editor is also structurally restacked rather than merely overflow-clamped: source selection, pool header, component-add actions, and each entered/balance/linked component use bounded responsive rows/grids. Long Series labels and pool names remain inside the Opex card. No engine economics, AUC calculation, recovery/markup formula, or Fee Product direction logic changed.

Pre-release full-matrix gate: 30/30 historical test entry points passed from zero. Key suites include 29/29 Opex UI checks, 23/23 paste-surface hardening checks, 71/71 cost-recovery checks, 59/59 Opex-extension checks, 88/88 audit-remediation checks, 9/9 parity fixtures, and 331/331 protocol checks. Browser JavaScript syntax and Git diff hygiene also pass.

## r73 verification addendum — Opex pool ownership + paste collapse correction
User validation of r72 exposed two remaining defects. First, the generic paste decorator detected its own generated `Close` button as a native Close on the next pass, so the collapse was immediately undone in a real browser even though the prior stub test passed. The controller now excludes generated Close/Edit controls from native-close detection. The regression initializes the generic control before invoking Close so this exact self-detection failure is exercised, and a Chromium DOM smoke check verifies Close hides the editor body and Edit restores it without clearing loaded values.

Second, new typed Opex cost-pool components still displayed the entire global cost-pool registry. Although r72 created a fresh pool, old/orphaned pools remained visible beside it and made ownership/reuse ambiguous. r73 gives newly-created Opex pools explicit authoring ownership, removes the global registry from the default typed editor, places sharing behind `Link existing shared pool…`, exposes only pools with another live consumer, and cleans a private Opex-owned pool when its sole consumer is removed or explicitly repointed. Legacy orphan records remain untouched for compatibility but are hidden from new authoring.

Pre-release full-matrix gate: 30/30 historical test entry points passed from zero. Key suites include 33/33 Opex UI checks, 23/23 paste-surface hardening checks, 71/71 cost-recovery checks, 59/59 Opex-extension checks, 88/88 audit-remediation checks, 9/9 parity fixtures, and 331/331 protocol checks. Python compilation, browser JavaScript syntax, `git diff --check`, credential-signature scanning, and a Chromium Close/Edit smoke check are release gates.
