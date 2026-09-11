
## Preview demo configuration — pinned (post-PC-26)
Client observed Summary Ratios changing between preview bakes. Cause: demo-config drift, not
engine drift — PC-20..PC-23 previews were baked from pf_a_base, PC-26 from pf_a_ots_msr
(+ management_capital_target 0.10), unannounced. Verified: fixtures 9/9 stable across all
commits; management_capital_target leaves financials byte-identical (config_hash differs by
design). Standing rule: the canonical preview config is pf_a_ots_msr with management target
0.10, changed only on client instruction, and any change is called out in the reply.





## r74 — Opex cost-pool containment and ownership-state repair
- Repairs the remaining Operating Expense cost-pool authoring defects reported in live validation without changing cost-pool arithmetic, Average-AUC resolution, recovery/markup economics, or posting semantics.
- Hard-bounds the Operating Expense card and cost-pool editor as CSS grid items. The Opex use of the shared CAC/AUC preview explicitly removes the generic 184px left offset, and long Series/select text is contained or internally scrollable instead of increasing the document width. A Chromium regression using a 1,000px viewport reproduces r73 at 1,629px document width and holds the r74 fixture to 985px.
- Keys `Link existing shared pool…` disclosure state by stable Opex category Series ID plus component ID rather than row indexes. Prepending a new expense can therefore no longer inherit an older row's open pool-sharing disclosure.
- Deleting or clearing an Operating Expense category now cleans any Opex-owned private pool whose last consumer disappeared. Detailed-mode migration hygiene also removes orphaned Opex-owned pools leaked by r72/r73 while preserving live/shared pools and non-Opex pools.
- New Opex cost-pool authoring remains private-by-default: the attached pool is the only pool shown. Reuse remains an explicit sharing action and only live in-use pools are offered.
- Regression coverage distinguishes legacy/global pools, live shared pools, private Opex-owned pools, orphan cleanup, stable disclosure identity, fresh new-entry state, and hard horizontal containment.

## r69 — Explicit CAC customer-count semantics
- Separates Customer Acquisition's active-client within-year shape from the AUC within-year shape. New feeds author both explicitly; saved r68 feeds without `customer_intra_year_shape` continue to inherit the AUC shape so existing economics remain unchanged.
- Account Fee streams sourced from CAC now expose an explicit customer-count measure: `annual_count`, `period_end`, or `period_average`. The fee price path remains independently owned by the Fee Product.
- `annual_count` repeats CAC's model-year ending customer count through that year and is appropriate when the source equation applies the year's client count to the full annual per-client fee. `period_end` uses canonical monthly EOP active clients; `period_average` uses `(prior month-end + current month-end) / 2`. Quarterly engines aggregate the canonical monthly measure to preserve cadence economics.
- Saved r68 CAC-count fee streams with no measure retain their former canonical-month EOP behavior through the `period_end` compatibility default; no existing stream is silently converted to annual-count semantics.
- Guide Me must name the customer measure when it returns a CAC-driven Account-fee plan and asks a clarification when the user's description does not resolve annual count versus active-client exposure. It never infers the count measure from AUC shape.
- Regression coverage includes the 38-client case that exposed the r68 opacity: with a smooth client ramp and a `$5,000 / client / year` price, `annual_count` yields `$190,000` Year-1 revenue, canonical-month `period_end` yields `$102,916.67`, and `period_average` yields `$95,000`; each interpretation is cadence-stable by construction.

## r68 — Composable Opex cost-pool charge + CAC customer-count Series
- Restores the pre-r67 Operating Expense composition model: a cost-pool / cost-recovery charge is now a typed additive Opex component rather than a mutually exclusive calculation mode. An Opex category may therefore combine its ordinary entered recurring amount, ordinary linked components, and one or more cost-pool charges.
- Preserves r67 saved-model economics as a read-only compatibility shape. Legacy `calculation.kind = cost_pool` categories remain exclusive so dormant entered drafts do not suddenly reactivate, but new authoring no longer creates that shape.
- Keeps the shared cost-pool primitive direction-neutral. Fee Products may continue to consume a pool for revenue; Opex may consume the same primitive for NIE. Pool components remain non-posting inputs and the downstream consumer owns the single accounting posting.
- Customer Acquisition now publishes a stable customer-count Series beside its AUC Series. CAC remains the single owner of the client-count trajectory and intra-year shape; downstream Fee Products consume the resolved count rather than recreating Flat/Growth/Explicit count assumptions.
- Account Fee streams may select `Customer Acquisition client count` as their driver and apply ordinary per-account pricing. For example, 10 CAC-derived clients at `$5,000 / client / year` produce `$50,000` annual fee revenue; 20 clients produce `$100,000`. Monthly and quarterly engines resolve the same annual economics from the canonical monthly customer-count path.
- Guide Me recognizes the CAC-owned client-count source and deliberately suppresses redundant count-path / Step-Smooth instructions. The user selects the owning CAC feed, while fee-price trajectory remains independently authorable.
- Dependency/Series guards continue to reject downstream Opex charges as upstream cost-pool sources, and CAC customer-count Series IDs now participate in global stable-ID validation.
- Profile B's broader first-class Fee Product limitation remains unchanged; r68 does not claim to port all Fee Product mechanics to Profile B.

## r67 — Operating Expense cost-pool / cost-plus consumer
- Extends the shared cost-pool / cost-recovery mechanic to Operating Expense without removing or changing the Fee Product revenue use case. The accounting destination now owns authoring: revenue-side charges remain Fee Products; expense-side charges are configured in the Operating Expense tile.
- Adds an Operating Expense `Calculation` choice between the existing entered-recurring-expense path and `Cost pool / cost-plus`. Existing categories with no calculation object preserve their entered-expense semantics. Switching methods keeps the dormant entered draft rather than destroying it.
- A cost-pool-calculated Opex category posts only the final recovered / marked-up charge to NIE: `eligible cost pool × recovery % × (1 + markup %)`. Entered, balance-derived, and linked components inside the pool remain non-posting calculation inputs, so the intercompany charge is not double counted.
- Reuses r66's canonical balance-measure contract unchanged. Expense-side cost pools can therefore combine entered Flat/Growth/Explicit cost bases with `Period average` / `Period end` AUC-linked costs and Month / Quarter / Year natural-period rates.
- The source Platform Services case now authors naturally as Operating Expense: $300,000 Year-1 fixed cost, 3% annual escalation, 0.006% p.a. of Average AUC, 100% recovery, and 5% markup produces $346,500 of Year-1 NIE and the same monthly values as the source workbook.
- Cost pools remain shareable across downstream consumers. Deletion is blocked while a pool is referenced by any Fee Product or Operating Expense category; cost-pool-calculated Opex categories are not offered as upstream pool sources because the final downstream charge is not a reusable underlying cost.
- Dependency guards now cover Opex -> pool -> same Opex and Opex -> CAC/AUC -> pool -> same Opex loops. Profile B can consume shared cost pools through Operating Expense; its broader first-class Fee Product cost-pool limitation remains separate.
- Fee Product cost-recovery regression coverage remains green, confirming that the revenue-side implementation was preserved rather than migrated.

## r66 — AUC measure normalization / Reg W source-index correction
- Corrects the Reg W source-workbook regression index: forecast Year 1 uses `(1 + escalation)^0`, Year 2 uses `^1`, so the canonical Month-1 sample is $1,320 rather than $1,332. The alternate `prior_period` growth-base semantic remains available but is no longer labeled source parity.
- Adds a shared balance-measure contract: balance owners publish canonical monthly period-end observations; consumers explicitly derive `period_end` or `period_average = (prior month-end + current month-end) / 2`.
- Fixes the CAC -> Fee Product bridge so the true `beginning_auc` is retained instead of being reset to zero.
- CAC-sourced Fee Products now derive native-period Average AUC from canonical monthly exposures. Quarterly custody/trust fees and AUC-derived transaction streams no longer approximate a quarter from two quarter-end points; stepped/nonlinear paths therefore preserve monthly economics.
- Operating Expense AUC links now expose `Period average` / `Period end`. Existing r64/r65 configs with no saved measure continue to mean `Period end`, preserving prior economics. Both measures accrue from canonical monthly balances before aggregation to presentation cadence.
- Workforce AUC activation remains explicitly EOP because threshold activation is a point-in-time observable, not a period exposure. CAC itself continues to publish EOP balances; the measure choice belongs to the consumer.
- Regression coverage includes nonzero opening AUC, stepped/nonlinear quarterly paths, custody/balance fees, AUC-derived transaction throughput, Opex Period-average/EOP migration behavior, Reg W YearIndex 0/1 parity, invalid-measure fail-closed behavior, and monthly/quarterly cadence equivalence.


## r65 — Generic eligible-cost components / cost-plus pricing
- Extends the existing cost-pool / cost-recovery mechanic instead of adding a Reg W-specific fee type. Cost pools can now combine linked modeled Operating Expense / Workforce costs, entered recurring non-posting cost-base assumptions, and balance-derived non-posting cost components.
- Entered cost-base assumptions reuse Foundry's natural-period Flat / Growth / Explicit flow contract. Growth can explicitly declare that its entered base belongs to the prior growth period, allowing source models that escalate once into forecast Year 1 to be represented without manually pre-escalating the input.
- Balance-derived cost supports period-end or period-average canonical managed-notional/AUC, a Series-style multiplier, and Month / Quarter / Year natural periods. Quarterly models accrue from the canonical monthly AUC path and sum the three monthly amounts rather than substituting quarter-end AUC.
- Added a source-workbook parity fixture for `(fixed annual eligible cost + monthly-average AUC × annual variable rate) × (1 + markup)`. The original r65 fixture misidentified an AC-column Year-2 formula (`^1`) as the first forecast month and therefore asserted $1,332; r66 corrects the source index to Month-1 `^0` and $1,320.
- Preserves allocation, recovery, and markup as distinct concepts. Entered and balance-derived eligible costs are pricing sources only and never post NIE; linked costs remain observational and are never reposted.
- Adds dependency-cycle detection for direct Opex → pool → fee → Opex loops and Opex → CAC → AUC → pool → fee → Opex loops while preserving valid one-way CAC → AUC → pool → fee chains.
- Surfaces resolved cost-pool Series in the run audit payload (`$000s / engine period`) and in the Fee Product latest-run UI, alongside resulting fee revenue when unambiguous. Reg W / §23B / arm's-length context remains optional product/memo language rather than engine ontology.
- Stable-Series validation now includes CAC feed AUC identities and cost-pool-owned component identities, closing a pre-existing global-ID collision gap discovered while wiring the new balance-linked component.
- Regression coverage includes literal source-formula parity, later-year escalation, rising/falling/flat AUC, first-period average-AUC convention, monthly/quarterly parity, no-repost behavior, cycle rejection, UI authoring, callback execution, and resolved-cost audit output.

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

## r73 — Opex pool ownership / explicit sharing + real paste collapse
- Corrects r72's paste-surface self-detection bug. The generic decorator had inserted its own `Close` button, then treated that generated button as a domain-native Close control on the next decoration pass and immediately canceled the collapse. Generated Close/Edit controls are now excluded from native-close detection. Close collapses the local editor body while preserving loaded schedule values; Edit reopens it.
- New additive Opex cost-pool components now create a pool with explicit authoring ownership metadata (`operating_expense` category + component identity). If that private pool loses its sole consumer, the orphaned pool record is cleaned up rather than lingering in the global registry.
- The typed Opex editor no longer exposes the global cost-pool registry in an always-visible selector. It shows only the pool attached to the current expense. Reuse is behind an explicit `Link existing shared pool…` action; only pools already in use elsewhere are offered, and unreferenced legacy orphan pools are intentionally hidden.
- Explicitly linking an existing shared pool cleans up the replaced private pool when safe, while preserving the shared pool and its assumptions. Removing a shared-pool Opex component detaches the consumer without deleting the shared pool.
- Cost-pool arithmetic, AUC measures, recovery/markup, cadence logic, Fee Product consumers, and accounting postings are unchanged. This release changes authoring ownership/state and paste-surface behavior only.

## r71 — Authoring UI hardening
- Operating Expense `+ Add category` now prepends the new category to the visible stack instead of appending it off-screen. Existing Advanced-panel state is reindexed and the new name field is scrolled/focused so authoring starts where the user clicked.
- Opex cost-pool authoring is bounded by responsive containers. Long cost-pool names, Series/source labels, action buttons, component fields, and AUC/cost previews wrap or scroll inside the Opex card rather than widening the Configuration canvas.
- Model-authoring paste / Explicit textareas share a presentation-only Close/Edit controller when they do not already own a native Close action. Closing a paste surface never clears or rewrites its loaded schedule; narrative free-text fields remain outside this contract.
- Bank Design Lab Sensitivity no longer places lever names in a fixed-width SVG left gutter. Lever names render in responsive wrapped HTML rows beside the centered-baseline tornado bars, preserving full engagement-specific labels at narrow widths.
- This release is UI-only. No engine, Series-resolution, cadence, AUC, Fee Product, cost-pool, or accounting-posting economics change.
