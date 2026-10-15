# r335 — guided tax calculation blocks and compact workspace

Built directly on r334 41f8a280b42e9052fca9dfc0f40500909b0ea66f. Full history and main are retained for the usual deployment script.

## Authoring

Three opt-in blocks assemble the existing validated tax-rule grammar: loss carryforward, credit limitation, and entity allocation. No new tax engine, entity names, engagement rates or amounts are inferred. Select existing monetary/scalar sources and review a read-only server plan, then Apply. The preview lists generated/reused steps, preserved source count, and the current provision before/after. Only an explicitly checked output option changes the current tax provision.

Compatible arithmetic rules are reused by normalized syntax and unit, without renaming or rewriting them. Existing inputs, schedules, standalone rules and unfinished placeholders are retained. No source-name guessing, automatic deletion, or engagement migration occurs. Existing work stays in Sources and Advanced / Derived rules; block summaries provide the shorter authoring interface.

Loss carryforward generates its own committed prior-state recurrence: no user-created placeholder or forward-reference workaround is needed. It is explicitly a period-based loss pool; it does not infer statutory annual netting, vintage/expiration rules, section 382 restrictions or recognition policy.

Credit limitation requires an explicit choice: tax up to the threshold is fully credited, or fully retained. In both cases, the selected share of tax above the threshold remains. Those choices differ economically; there is no inferred default.

Allocation supports positive entity income or signed entity income, with an explicitly chosen participating set and receiving entity. A zero denominator allocates zero. Signed shares may be negative or above 100%.

## Workspace

Aligned bounded tax-rate / utilization fields replace the scattered top controls. Three compact block actions sit above collapsed source and advanced-rule sections. Inputs have visible labels and technical IDs are secondary. Individual rule editing now uses grouped fields, a consistent action row and a collapsed expression preview. Responsive layouts wrap at 800px; the global theme is retained. No claim of rendered browser QA is made.

## Safety and compatibility

Preview is authenticated and read-only. Draft/cancel never mutates the engagement. Apply is blocked if the configuration or engagement changed since preview. Known invalid rates, balances and thresholds are rejected in preview; endogenous values are checked before each period can commit. Missing sources, units, current cycles and invalid expressions retain the existing fail-closed engine behavior.

Existing calculated and external engagements without blocks keep their full results and fingerprints. Explicitly applying a block changes the configuration, provenance and fingerprint even if the selected posting source stays unchanged. No previous engagement is automatically converted. Existing entered data do not need to be re-entered.

Payment timing, DTA/DTL recognition and entity scope remain explicit choices. The actual engagement is not reconciled until its blocks, settlement and deferred settings are finished and checked.
