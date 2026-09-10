
## Preview demo configuration — pinned (post-PC-26)
Client observed Summary Ratios changing between preview bakes. Cause: demo-config drift, not
engine drift — PC-20..PC-23 previews were baked from pf_a_base, PC-26 from pf_a_ots_msr
(+ management_capital_target 0.10), unannounced. Verified: fixtures 9/9 stable across all
commits; management_capital_target leaves financials byte-identical (config_hash differs by
design). Standing rule: the canonical preview config is pf_a_ots_msr with management target
0.10, changed only on client instruction, and any change is called out in the reply.



## r64 — AUC-linked Operating Expense
- Operating Expense Linked Components can now consume a Customer Acquisition feed's stable period-end AUC Series directly.
- The multiplier remains ordinary percentage authoring; for the stock-linked AUC driver it also owns an explicit natural period (Month / Quarter / Year). No bespoke bps or fraud-loss expense type was added.
- Annual/quarterly AUC multipliers accrue against the canonical monthly AUC path introduced in r63, then aggregate to the selected presentation cadence. A quarterly model therefore does not substitute quarter-end AUC for intra-quarter exposure.
- Validation fails closed when the referenced AUC Series does not exist or when the same Opex category is already upstream of that CAC feed through Acquisition Spend, preventing Opex → CAC → AUC → Opex circularity.
- Regression coverage includes the source-model fraud provision pattern `period-end AUC × annual percentage rate`, monthly/quarterly cadence equivalence, missing-Series validation, and circular-link rejection.

## r63 — Canonical monthly CAC/AUC cadence foundation
- Customer Acquisition now resolves period-end AUC on a canonical monthly grid in both monthly and quarterly models.
- Quarterly native AUC remains a quarter-end balance view, sampled from canonical M3/M6/M9/M12, so existing balance consumers preserve their native-cadence contract.
- The canonical monthly AUC path is retained in CAC results/Derived Series metadata for cadence-sensitive downstream calculations instead of forcing quarter-end AUC to stand in for the three monthly exposure observations.
- Regression coverage proves that an annualized rate applied to monthly period-end AUC produces identical quarterly totals when the monthly expense is aggregated, and that monthly/quarterly CAC runs share the same canonical monthly AUC path.
- This release does not yet expose AUC in the Operating Expense link picker; it establishes the cadence-safe upstream Series foundation first.

## r62 — Acquisition-channel drag reorder
- Adds a dedicated mouse drag handle to each Customer Acquisition channel, matching the direct-manipulation pattern introduced for Operating Expense items.
- Reorders the actual channel object within its current Feed, so driver specs, derived Series IDs, and all channel economics move intact.
- Preserves per-channel Explicit editor open/closed state when indices change.
- Drag/drop is intentionally Feed-scoped: moving a channel into a different Feed remains an explicit model edit rather than a visual reorder that silently changes the customer/AUC roll-forward.

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
