
## Preview demo configuration — pinned (post-PC-26)
Client observed Summary Ratios changing between preview bakes. Cause: demo-config drift, not
engine drift — PC-20..PC-23 previews were baked from pf_a_base, PC-26 from pf_a_ots_msr
(+ management_capital_target 0.10), unannounced. Verified: fixtures 9/9 stable across all
commits; management_capital_target leaves financials byte-identical (config_hash differs by
design). Standing rule: the canonical preview config is pf_a_ots_msr with management target
0.10, changed only on client instruction, and any change is called out in the reply.


## r61 — Simplified literal Opex recognition start
- Removes r60's separate `flow_spec.start_period` / “Expense begins” axis from Operating Expense authoring.
- Recognition timing is once again a single contract: cadence + literal `first_period`. Nothing hits NIE before that event, and recurrence is anchored there (for example Annual + M35 -> M35, M47, M59...).
- Monthly timing now also accepts a first recognition ordinal, so a delayed monthly expense needs no separate commencement concept.
- The entered Flat/Growth/Explicit trajectory remains the economic amount path; recognition rebuckets forward recurrence blocks beginning at the first event.
- One-way r60 compatibility: saved `flow_spec.start_period` values are translated into the recognition contract where unambiguous, then the browser removes the obsolete field. Explicitly authored `recognition.first_period` wins.

## r60 — Opex literal commencement / late-recognition correction
- Fixes r59's semantic mismatch where a late `recognition.first_period` could leave earlier economic expense recognized on its original trajectory.
- Adds `flow_spec.start_period` as the canonical model-period ordinal for Operating Expense commencement; recurring flows are zero before commencement and growth is anchored at commencement.
- Recognition cycles are anchored to economic commencement. `first_period` must fall inside the first recurrence cycle, then repeats at the selected cadence.
- Backward-compatible migration: an r59-style late first recognition beyond the initial recurrence interval, with no explicit `flow_spec.start_period`, infers commencement at that same first-recognition period. Thus Annual + first recognition M35 begins at M35 and repeats M47/M59... rather than recognizing earlier periods.
- UI exposes `Expense begins M#/Q#` separately from Recognition timing.
