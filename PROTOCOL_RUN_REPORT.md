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
