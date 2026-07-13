# Peer Evidence Governance — Six Rulings (DRAFT v0.1, for client review)

**Context.** Two peer-benchmarking designs exist in this engagement: the Foundry consumption
engine (pre-registered bounded-radius cohorts, kernel-weighted priors, mandatory disclosures,
hard insufficiency) and the CharterIQ benchmark system (curated cohort definitions with a
human-judgment overlay, snapshots, percentile-derived assumption drafting). They agree on
doctrine — *evidence, never authority* — and conflict on six specific questions. Each ruling
below is argued for **Klaros's use case**: models filed in de novo charter applications and
defended before examiners under SR 26-2-aligned governance, where the decisive test of any
design choice is how it survives adversarial cross-examination.

---

## Ruling 1 — Selection authority
**Holding: the pre-registered algorithm alone decides cohort membership at run time. Human
judgment operates upstream (evidence-base curation, with recorded reasons) and downstream
(narrative argument), never on admission.**

The most damaging cross-examination available against any benchmarked filing is cohort
shopping: *who chose these peers, and did they know the client's numbers when they chose?*
Pre-registration is the only complete answer — the rules predate the question. A cohort that
is "cheap and editable" with judgment on top is exactly the surface that question opens.

What this ruling does **not** discard: the judgment overlay's value is preserved in two
sanctioned places. (a) **Warehouse curation** — data-quality and integrity exclusions
(enforcement actions, broken filings, non-de-novo charters) applied to the evidence base
itself, every exclusion carrying a recorded reason in the vintage manifest; "excluded:
enforcement action pending" remains evidence of rigor, applied to *everyone's* cohorts
identically, blind to any client. (b) **Counsel's exhibit** — comparators Klaros wishes to
cite that the algorithm did not admit may appear in a clearly labeled advocacy section,
outside the statistics, never entering a percentile. The line is bright: judgment may shape
what the evidence base contains and what the narrative argues; it may not touch who counts.

## Ruling 2 — Direction of inference
**Holding: percentile-derived assumption drafting ("set to peer p50") is permitted as a
drafting convenience, but a derived assumption carries permanent provenance, and the
challenge layer must treat cohort-consistency of a cohort-derived value as
consistency, never support.**

The trap is circularity: an assumption set *from* the cohort's median will, by construction,
sit at the median when challenged *against* that cohort — flags never fire, the examiner book
stays silent, and a plan whose every input was set to p50 presents as maximally supported
while being maximally unexamined. Under this ruling: (a) derived values are tagged
`peer_derived(cohort_id, metric, percentile, vintage)` in the assumption book; (b) the
challenge layer prints, for such assumptions, "placement reflects derivation, not
independent support"; (c) support status requires independent evidence (contract, observed
parent data, engagement diligence) or testing against a different vintage; (d) derivation
defaults are step-3 drafting aids that must be resolved to committed, rationale-bearing
values by step 6. An examiner who asks "what supports 2.1% deposit cost?" must never be
answered by the same cohort twice.

## Ruling 3 — Selection geometry
**Holding: continuous distance remains the admission engine. Rectangular criteria
(geography, asset bands, tags) enter only as pre-registered, archetype-specific feature-set
extensions — never as ad hoc filters.**

Rectangular bands create cliff effects and a tuning surface (move the band edge $50M and the
cohort changes — shopping by another name). Distance degrades gracefully and discloses
honestly. But the objection embedded in the alternative design is correct for one archetype:
geography is economically first-class for branch-based community banks and absent from the
current five features. Resolution: the criteria document defines **feature sets per
archetype**, frozen before client review — the digital-consumer set stands as-is; a
community/CRE set adds pre-registered market features (e.g., state or MSA-density, local
deposit concentration). This extends pre-registration rather than breaching it, and it is
the Blackland-shaped concession the current engine owes.

## Ruling 4 — Thin evidence
**Holding: hard insufficiency stands for anything filed. Sub-minimum cohorts may be viewed
in the workspace only as watermarked exploration, and their placements cannot flow into a
filed assumption citation. The sanctioned fallback is a coarser, honest baseline — the UBPR
peer group — clearly labeled as coarser, not a widened radius.**

With a realistic universe of one to two hundred de novo trajectories, insufficiency will
bind often, and the pressure will be to soften it. For Klaros the discipline *is* the
product: "this tool refuses to manufacture evidence" is the sentence that buys credibility
with an examiner, and it is only true if refusal is mechanical. Flag-and-proceed converts a
hard property into a caveat nobody reads. Where the bounded-radius cohort comes back
insufficient, the model answers a coarser question honestly (national UBPR peer-group
placement, labeled as such) rather than the precise question dishonestly.

## Ruling 5 — Statistic of record
**Holding: kernel-weighted percentiles with disclosed effective-n are the statistic of
record; unweighted counts and percentiles are disclosed alongside; where the two readings
disagree across a flag threshold, the flag fires — the model takes the worse reading.**

Distance weighting is the defensible position (a barely-admitted peer should not count as
much as a near-twin), and effective-n is the honest sample size under any weighting. But a
weighting scheme must never be attackable as concealment, so both readings are shown, and
the conservative rule removes any incentive to prefer one: whichever reading is worse for
the applicant governs the flag. No examiner can allege the statistics were chosen to flatter.

## Ruling 6 — Survivorship
**Holding: no survivor-only statistic may support a filed assumption. Steady-state
("mature archetype") benchmarks must be built from the trajectory universe evaluated at
age — including members who subsequently failed or were acquired — or, where a
present-quarter sponsor cohort is used, must carry a cohort-mortality disclosure beside
every figure.**

A cross-sectional cohort drawn from banks filing the most recent quarter is structurally
survivor-only: the dead don't file. Its steady-state economics are therefore flattered by
construction, and the flattery compounds exactly where charter applications are most
optimistic. The trajectory universe fixes this cleanly — "banks like ours at age 20
quarters" naturally includes those that died at quarter 30. Where a live sponsor cohort is
nonetheless the right exhibit (the Pack B story — *these partner-led banks exist today*),
it may be shown with its base rate attached: of the N comparable entrants since 2010, X
failed and Y were acquired. The examiner-book survivorship question remains generated in
all cases.

---

## Interface assignments implied by the rulings
CharterIQ owns: the evidence base, curation with recorded reasons (R1a), snapshots and
ingest-watermark vintages, the trajectory and age-aligned tables (R6), UBPR peer-group
baselines (R4). Foundry owns: pre-registered admission from the snapshot (R1), weighting
and placement with dual disclosure (R5), insufficiency machinery (R4), provenance-aware
challenge (R2), archetype feature sets in the criteria document (R3), flags and the
examiner book. The extract spec moves to v1.1 to add: age-aligned trajectory table,
snapshot/watermark vocabulary, curation-reason fields, and a real freeze event replacing
the fixture's simulated pre-registration date.

## Status
DRAFT for client review. Nothing here is implemented until ratified; Rulings 2, 3, 4, and
6 imply Foundry work (provenance tags, archetype feature sets, UBPR fallback, mortality
disclosure) and CharterIQ work (trajectory re-indexing, curation manifest) that will be
sequenced after ratification.
