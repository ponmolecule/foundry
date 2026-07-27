# Foundry — Executive Summary redesign v2 (reconciled, build spec)

Reconciles the original component spec with GPT's review. Each item marked **[ADOPT]**,
**[SIMPLIFY]**, or **[DEFER]**. Every generated word/number traces to a named model field —
no free-composed prose, no absolute claims, no invented workflow fields.

---

## Layer 0 — Top utility line  **[ADOPT]**
A thin identity strip so live and exported summaries are bound to the same immutable run:
`Config {config_version} · Run {config_hash} · Engine {engine_version} · Peer snapshot {peer_snapshot_id} · Generated {ts}`.
Fields exist today except peer_snapshot_id (verify/capture). Export must carry the same identity.

## Layer 0.5 — Change since prior version  **[ADOPT]**
Uses the diff engine we already built (`_diffCfgAgainst`). One narrow strip:
"Since {prior}: opening capital +$3.0M; retail-deposit growth −5 ppt; min leverage +42 bp;
verdict unchanged." Only shown when a prior baseline exists.

---

## TIER 1 — Judgment

### 1a. Verdict block — GENERATED, meets/does-not-meet framing  **[ADOPT, relanguaged]**

**Precedence 0 (integrity/completeness GATES the verdict)** — checked before any viability call:
| State | Call |
|---|---|
| model integrity check fails | **Results unavailable — model integrity issue** |
| required inputs incomplete / stale run | **Assessment incomplete — required inputs unresolved** |

**Verdict enum** (only reached if Precedence 0 clears) — meets/does-not-meet, never viable/clean:
| State | Call |
|---|---|
| base hard constraint fails | **Does not meet the stated {constraint-source-noun}** |
| base passes, a modeled stress fails | **Meets base constraints; vulnerable under stress** |
| constraints pass, ≥1 severe assumption fires | **Meets modeled constraints; material assumptions require support** |
| advisory findings only | **Meets modeled constraints; review items remain** |
| nothing fires | **No modeled exceptions identified** |

**Constraint-source drives the noun**  **[ADOPT]** — from `constraints[].source`:
- regulatory requirement → "stated capital **requirement**"
- charter/application commitment → "stated capital **commitment**"
- board/management target → "management capital **target**"
- engagement convention / system default → "engagement **threshold**"
So Calamity (9% = engagement commitment) → "**Does not meet the stated capital commitment.**"
Never "Not viable."

**Slots (each a named field; line omitted if null):**
- Binding reason: "Base leverage bottoms at **{min_leverage}%** in **Q{min_leverage_q}** against the
  stated **{commitment}%** threshold; **all {n} modeled scenarios** breach it." → base.min_leverage,
  base.min_leverage_q, constraints[0].value, count of failing scenarios. ("all MODELED scenarios",
  never "all scenarios".)  **[ADOPT]**
- Highest-priority finding (NOT "driver"): the top issue family's headline, in the flag's own text.
  **[ADOPT rename]** — "driver" implies causation we haven't attributed.
- Capital requirement, precisely scoped: "Estimated additional opening capital to maintain the
  **{commitment}%** base-case threshold **through Q12**: **${capital_shortfall_est}K** (estimate)."
  **[ADOPT]** — state exactly what it solves (scenario + horizon + estimate status).

Worked (Calamity): "**Does not meet the stated capital commitment.** Base leverage bottoms at
**2.14%** in **Q1** against the stated **9.0%** threshold; **all five modeled scenarios** breach it.
Highest-priority finding: **$0.5M** of opening equity supports **$335.5M** of Q0 assets and requires
approximately **$244M** of opening borrowings. Estimated additional opening capital to maintain the
9.0% base-case threshold through Q12: **$115.2M** (estimate)."

### 1b. Leverage sparkline  **[ADOPT]**
12-quarter base leverage path + commitment line. Fields: financials.ratios.lev[], constraints[0].value.

### 1c. Top issue families strip (ADAPTIVE, family-grouped)  **[ADOPT grouping, SIMPLIFY ranking]**
2–3 root-cause families, NOT raw flags (avoids three CRE variations filling the strip). Families:
opening capitalization & Day-1 funding · CRE economics & concentration · deposit pricing & growth ·
card pricing & credit losses · mortgage-banking execution · expense/staffing · evidence/citation gaps.
**Ranking [SIMPLIFY]:** explainable order only — families containing a constraint-breaching or severe
flag first, then by flag count. NOT a 5-term weighted composite (un-auditable magic number).
Adaptive: a clean bank shows "no input outside its peer band" or nothing.

---

## TIER 2 — Decision drivers  **[ADOPT, recomposed]**
Four metrics that move the verdict (breakeven REMOVED — misleading: Calamity "breakeven Q1" while
Year-3 NI ≈ −$2.8M):
- Minimum base leverage ({value} in Q{q} vs {commitment})
- Worst stress outcome ({min_leverage} of the worst scenario)
- Opening wholesale funding (~${day1_borrow}) — the funding the plan needs Day 1
- **Earnings durability** — Year-3 net income (replaces breakeven)  **[ADOPT swap]**

### Required before sign-off  **[ADOPT LITE — reject PM scaffolding]**
Up to 3 generated, flag-family-linked STATEMENTS ("Revise or support the opening capitalization and
Day-1 funding plan"). Each may carry "can resolving this change the verdict? yes/no". **NO owner /
due-date / status fields** — Foundry models banks, it is not a task tracker. **[SIMPLIFY]**

---

## TIER 3 — Evidence (expanded by default: 1–2; collapsed: 3–6)

1. **Input reasonableness review** (lead, open). Per thesis-bearing assumption: Input · Value ·
   Observation (GENERATED from value-vs-band position) · Peer benchmark (LIVE p10–median–p90, n,
   vintage) · Comparability label · Severity · Conclusion. **[ADOPT]**
   - **Peer cohort summary line + caveats INLINE**  **[ADOPT+]**: "Benchmarked against {n} de novo
     filers, {vintages}. Current-quarter stock measures are like-for-like; selected earnings measures
     are directional (modeled quarterly vs peer YTD). **View cohort basis →** (links to Peer Cohort tab)."
   - **Per-metric comparability label**  **[ADOPT]**: like-for-like / directional / not comparable /
     insufficient sample — on EACH peer band, not one blanket footnote.
2. **Scenario & constraint outcomes** (open). All modeled scenarios, min leverage, quarter, pass/fail.
3. Three-year financial summary (collapsed)
4. Model integrity checks (collapsed) — also feeds Precedence 0
5. Full threshold ledger (collapsed)
6. Change history (collapsed)

## APPENDIX — Peer cohort & survivorship  **[ADOPT, export-primary + on-screen drawer]**
On-screen: the compact inline summary above + link to the live Peer Cohort tab (the interactive
drill-down). Export appendix (self-sufficient, offline-defensible) contains the full manifest:
cohort definition · selection date & Call Report vintage · inclusion/exclusion rules · survivorship
treatment · effective-n **by metric** · radius-widening/fallback · denominator & annualization
convention · comparability classification · peer-data snapshot ID · registry & model version.
(Most already computed by the substrate — this itemizes what to emit.)

---

## DEFERRED (honest — needs data we don't have)
- **Evidence readiness** ("7 of 12 thesis-bearing assumptions supported")  **[DEFER]**: requires a
  per-assumption supported/unsupported status Foundry doesn't track (it's a human judgment — was a
  pipeline doc provided?). Design toward it; do not fabricate. Needs a new input field first.
- **Real causal attribution for "driver"**  **[DEFER]**: until a sensitivity/remediation test exists,
  language stays "highest-priority finding," never "driver".

---

## Overstatement controls (verdict can still mislead even when slot-filled)  **[ADOPT all]**
- Qualify by constraint source (management target ≠ regulatory requirement).
- "Highest-priority finding", never "driver", absent attribution.
- Comparability status on every peer benchmark.
- "No modeled exceptions identified", never "Clean".
- Capital shortfall labeled: method · scenario · horizon · estimate.
- Precedence 0 (integrity/completeness) before any verdict.
- "All modeled scenarios", never "all scenarios".

---

## Build sequence
1. **Spacing fix** — threshold ledger `<details>` butts the first flag; add margin. (trivial)
2. **Verdict block + Precedence 0 + constraint-source wording + sparkline + Tier 1/2/3 hierarchy +
   earnings-durability swap.** (core reframe)
3. **Input reasonableness review + adaptive family strip + per-metric comparability + inline peer
   summary/link.** (content win)
4. **Change-since-prior strip + required-before-sign-off statements + top utility line / run identity.**
5. **Export parity** — verdict prose + peer appendix into the exec-summary export.
