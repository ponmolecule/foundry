# r307 — Guide Me vocabulary and annual-change mapping repair

See R307_RELEASE_NOTES.md and R307_VALIDATION.md. Engine and saved engagement results unchanged.

# r306 — Zero funding and FDIC template defaults

See R306_RELEASE_NOTES.md and R306_VALIDATION.md. Saved engagements are unchanged.

# r305 — Consistent fee-stream authoring

See R305_RELEASE_NOTES.md and R305_VALIDATION.md. Built on r304; no legacy fixture output changes.


## Preview demo configuration — pinned (post-PC-26)
Client observed Summary Ratios changing between preview bakes. Cause: demo-config drift, not
engine drift — PC-20..PC-23 previews were baked from pf_a_base, PC-26 from pf_a_ots_msr
(+ management_capital_target 0.10), unannounced. Verified: fixtures 9/9 stable across all
commits; management_capital_target leaves financials byte-identical (config_hash differs by
design). Standing rule: the canonical preview config is pf_a_ots_msr with management target
0.10, changed only on client instruction, and any change is called out in the reply.

## r104 — Canonical-monthly Customer Acquisition engine
- Replaces Customer Acquisition's annual causal engine plus post-hoc within-year shaping with one canonical monthly calculation. Month / Quarter / Year now belong to each CAC source assumption; annual tables are presentation aggregations of the monthly results.
- Flow operands (`Pool`, `Acquisition Spend`, `Productivity`, `Compensation/FTE`, `Explicit New Customers`) own a natural Month / Quarter / Year amount period. Annual totals are spread over twelve causal months, quarterly totals over three, and monthly amounts are used directly. Level/rate operands (`Conversion`, `CAC $/customer`, `FTE Count`, `Average AUC/customer`) hold as levels until their authored trajectory changes.
- Cross-module CAC links consume the source owner's monthly-resolved Series directly and are never periodized twice. The r103 Operating Expense → CAC contract therefore remains intact, including Workforce Count × amount/FTE components.
- `Pool × Conversion`, `Spend ÷ CAC`, `FTE × Productivity`, and `Explicit Customers` are evaluated month-by-month. A varying monthly pool and conversion path therefore uses `sum(monthly pool × monthly conversion)` rather than multiplying annual averages.
- Existing-book attrition is source-period causal: Month / Quarter / Year controls the attrition event period, and the rate is applied at the source-period boundary to the book that existed at the beginning of that source period. Annual attrition therefore remains a once-per-year opening-book assumption rather than being repeated twelve times.
- Legacy `intra_year_shape` / `customer_intra_year_shape` fields remain readable but no longer manufacture CAC timing after an annual calculation. Legacy `new_customers_by_year` retains its historical zero-beyond-supplied-years extension behavior.
- CAC Explicit authoring always offers Month / Quarter / Year even under quarterly presentation. Switching a natural-period flow or attrition assumption between Flat/Growth/Explicit preserves its authored amount/source period rather than silently changing economics.
- Calculation Audit adds `CAC Monthly Acquisition`, exposing every monthly channel operand and equation result. `CAC Channels` is now explicitly an annual summary; `CAC Monthly Canonical` adds monthly acquisition/attrition flows alongside stock observations.



## r102 — Workforce Count-linked Operating Expense + useful workforce run summary
- Adds a first-class Operating Expense linked-component contract for `Workforce Count × amount per FTE`. The driver is selected by a stable Workforce Series ID: either a role/population `series_id` or the Workforce-owned aggregate `total_count_series_id`. Display names are labels only.
- The coefficient is a typed natural-period dollar amount per FTE, not a dimensionless percentage. Flat / Growth / Explicit paths support Month / Quarter / Year amount units; `$12,000/FTE/year`, `$3,000/FTE/quarter`, and `$1,000/FTE/month` resolve equivalently and are periodized exactly once before multiplying active headcount.
- Both Profile A and Profile B consume the same resolved Workforce Count Series. The aggregate count is derived from the active role populations used by the workforce runtime and is surfaced in run output for auditability. Missing stable Series references fail closed.
- Calculation Audit now carries Workforce Count into Operating Expense reconciliation. `Opex Component Detail` exposes the active FTE/headcount operand, resolved amount/FTE factor, and calculated raw-dollar expense, so a headcount-linked cost does not disappear into an Other Opex residual.
- Replaces the sparse `Workforce activation tracking` table with a compact `Workforce run summary`: role/population, resolved headcount path, compensation/FTE path, resolved active window plus authored start rule, and payroll load. A Total workforce row shows the aggregate headcount Series available to Opex.
- No engagement-specific staffing or expense labels are embedded in the engine. Workforce remains the single owner of Count trajectories; Operating Expense is a read-only downstream consumer.

## r100 — Product Details precision toggle + unrounded diagnostic path
- Adds a Product Details `High precision (reconciliation view)` toggle. Presentation mode remains fixed at three decimals in `$000s`; High precision exposes up to 15 significant digits. The toggle is display state only and does not change model assumptions, accounting, statements, or parity outputs.
- Corrects a deeper r98/r99 limitation: Product Details had been formatting the historical public parity product arrays, which are rounded to `0.01 $000s` before reaching the browser. A value such as `0.038779351215693 $000s` therefore arrived as `0.04`, so showing three decimals could only produce `0.040`.
- `run_v2` now carries a parallel `detailExact` monetary series for Product Details from the same base engine run, converted to `$000s` without parity rounding. Presentation mode formats that exact series to three decimals (`0.039` in the regression); High precision exposes `0.038779351215693`. Legacy public product arrays remain unchanged for compatibility.
- Calculation Audit headline Fee Product rows now reconcile to the same unrounded Product Details diagnostic series when available, while the separately labeled `· exact engine` rows remain as a second audit trail.
- First-principles regression uses three Fee Product costs of `0.019282552032793`, `0.019282552032793`, and `0.000214247150107 $000s`: exact sum `0.038779351215693`, legacy parity product value `0.04`, Product Details diagnostic `0.038779351215693`.

## r99 — Product Details fixed three-decimal precision
- Product Details now renders every monetary `$000s` cell to exactly three decimal places, regardless of magnitude. This replaces r98's magnitude-aware formatting so troubleshooting views are consistent and never hide the third decimal on larger values.
- Zero values render as `0.000`; observed Stablecoin examples render as `0.386`, `2.020`, `0.019`, `0.101`, while larger values such as `257.100694` and `1,346.886525` render as `257.101` and `1,346.887`.
- The change is presentation-only. Engine arrays, audit workbook precision, accounting, cadence, Fee Product economics, and model configuration remain unchanged.
- Regression coverage executes the shipped Product Details formatter in Node and asserts fixed three-decimal formatting across small, zero, and larger `$000s` values.

## r98 — Product Details diagnostic precision
- Product Details remains in `$000s` but now uses magnitude-aware display precision so small engine-computed values are not rounded out of existence while troubleshooting. Values below 10 `$000s` show three decimals, below 100 show two, below 1,000 show one, and larger values remain whole `$000s`.
- The Stablecoin regression that exposed the defect now renders approximately `0.386` and `2.020` of fee income and `0.019` and `0.101` of Fee Product cost instead of `0`, `2`, `0`, `0`. Underlying engine arrays, accounting, audit exports, and model economics are unchanged.
- Per-product detail rows use the diagnostic formatter only; statement/reporting tables retain their existing presentation conventions. The Fee Product cost row is also labeled generically as `Fee Product cost (→ overhead)` rather than the narrower `Pass-through cost`, which is not correct for every direct-cost basis.
- Product Details now surfaces a nonzero Fee Product cost row down to a de minimis floating-point threshold rather than requiring a value above 0.5 `$000s` merely to appear.
- Regression coverage executes the shipped formatter in Node against the observed Stablecoin values and asserts the Product Details table uses the diagnostic formatter and the neutral Fee Product cost label.

## r97 — Transaction operating cost as % of throughput
- Adds a first-class Transaction Fee Product cost mode, `pct_of_throughput_opex`, for source-model economics quoted as a percentage of transaction volume/throughput rather than as a percentage of gross fee revenue.
- The calculation is `Transaction throughput × direct cost rate × cost multiplier = Fee Product cost`. Gross fee income remains intact and the cost routes to Noninterest Expense: Fee Product Costs.
- Keeps `pct_of_revenue_opex` unchanged for genuinely revenue-based operating costs and `pct_of_revenue` unchanged for contra-revenue/revenue-share economics. No implicit conversion between cost bases is performed.
- The UI exposes “Operating cost (% of throughput)” with the same Flat / Growth / Explicit Month / Quarter / Year trajectory grammar and separate multiplier layer already used by direct Fee Product costs.
- Calculation Audit identifies the direct cost factor as `% of transaction throughput`, so the troubleshooting workbook preserves the cost base explicitly.
- Focused regression uses the observed source-model shape: 0.15% revenue on throughput plus 0.0075% operating cost on throughput, proving the cost is computed directly from volume rather than approximated as 5% of revenue.

## r94 — Audit/Product Details snapshot reconciliation
- Pins Calculation Audit export to the exact public preview snapshot shown by Product Details. The browser freezes the current config, invalidates older in-flight previews, obtains a fresh preview, and posts that config together with its `config_hash` and `run_hash`; the server re-runs the frozen config and refuses the export on any hash mismatch.
- Changes the headline `Fee Product Costs` rows (`Fee revenue`, `Fee Product cost`, `Product operating expense`) to consume the same public product Series that Product Details displays, so the workbook reconciles cell-for-cell instead of silently comparing a public rounded view with a separate raw-engine representation.
- Retains the audit workbook's hidden-precision purpose with separately labeled `· exact engine` rows for those same product measures. Reviewers can therefore compare Product Details exactly and still inspect unrounded engine values without confusing the two representations.
- Adds a dedicated reconciliation regression covering all three product rows, workbook-cell equality, exact-engine preservation, browser snapshot freezing/hash pinning, edit-during-export fail-closed behavior, and server-side 409 rejection for mismatched hashes.
- Verification: all 31 historical test entry points pass; the new audit-reconciliation suite passes 11/11; Fee Suite remains 45/45 and parity remains 9/9. Python compilation, browser JavaScript syntax, `git diff --check`, credential-signature scanning, and modified-runtime engagement-overfitting scanning are clean. No financial-engine economics changed.

## r93 — Transaction pricing and direct-cost trajectories
- Generalizes Transaction percentage pricing so `Fee (% of throughput)` is a first-class Flat / Growth / Explicit rate path with Month / Quarter / Year natural periods, Step / Smooth resolution, percentage paste ingestion, compact schedule preview, and View all / Collapse inspection. Legacy scalar `per_unit` remains the Flat fallback for saved configurations.
- Reuses Foundry's factor-path grammar without conflating economic layers: Transaction throughput is resolved first, the revenue-rate trajectory prices that throughput, and no pricing factor is divided by projection cadence. The r91 `Amount per source unit` coefficient remains independent and unchanged.
- Promotes Fee Product `cost.params.factor_path` from a compatibility-only replacement path to the first-class direct cost rate/factor trajectory. `Operating cost (% of gross fee revenue)` and other fee-product cost modes can therefore author Flat / Growth / Explicit paths directly.
- Preserves `cost.params.multiplier_path` as a separate multiplicative layer. Effective fee-product cost is `direct cost path × cost multiplier path`; saved r82 factor-path models remain exact because their implicit multiplier is 1.0, while scalar-only r83+ models retain the scalar as their Flat fallback.
- Extends Calculation Audit Workbook provenance to show the direct cost path, cost multiplier, and effective cost factor independently. Bank Design Lab exposes non-explicit Transaction rate-path, direct-cost-path, and multiplier levers independently.
- Tightens authoring-state hygiene: incompatible pricing-rate paths are retired when a stream changes basis, and Durbin authoring clears the ordinary Transaction rate path rather than retaining a hidden conflicting pricing state.
- Focused regression coverage proves revenue Flat / Growth / Explicit behavior, Month / Quarter / Year buckets, Step / Smooth growth, explicit percentage paste ingestion, zero/negative revenue-rate conventions, percentage-cost bounds, Amount-per-source-unit interaction, direct-cost × multiplier composition, audit provenance, and the new UI paths.
- Pre-release verification: all 31 historical test entry points passed from zero; focused Fee Suite 45/45, Growth UI 60/60, paste-surface hardening 26/26, and Lab Fee Levers 8/8. Python compilation, browser JavaScript syntax, `git diff --check`, credential-signature scanning, and modified-runtime overfitting scanning are clean.

## r80 — Advanced Opex timing ownership and authoring cleanup
- Clarifies timing ownership without changing existing valid-model economics. Category-level recognition and cash-settlement controls govern only the entered recurring Opex trajectory; additive linked, cost-pool, and self-timed tiered/banded components retain their own/native timing.
- Hides recurring-expense recognition and settlement controls when the entered recurring trajectory is economically zero. Stored settings are preserved rather than deleted, so they return unchanged if the recurring expense becomes active again.
- Mixed categories are now valid: an entered recurring expense may use custom recognition/settlement while additive components continue on their independent timing. The prior blanket validation guard is removed because the engine paths are already resolved separately.
- De-verboses Advanced Operating Expense authoring: removes release-history archaeology and repetitive implementation prose, keeps only short decision-oriented helper text, and retains clear section ownership.
- Renames the tier schedule's user-facing `Base amount` field to `Band base fee` so it cannot be confused with the category's entered recurring expense. Stored schema remains `base_amount`; piecewise arithmetic is unchanged.
- Tiered/banded observation lag, event cadence, first event model period, driver composition, bands, Series resolution, and accounting posting logic are unchanged. No OCC- or engagement-specific runtime branch is introduced.





## r75 — Opex cost-pool removal placement polish
- UI-only refinement to the typed Operating Expense cost-pool editor. The existing `Remove cost-pool component` action is preserved but moved from a detached trailing link into the cost-pool component title bar, right-aligned and visually secondary.
- The detached `× remove cost-pool component` link is removed so each typed cost-pool component exposes a single removal affordance attached to the object it affects.
- Pool ownership, orphan cleanup, explicit sharing, recovery/markup economics, AUC measures, and accounting postings are unchanged.
- Regression coverage asserts the header placement and the absence of the old detached trailing link.

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

## r95 — Preview lifecycle recovery + audit snapshot isolation
- Fixes an r94 regression where Calculation Audit preparation advanced the shared browser preview sequence before its own snapshot had succeeded. A failed audit attempt could therefore invalidate the normal model preview and leave Balance Sheet, Product Details, and Income Statement permanently on `Running…`.
- Calculation Audit now runs the same `syncModules()` normalization as Product Details before freezing its config, does not advance the shared preview sequence on failure, and invalidates older previews only after a successful still-current snapshot has landed.
- Failed audit preparation schedules a normal preview recovery and surfaces the actual timeout/HTTP diagnostic instead of the opaque `Could not prepare the calculation-audit snapshot.` message where possible.
- The normal preview path now fails visibly rather than spinning forever: network errors, HTTP failures, unreadable responses, and a 60-second timeout set an explicit model-run failure state and render no stale financials.
- Financial-engine arithmetic, accounting, Fee Product pricing/cost semantics, cadence, and the r94 audit/Product Details reconciliation contract are unchanged.

## r106 — Ending bank customers Fee Product link
- Exposes the CAC-owned customer-count Series in Account-basis Fee Product authoring as **Ending bank customers — Customer Acquisition**, with stable-ID feed selection and a latest-run read-only path preview.
- Keeps canonical customer-count measures explicit: monthly period-end Ending bank customers, year-end customers held through the model year, or period-average customers.
- Makes source switching non-destructive: an existing pasted Constant/Explicit Account count path is preserved while the CAC link is active and restored exactly if the user switches back to Constant.
- Guide Me uses the same economic wording. Engine arithmetic, CAC ownership, Fee Product pricing, cadence, and accounting are unchanged.

## r108 — Workforce compensation amount basis
- Adds a generic Series amount-basis primitive: `total` versus `per_unit`. Workforce presents `per_unit` as **Per FTE**.
- Ordinary Workforce compensation can now be authored as **Total** without multiplying by Count. Count remains an independently published/linkable Series for other model consumers.
- Keeps amount basis orthogonal to Flat/Growth/Explicit trajectory, Month/Quarter/Year amount period, Explicit schedule cadence, and Growth rate period.
- Preserves pre-r108 economics by treating historical Workforce compensation as Per FTE. Invalid bases fail closed.
- Adds Total/Per FTE authoring to the main Workforce row, bulk paste, Calculation Audit, FIW, and reviewer-facing settings output. Generic paste rows require both basis and period; historical self-describing per-FTE headers remain valid.
- Regression includes the motivating `28.333 FTE + 354 $000s/month Total` case, which now produces exactly `$354k/month` rather than `$10.029882MM/month` while retaining the 28.333 Count Series.

## r120 — Formula / level fixed-asset basis correction
- Corrects the r119 accounting bug that silently treated every Formula / level stock as **net PP&E**. Under r119, a flat authored asset level plus depreciation caused gross PP&E and implied CAPEX to increase every period by the depreciation charge, effectively manufacturing replacement CAPEX that the user never authored.
- Formula / level now owns an explicit `level_basis`: **Gross PP&E** (default) or **Net PP&E target**. Gross basis is the canonical/default r120 path: the entered base + linked-Series × multiplier formula resolves gross PP&E; depreciation increases accumulated depreciation and reduces net PP&E; a flat gross level therefore creates no replacement CAPEX.
- Explicit Net PP&E target remains available for source models that intentionally maintain a net carrying-value target. That branch preserves the r119 target-maintenance reconciliation `gross = net + accumulated depreciation` and `implied CAPEX = Δnet + depreciation`, but it is no longer a hidden assumption.
- r119 Formula / level configs remain readable. `opening_net` is accepted as a migration alias for `opening_level`; missing r119 `level_basis` values resolve to **gross** because the hidden net interpretation is the defect this release repairs. New browser authoring stores `opening_level`, `opening_accumulated_depreciation`, and `level_basis` explicitly.
- Historical Simple configs remain byte-for-byte on their legacy engine path until explicitly converted. Browser conversion to Formula / level now materializes an explicit **net-basis** schedule so the conversion itself preserves the historical declining-net path rather than double-depreciating it.
- Gross-basis declines are treated as proportional disposals of the existing asset pool. Foundry relieves the same proportion of accumulated depreciation before current-period depreciation, preventing accumulated depreciation from remaining attached to disposed gross PP&E and keeping the reduction at carrying value. Depreciation is capped at the remaining carrying basis.
- FIW, Calculation Audit, public parity conversion, and browser authoring now surface the basis explicitly. Asset schedule is unchanged.
- Focused Fixed Assets coverage is **46/46** and Fixed Assets UI is **8/8**. The complete pre-stamp historical/current matrix passes **35/35** entry points on one unchanged tree (entries 1–23, then 24–35 after the execution window, with no intervening code changes). Universal Template is **56/56**, Series Architecture **40/40**, Opex Extensions **96/96**, parity **9/9**, and protocol **332/332**. Python compilation, browser JavaScript syntax, `git diff --check`, changed-line credential scanning, and changed-runtime engagement-name scanning are clean.

## r123 — Formula / driver Operating Expense rationalization
- Rationalizes new Advanced Operating Expense authoring to three structural families: **Formula / driver**, **Tiered / banded**, and **Cost-pool / cost-recovery**. Historical linked and service-capacity storage remains readable/editable for backward compatibility, but no longer requires separate new-authoring buttons.
- Adds a constrained typed factor chain using stable linked Series and entered Flat / Growth / Explicit factors. Factors may multiply or divide; only factors that own a natural time unit carry Month / Quarter / Year and are periodized exactly once.
- The same Formula / driver primitive expresses conventional service capacity and four activity-cost cases without engagement-specific branches: base × transactions/base × cost/transaction; base × incidents/base × cost/incident; remittance volume × cost rate; and calls × cost/call.
- Calculation Audit surfaces the factor chain and resolved operands. Universal coverage includes a stable linked quantity × periodic activity factor × non-periodic unit-cost specimen. Workload-derived Compliance remains intentionally out of scope pending explicit quantity-period semantics.
- Pre-stamp verification: complete historical/current matrix **35/35** on one unchanged tree (entries 1–30, then 31–35 after the execution window). Focused suites: Opex Extensions **115/115**, Opex UI **64/64**, Growth UI **79/79**, pastebox hardening **29/29**, Universal **58/58**, Series Architecture **40/40**, parity **9/9**, protocol **332/332**. Python compilation, browser JavaScript syntax, `git diff --check`, changed-line credential scanning, and runtime engagement-label scanning are clean.

## r125 — Fee-stream quantity unit metadata correction
- Corrects misleading Opex Formula / driver linked-source metadata that labeled every transaction Fee-stream quantity as `$000s / month` or `$000s / quarter`. Fee-stream quantity Series can carry counts or other native quantities (for example MAB helpers), so the linked preview now preserves them as **native units** rather than inventing monetary units.
- The linked-source path copy now says **Fee-stream quantity** rather than implying every linked helper is a monetary transaction amount.
- Public `fee_stream_quantities` metadata likewise uses a unit-neutral native-quantity Series label. Series values, stable IDs, cadence, Formula / driver arithmetic, fee economics, and saved Opex inputs are unchanged.

## r126 — Fee-stream quantity native-scale correction
- Fixes the r125 follow-on defect where the Opex linked-source preview label was corrected to `native units` but the public quantity values were still sourced from the historical parity-shaped result tree, which divides ordinary numeric arrays by 1,000. A native quantity such as Migrated MAB = 1,234 could therefore display as 1.234 even though Formula / driver consumed 1,234 internally.
- `run_v2` now publishes `fee_stream_quantities` from the exact base-engine result rather than the parity-converted tree. The public preview and Opex engine therefore observe the same native quantity values.
- Calculation Audit public-result fallbacks now treat fee-stream quantities as native values; monetary throughput is converted to $000s only on monetary audit rows, while counts/native quantities remain unscaled.
- No Fee Product pricing, Opex Formula / driver arithmetic, cadence behavior, stable Series identity, or saved engagement inputs change. Existing Migrated MAB links require no re-entry.
## r128 — fixed-asset Series publication and additive liability formulas
- Corrects the r127 operating-lease overreach. r127 could only link a liability component to aggregate net fixed assets, so a source relationship such as `ROU asset + negative cumulative depreciation` was overstated whenever gross fixed assets also contained unrelated components such as `Total workforce × $800/FTE`.
- Formula / level Fixed Assets now publishes stable downstream Series for the entered base component, each named linked component, aggregate gross fixed assets, accumulated depreciation, and aggregate net fixed assets. Names remain presentation labels; stable IDs own the link contract.
- Other-liability Formula / level now allows each named liability component to contain multiple additive `linked Series × multiplier` terms. Fixed-asset multipliers may be signed. This expresses the source-model lease relationship generically as `ROU × 1 + accumulated depreciation × -1`, while Accounts Payable & Accrued Expenses remains `Total workforce × $/FTE`. The resolved total liability balance still fails closed if negative.
- Saved r127 one-driver components are adapted at runtime without silent storage migration or economic reinterpretation. The legacy net-fixed-asset path remains available only to preserve already-saved r127 economics until the user edits that component.
- Workforce-linked liability terms remain on the engine-native runtime Workforce path so metric-triggered roles do not acquire a false upstream circularity. New Fixed Asset Formula / level Series resolve through the generic Series layer.
- The on-screen Balance Sheet exposes the Fixed Asset Formula / level components, gross PP&E, accumulated depreciation, and net PP&E together, plus named Other-liability components and their multi-term contributions. The Income Statement continues to expose aggregate Depreciation expense; component-specific depreciation is not invented because Fixed Assets does not yet attribute depreciation by component.
- Pre-stamp verification: the complete historical/current matrix passes **37/37** entry points on one unchanged runtime tree in consecutive **19 + 18** batches. Focused Other Liabilities coverage is **21/21**, Other Liabilities UI **7/7**, Fixed Assets **46/46**, Fixed Assets UI **8/8**, Universal Template **60/60**, Series Architecture **40/40**, Fee Suite **54/54**, parity **9/9**, and protocol **332/332**.


## r130 — reversible Other-liability mode + economic fixed-asset labels
- Replaces the one-way **Use Formula / level** activation affordance for Other liabilities with a permanently visible **Flat | Formula / level** mode selector. Users may switch in either direction any number of times; the inactive setup is preserved and becomes active again when selected.
- Backward compatibility is explicit: pre-r130 engagements with no `other_liabilities_mode` remain Flat when no generalized model exists, and remain Formula / level when `other_liabilities_model` already exists. Existing engagements therefore do not silently change economics on load.
- The engine, validation, FIW reviewer summary, and Calculation Audit respect the active liability mode. A saved but inactive Formula / level draft does not override the flat balance or block a Flat-mode run.
- Removes the user-facing placeholder **Linked asset component** from new Fixed Asset Formula / level authoring. New components derive an economic label from their linked Series (for example **Fixed assets · Total workforce**). Historical generic placeholders render through the same driver-derived label without rewriting stable component IDs or authored economics.
- The complete pre-stamp historical/current matrix passes **37/37** entry points on one unchanged runtime tree in consecutive **19 + 18** batches. Focused Other Liabilities coverage is **24/24**, Other Liabilities UI **9/9**, Fixed Assets **47/47**, Fixed Assets UI **9/9**, Universal Template **60/60**, Opex Extensions **116/116**, Series Architecture **40/40**, Fee Suite **54/54**, parity **9/9**, and protocol **332/332**. Python compilation, browser JavaScript syntax, and `git diff --check` are clean.

## r131 — Net fee income as a downstream Opex driver
- Adds a deterministic internal **Net fee income** driver defined as `Total noninterest income − Fee Product Costs`. This does **not** net Fee Product Costs against the regulatory/financial-statement Total noninterest income line; gross noninterest income and Fee Product Costs remain separately presented.
- Surfaces **Net fee income** in Operating Expense linked-source and Formula / driver factor pickers so percentage-based costs such as IP licensing can use the economically correct post-direct-cost base. The existing **Total noninterest income · Call Report** source remains available when gross regulatory income is intentionally desired.
- Same-period ordering is explicit: Fee Product Costs are resolved before downstream corporate Opex, so a 10% IP charge observes the fee base after direct product costs. Any Cost of Risk routed through Fee Product Costs therefore reduces the same base automatically.
- Calculation Audit exposes the gross noninterest-income components, Fee Product Costs, derived Net fee income base, selected rate, and calculated downstream Opex. Profile B follows the same driver contract with zero Fee Product Costs until that profile gains a first-class direct-cost side.
- Regression coverage proves the driver through both ordinary linked Opex and Formula / driver, verifies that financial-statement fee income remains gross, exercises the Calculation Audit disclosure, and keeps cost-pool cycle detection conservative. Pre-stamp historical/current matrix passes **37/37** entry points in consecutive **19 + 18** batches. Focused Opex Extensions are **121/121**, Opex UI **66/66**, Universal Template **60/60**, parity **9/9**, and protocol **332/332**.

## r132 — draggable Product ordering
- Product cards on the **Products** tab can now be dragged into a user-defined order within their economic family: Loans, Deposits, or Off-Balance-Sheet. The category boundary remains structural; dragging cannot silently turn a loan into a deposit or fee product.
- Reordering mutates the underlying saved product array rather than maintaining a cosmetic UI-only list, so downstream per-product views inherit the same authoring order. Aggregate model economics remain order-invariant.
- Drag handles show insertion markers and preserve each card's expanded/collapsed state as the product moves. The focused drag handle also supports arrow-key movement through the same reorder controller.
- Before a reorder, Foundry canonicalizes legacy managed-notional Workforce activation aliases onto their stable Series identities, preventing historical index/name-based references from following the wrong product after a move.
- Regression coverage executes the shipped reorder controller, verifies object identity and card state survive the move, proves cross-family drops are rejected, and proves the Universal fixture's aggregate financial statements are unchanged when each product family is reordered.

## r137 — zero-default funding waterfall assumptions
- New engagements now explicitly initialize Cash floor, Cash yield, Residual securities yield, and Borrowing rate to zero instead of inheriting the populated example bank's 5.0%, 2.5%, 4.0%, and 5.5% assumptions.
- This prevents a new engagement from silently manufacturing required cash, cash interest, residual-securities interest, or borrowing expense before the user authors those economics. The motivating engagement had unsupported M1 cash interest of $50,534 from a hidden 2.5% default applied to average cash.
- Legacy parity import fallbacks now also resolve omitted funding-waterfall assumptions to zero. Explicitly present imported values and values already saved in existing engagements remain unchanged.
- The on-demand example bank retains its explicit example economics; it is not treated as a blank-engagement default.
- Regression coverage verifies all four new-engagement fields and both legacy profile fallback paths. The complete protocol harness passes with the new checks; browser JavaScript syntax and Python compilation are clean.

## r138 — bank EBITDA subtotal

- Adds an explicit **Earnings before D&A and taxes (bank EBITDA)** subtotal to the on-screen Income Statement, Results workbook, Calculation Audit workbook, and Business Plan Tables.
- Computes the subtotal as pre-tax income plus fixed-asset depreciation expense plus separately modeled MSR amortization.
- Keeps interest income and interest expense in the subtotal because they are core bank operating activities.
- Does not change pre-tax income, taxes, net income, equity, or any underlying model economics.
- Includes the undeployed r137 correction that makes cash floor, cash yield, residual securities yield, and borrowing rate default to zero for new engagements and legacy-import fallbacks.

## r139 — interest-bearing balances and remaining net interest income

- Adds an opt-in, zero-default interest-balance model for affiliated-bank cash, operating cash, fiduciary assets under administration, and Federal Reserve Bank stock. Existing Treasury, GSE, and CRA securities economics remain owned by Managed Securities and are not duplicated; absent unsecured-business-loan and zero-valued Deposit Float / Commercial Treasury NII branches remain omitted.
- Affiliated-bank cash is the residual funding-waterfall cash after the required operating-cash balance. Its income uses the authored Scenario Fed Funds path. Operating cash is zero in M1 and thereafter equals an authored percentage of prior-period equity; its income uses its separately authored annual yield.
- Fiduciary non-interest-bearing and interest-bearing AUA are closed equations driven by an entered MAB path or a stable linked Customer Acquisition ending-customer Series. Attach rates and average balances per MAB each retain independent Flat / Growth / Explicit paths. Total fiduciary AUA earns the Scenario Fed Funds rate; only interest-bearing AUA incurs the authored customer cost rate.
- Federal Reserve Bank stock is zero in M1 and thereafter equals an authored percentage of prior-period equity. It is included as a distinct balance-sheet asset and earns its separately authored annual yield. Both equity-linked assets are lagged, avoiding same-period circularity.
- The authoring UI explicitly labels average balance per MAB as dollars, not $000s. Every new field starts at zero; enabling the module does not seed engagement-specific rates, balances, or ratios.
- The Income Statement and export presentation disclose each interest component beneath the canonical cash-interest total and fiduciary customer cost beneath deposit interest. The Balance Sheet discloses affiliated cash, operating cash, and Federal Reserve stock; canonical cash, deposit expense, NII, pretax income, net income, and equity remain the accounting totals consumed downstream.
- Corrects the presentation-layer Total Interest Income subtotal so designated-book interest is not added a second time after already being included in canonical Securities Interest Income.
- Focused regression coverage is 9/9, Managed Securities remains 47/47, Universal Template remains 61/61, cadence/audit remediation remains 88/88, protocol runs clean through T50 and stops at the environment's missing FastAPI dependency in T51, and browser JavaScript syntax, Python compilation, and `git diff --check` are clean.

## r140 — source-faithful interest-income links

- Interest-bearing balances can now consume the canonical quantity Series published by a Transaction Fee stream, including a Migrated MAB stream. The stream remains the sole owner of the customer path; the interest module no longer requires a duplicate pasted schedule or an incorrect total-CAC proxy.
- Adds an explicit model-period control for when affiliated-bank cash begins earning interest. This preserves ordinary M1 behavior by default while allowing source models whose opening/setup month earns no affiliated-cash interest to start in M2.
- Keeps the customer cost rate as the explicit expense assumption on interest-bearing fiduciary AUA and labels MAB as a count in the Calculation Audit instead of `$000s`.
- Regression coverage verifies fee-stream MAB resolution, M1 affiliated-cash suppression, and the new authoring controls in addition to the existing balance and income identities.

## r141 — explicit cash-interest balance basis

- Adds an explicit balance-basis choice for affiliated-bank and operating-cash interest: current period end, prior period end, or the average of prior and current period ends. Existing saved engagements retain current-period-end behavior unless the user changes the setting.
- The source-model configuration uses prior-period-end balances for both cash components. This removes the M2 timing discontinuity without changing rates, inserting plugs, or tuning unrelated assumptions.
- FRB stock remains a current-period balance calculation. Its source-model 0.50% monthly return is entered in Foundry as the economically equivalent 6.00% annual yield.
## r193 — shared-cap editor contrast

- The shared cap is one allocation-group object referenced by each participating lending product. Editing its source or capacity from either card updates the same group.
- On white lending cards, the reusable Series editor now has a light background and legible labels, schedule summary, preview, buttons, and paste area. Dark securities and other dark-surface editors retain their existing theme. This is a presentation-only change.
## r194 — rate sidebar readability

- Widens the desktop assumption sidebar to 400 px and fits numeric inputs within their grid cells. The four-column interest rate table gives its calendar label a stable share of the width, preventing clipped curve values. The small-screen single-column layout remains responsive.
- Presentation only; no rate curves, model assumptions, or calculations change.

## r195 — manual rate edits retain calendar dates

- Editing a quarterly curve cell now retains the dated curve and places every visible grid value at its displayed quarter-end date. Previously the edit deleted dated anchors, causing monthly runs to use an ordinal path two months early and to glide past the final anchor before its displayed date.
- Previously saved manually edited grids without dates are migrated to dated anchors when the configuration loads. Legacy quarterly paths outside this editor retain their existing engine behavior.
- A flat 3.12% SOFR grid through December 2030 now yields 3.12% in every 2030 month, including November and December. Changing a curve can reprice other floating products; compare those runs after deploying.

## r196 — preserve the original curve under manual overrides

- Corrects r195's excessive conversion of every preview grid cell into an anchor. Only explicitly edited cells become calendar-dated anchors; untouched periods continue to interpolate the original policy/SEP curve.
- Migrates saved r194 grids without dates and r195 grids with synthetic quarter anchors using their edited-cell markers. Keeps an original dated-curve snapshot so later edits remain selective.


## r197 — Stable authoring editors

Configuration preview completion now updates read-only workforce, acquisition,
linked-source, and expense summaries in place instead of replacing the editor DOM.
Structural rerenders preserve pending paste text, Load activation, caret selection,
focus, textarea resize and scroll, and viewport position. Load/Append/Clear consume
only the targeted draft; engagement changes discard old transient editor state.

Validation: Node authoring-state regression checks, 23 UI session checks, funded-flow
paste checks, dated-curve checks, JavaScript syntax and diff checks passed. Existing
pastebox inventory gate retains its four pre-existing r196 failures (25 passed).
Playwright browser regression is included but could not run here because the browser
binary download failed; live visual verification remains necessary after deployment.


## r198 — Explicit allocation of unallocated funding

New engagements default to holding unallocated funding in cash. Funding waterfall
exposes Hold in cash / Invest surplus in securities. Authored securities are funded
first, the cash floor remains binding, and funding shortfalls still borrow. Legacy
engagements preserve prior economics on import and save an explicit policy so later
module activation does not change routing. Profile B retains its historical split
until explicitly changed. Policy is validated and editable through FIW CONTROL.

Validation: $30M isolated capital, authored assets, shortfalls, managed policy
independence, profile A/B legacy compatibility, FIW policy edits, UI migration/default
checks passed; all 47 managed-securities checks passed. Legacy parity fixture/hash,
validation and workbook checks passed; broad parity gate still reports pre-existing
unmapped EBITDA and MSR amortization Call Report diagnostics.


## r199 — Klaros graphite theme and staged Configuration workspace

Presentation-only release; no engine, schema, or saved-configuration change.

Theme. The navy/amber palette is remapped to Klaros charcoal, taupe, silver and gold by a
lightness-preserving transform (each colour keeps its OKLCH lightness, so existing contrast
relationships hold). Statement tabs keep light paper surfaces with charcoal headers. Type is
the system UI face on Apple hardware and Inter elsewhere, with tabular figures in fields.

Chrome. Ribbon, cover header and wrapped tab toolbar (about 285px) are replaced by one
two-row application bar (89px): brand, engagement switcher, save state, flags, Export, and a
single-row tab strip with hairline rules between workflow groups. All 15 tabs fit at 1440px.

Assumptions inspector. Global assumptions, rate curves and stress settings move from the
left rail to a right-hand inspector toggled from the bar. It persists across every tab and
the choice is remembered per browser; first visit opens it at 1500px and wider.

Configuration. The three-column grid is replaced by a module navigator (six modules, each
with its state summary and activation switch, plus the staged module's section index) and a
full-width stage that shows one module at a time. Sections open by default. Opex expense
components (formula / driver, tiered / banded, cost pool) are authored directly on the
category; only recognition and cash-settlement timing sit behind a disclosure, which states
its current values when closed. Workforce Advanced trajectories always state Count and
Compensation paths. Loaded explicit schedules show a sparkline preview in open, closed and
collapsed states. Links that acted as buttons are now one button family (secondary, primary
for an armed Load, quiet destructive).

Validation: full Python gate set and Node checks compared line-by-line against the r198
baseline. tests_config_layout rewritten for the staged layout. Four legacy rule strings
that gates pin by colour literal are preserved verbatim and overridden by the design layer.
Visual verification by headless Chromium at 1440, 1600 and 1720px.


## r200 — Light work surface; Configuration master-detail

Presentation-only release; no engine, schema, or saved-configuration change.

Theme. Configuration, the Assumptions inspector and the tab strip move to white working
surfaces on a warm light canvas. Graphite is structure only (application bar, module bands,
detail-panel heads); Klaros gold marks state only (active tab, selected row and module,
activation switch, sparkline). Inline colours in the configuration renderers and the
configuration-only legacy rules are converted by a property-aware transform (surfaces and
rules flip lightness, dark text already on light stays, accents deepen to read on white).
Statement tabs keep their paper tables. The analysis and record tabs (Executive Summary,
Peer Cohort, Examiner Book, Assumption Book, Governance, Start, Lab) remain graphite.

Configuration. Module rail shows status dots; the activation switch moved into the module
band. Operating expense gains a KPI strip (first-period workforce and category totals from
the latest run, population/category and component/schedule counts) and sub-tabs
(Workforce / Expense categories / Assessments). Workforce populations and expense
categories are master-detail: a dense grid of all records beside the selected record's
editor. Selection follows object identity, so adds, deletes and drag reorders keep the right
record open; new records open automatically. Category drag-to-reorder moved to the grid.
Component tools (formula / driver, tiered / banded, cost pool) are cards inside the
selected category.

Validation: full gate set compared line-by-line with r198/r199; tests_config_layout extended
with six r200 checks. Headless Chromium at 1440 and 1600px, inspector open and closed.


## r201 — Analysis and record tabs on the light surface

Presentation-only release; no engine, schema, or saved-configuration change.

Executive Summary, Peer Cohort, Examiner Book, Assumption Book, Governance, Start and Bank
Design Lab move from the dark cover theme to the light work surface. Only the Welcome landing
stays dark. Inline colours in 44 renderers, plus the Executive Summary, Notes and stress
callout branches of _renderContentBody, are converted by the same property-aware transform as
r200, extended to SVG and canvas attributes (fill, stroke, fillStyle, strokeStyle). Every
converted function is identical to r200 apart from colour literals. The statement branches of
_renderContentBody are untouched.

Dark surfaces map to near-white tiers rather than mid grey. Section headers (ovh2) are
graphite bands; KPI tiles and flags are white with hairlines; analysis data tables use
proportional tabular figures with Capital IQ grid heads. Lab heatmaps (3D surface and
contour) use a champagne-to-gold ramp in place of blue-to-green.

Validation: full gate set compared with the r198 baseline; tests_config_layout extended with
four r201 checks. Headless Chromium at 1440px on all seven tabs; Lab sensitivity run live,
trade-off surface and contour rendered from a synthetic 9x9 grid (the example bank exposes a
single lever).


## r202 — Finish: remaining editors, account page, exhibits

Presentation-only release; no engine, schema, or saved-configuration change.

Managed-portfolio securities and acquisition channels are master-detail, matching Workforce
and Expense categories: a grid of records beside (channels) or above (securities, which sit
in a half-width column) the selected record's editor. Channel drag-to-reorder moved to the
grid. Newly added records open automatically.

The /account page is rebuilt as a light Klaros page (graphite bar, white cards, gold focus).
Excel exhibit writers (excelio, audit_workbook, bpt_cover) move from navy to graphite and
Klaros gold for header fills, rules and muted text. Blue inputs, green links and red checks
keep the modeling convention.

Unchanged by design: the Welcome landing (dark brand page) and the frozen /v1 console.

Validation: full gate set compared with the r198 baseline; tests_config_layout extended with
two r202 checks; exhibit workbooks regenerated and opened.


## r203 — Welcome on the light surface

Presentation-only release. The Welcome landing, the last dark page in the console, moves to
the light surface: a light hero with a graphite primary action and a graphite panel that
names what the platform contains (taken from the actual tabs). The redundant in-page brand
row and placeholder mark are removed; the application bar carries the Klaros mark. While on
Welcome, engagement controls (switcher, save state, flags, Assumptions, Export) are hidden.
Every id, handler and line of copy used by sign-in, Enter platform, sign-out and account
recovery is unchanged. The frozen /v1 console is untouched by design.


## r204 — Klaros ledger palette and Products workspace

Presentation-only release; no engine, schema, or saved-configuration change. Built on the
deployed tree (9e47864, byte-identical to r203).

Palette. Graphite is #2C2C2C (neutral, not black) and now carries both application-bar rows;
tab labels are white with a gold underline. Klaros gold is #DBAB5D, with light washes from the
Klaros gold strip (#FAF1DE). Every neutral in the console is re-toned to a true grey, removing
the warm pink cast of r199 to r203; pale pink washes become cream and alarm reds become brick.
The account page, build stamp and Excel exhibits (audit workbook, BPT cover, workbook export)
use the same palette.

Ledger geometry. Radii are 2 to 3px throughout, legacy and inline styles included; data grids
carry hairline column rules; panels drop soft shadows.

Products. The tab is a product navigator (search, families, 12Q revenue, drag reorder via the
existing handlers) beside one workspace:
- Portfolio: KPI strip, one graphite-banded ledger per family with share of family and
  contribution, and a Notes column that flags identical explicit schedules loaded separately
  in more than one product (read-only scan).
- Compare: products of one family side by side (stream bases, drivers, pricing, cost side,
  off-book balance source, latest-run balance, revenue, contribution).
- Product: graphite header with the existing per-product KPIs, and Setup / Fee streams /
  Per-month overrides tabs. Fee streams are master-detail: a grid of streams, a driver chain
  built from stream references, and the selected stream's existing six-axis editor split into
  Activity / Pricing / Timing / Costs by the editor's own axis boundaries.
Every editor is the unchanged product card and stream editor; tabs are sections toggled by
markup only, so lending, deposit, legacy notional and fee products, and every stream basis and
driver source, keep their behaviour. Stream removal from the detail header asks for confirmation.

Validation: full gate set compared line-by-line with the r198 baseline; tests_config_layout
extended to 35 checks (five new for r204). Headless Chromium at 1440px on the universal template
bank (six fee products, stream-to-stream references): every family rendered with balanced
sections, stream add auto-selects, field edits persist with selection and tab kept, no page errors.


## r205 — Stream workspace to the approved mockup

Presentation-only release on r204; no engine, schema, or saved-configuration change.

Fee streams tab. A product-level driver chain sits above the streams, built from stream
references, naming the streams outside it. The stream grid and the selected stream's editor sit
side by side when the workspace is at least 1000px wide, stacked below that. Grid columns: Role
(Revenue if any price parameter is non-zero, else Driver: a quantity carried at a zero price),
Driven by, and the engine's own last-period quantity for the stream (fee_stream_quantities) with
a sparkline in the stacked layout. Per-stream revenue is not shown because the run results do not
carry it.

Editor. The unchanged six-axis editor is restyled: sentence-case labels, uniform 30px controls
at full field width, multi-control rows (growth rate, period, method, anchor) on one line, and
standalone explanatory memos folded into one "About these settings" note per tab. Explicit
schedules show a six-cell strip (first three and last three values) with display-only rounding;
stored values keep full precision.

Product header carries a breadcrumb back to the portfolio. A stream rename mirrors into the
header and grid as you type.

Validation: full gate set matches the r198 baseline; tests_config_layout at 39 checks (four new).
Headless Chromium at 1440px: every product family renders with balanced sections, stream add
auto-selects, field edits persist with selection and tab kept, no page errors.


## r206 — One side-column pattern for Configuration and Products

Presentation-only release on r205; no engine, schema, or saved-configuration change.

Configuration takes Products' side column: full height from the application bar, #EDEEEC with a
hairline right border, the page title at its head. The onboarding nudge and footer move inside
the workspace after render (cfgArrangeShell) so the column is never interrupted.

Products takes Configuration's elevated navigator: a white bordered card holding family
headings (collapsible, with counts) and product rows with an icon tile per family, the product
name, a sub-line (fee-stream count, or Q12 balance for lending and deposits) and 12Q revenue.
The selected row carries the gold wash, gold bar and graphite icon tile used by Configuration.
Search, drag reorder and selection are unchanged.

Validation: full gate set matches the r198 baseline; tests_config_layout at 41 checks (two new).


## r207 — Product tab fixes: figures during incomplete inputs, add-stream cards, field sizing

Presentation-only release on r206; no engine, schema, or saved-configuration change.

Figures while inputs are incomplete. Lending and deposit presets arrive missing required fields
(for example charge_off_ann, rate_paid_ann). The engine answers with open questions (HTTP 422)
and, by design, returns no run, which blanked every figure in the navigator. The Products tab now
keeps the last complete run for the same engagement on screen, muted, with a banner that names
the open inputs. Products with open questions read "Needs inputs" and show a dash, never a
borrowed figure. Figures refresh when the inputs are complete. The engine's fail-closed rule is
unchanged; nothing downstream uses the cached figures.

Add-stream tiles. The five basis tiles are option cards: icon tile, title, one-line description,
and a "+" affordance, laid five across on wide stages. The canonical definitions stay in the info
popover; the tile markup keeps the classes, help text and toggle behaviour the gates pin.

Field sizing. Product card fields flow in columns of at least 280px (at most 1180px wide);
numeric inputs cap at 180px, selects at 380px, text at 520px, paste boxes at 760px.

Validation: full gate set matches the r198 baseline; tests_config_layout at 44 checks (three new).
Live checks: adding lending and deposit presets keeps other figures and names the open inputs;
removing the product restores normal display; option cards add the right stream basis.


## r208 — Checkboxes keep their natural size

Presentation-only release on r207. The legacy rule ".fld input{width:100%}", written for text
boxes, also stretched checkboxes and radios inside fields: the "Apply Durbin debit-interchange
cap" checkbox rendered 530px wide with its label squeezed off the right edge. Checkboxes and
radios now keep their natural size and sit beside their labels, everywhere in the workspace and
the Assumptions panel. A sweep of 95 views (every product, stream and stream tab, all
Configuration modules, Stress, Lab, Governance, Start) found no other stretched control.


## r209 — Klaros theme colours and a uniform page header

Presentation-only release on r208. Graphite bars (application bar, tab row, title bands, detail
heads) are unchanged.

Theme. Every non-graphite surface follows the Klaros pro-forma theme: white page (including the
legacy "paper" token on statement and record tabs), #343434 ink, #666666 labels, #96928C muted
text, #D8D8D8 rules, #C4C4C4 control borders, #EFEFEF side columns and stripes, #DFB367 gold for
accents and focus, #D3A157 / #BF975E gold buttons, #EAD8BC champagne chips and selection washes,
#B0413E alarm red. A 3px gold gradient accent bar sits under the tab row; Assumptions cards,
banners and flags carry the theme's 4px gold left edge. Button text stays #343434 rather than the
theme's white, for legibility on gold.

Page header. Every tab except Welcome opens with a breadcrumb (group / tab, or tab / section) and
a graphite title band set below the menu: Configuration / module, Products / Portfolio, Compare
or family / product, Statements / Balance Sheet, Analysis / Executive Summary, Record /
Assumption Book, and so on. Applied after each render by a small observer; tab content is
untouched apart from the first heading becoming the band.

Validation: full gate set matches the r198 baseline; tests_config_layout at 46 checks.


## r210 — Klaros-gold strip under the menu

Presentation-only release on r209. The 3px gradient accent under the menu becomes a 6px solid
Klaros-gold (#DFB367) strip, built into the bar as its bottom border so page content and the
sticky side columns start below it (sticky offset 96px, the bar's measured height).


## r211 — Welcome on the Klaros cover image

Presentation-only release on r210. The Welcome page uses the Klaros cover image (2341x1314, deck
title removed, embedded as a 253 KB JPEG). Layout follows the image's own blocks, positioned in
image pixels and scaled with the page width:
- Graphite block: eyebrow, headline and subtitle under the Klaros Group logo; the headline is
  optically centred between eyebrow and subtitle (24px above and below at 1440px).
- Gold strip: sign-in drawn directly on the strip (no card): heading, white fields, graphite
  Enter platform button, account recovery. Signed in, the same area reads "Welcome back".
- Building: "One model, every exhibit" as an index ribbon of four numbered columns on a graphite
  fade; the fourth is renamed "Peer and vintage analysis" with a matching description.
Below 1000px wide the image's top band becomes a banner and the hero, sign-in and ribbon stack.
Every sign-in id, handler and string the gates pin is unchanged; sign-in tested end to end at
1440, 1920 and 900px.


## r212 — Narrow Welcome over the photograph

Presentation-only release on r211. Below 1000px wide (browser zoom, half-screen windows,
tablets) the Welcome page no longer drops the photograph: the image's top band with the logo is
the banner, and the building runs behind the stacked headline, a translucent-gold sign-in panel
and the graphite-fade index ribbon. The image is held once in a CSS custom property and shared
by every layer. 1440px and 1920px renders are pixel-identical to r211.


## r213 — Sign-in fields sized for a username

Presentation-only release on r212. Sign-in fields cap at 300px at every width (were 420px in the
narrow layout and 367px at 1920px; 1440px is unchanged at 276px and pixel-identical to r211). In
the narrow layout the translucent-gold sign-in panel is a compact 344px strip with the building
beside it, echoing the desktop composition.


## r214 — Sign-in fields match the Enter platform button

Presentation-only release on r213. Username, password and Enter platform share one 162px column
(same left edge, same width) at every window size; the button's width is fixed with its label
centred so the match holds across system fonts. The narrow-layout gold panel fits its contents.


## r215 — Welcome recomposed: smaller graphite, refined headline

Presentation-only release on r214. The Welcome page is composed from the Klaros cover image's
parts instead of one fixed picture, so the graphite block can be sized: 50% wide by 40% tall
(was about 75% by 48%). The graphite is a CSS gradient sampled from the image; the Klaros Group
logo is lifted onto a transparent background; sky, gold strip and building are separate crops
(black edge rows trimmed). The headline is semibold, one line, and fitted on the live page so it
ends exactly where the subtitle ends (within 2px at 1440 and 1920) on any system font. Gaps
above and below the headline are equal: 25px at 1440, 36px at 1920. Sign-in and the index ribbon
keep their approved sizes. Narrow layout: the building is the backdrop and the logo sits in the
graphite hero. Sign-in tested end to end at 1440, 1920 and 900px.


## r216 — Customer-acquisition audit view as a ruled ledger table

Presentation-only release on r215. The calculated customer-base roll-forward is a fully ruled
table (horizontal and vertical lines) sized to its content: 583px wide instead of the full
1,034px panel, first column 190px instead of 478px. Year headers are right-aligned over their
figures (they were left-aligned over right-aligned numbers); the long first header wraps rather
than widening its column. Ending bank customers and Ending AUC are bold under a dark rule;
alternate rows carry a faint stripe. Header wording and figures are unchanged.


## r217 — Sign-in: underlined fields, floating labels, "User access"

Presentation-only release on r216. The sign-in fields are underlined (no boxes on the gold strip)
with floating labels: "Username" and "Password" sit in the field and lift to small capitals as
you type, so the labels stay visible once filled. The password has a show/hide eye, and a
"Caps Lock is on" warning appears while Caps Lock is on (cleared on release or leaving the field).
The "Sign in" / "Welcome back" heading is replaced in both states by a small-caps "User access"
label, matching the page's other zone labels; screen readers still announce the region as
"Sign in". Field ids, handlers and the 162px field width are unchanged. Tested at 1440, 1920
and 900px: label lift, show/hide, Caps Lock, Enter to submit, wrong-password error, real sign-in.


## r218 — Product list drag-to-reorder restored as a proper slide

Presentation-only release on r217. Reordering still uses the existing productDrop logic, but the
interaction was rebuilt for the vertical product list: the whole row is the handle (the grip is a
constant visual cue, not the only target); the row itself follows the pointer while dragging and
the original dims; the gold drop line sits above or below the target row according to its top or
bottom half only (the old card-grid rule also used left/right, which mis-placed drops in a list).
A plain click still selects the product; drops across families are still refused.


## r219 — Fee-stream driver figures with their working shown

Presentation-only release on r218. The fee-stream grid's "Quantity, last period" column becomes
"Driver · M36" (the model's actual final period: M, Q or Y). Values are shown in the editor's
units: money in $000s (the engine's quantity series is in plain units, so 51,599,500 now reads
51,599.5), counts as accounts, customers or units. Units mirror the engine's own classifier
(income_modules._fee_stream_quantity_kinds), including inheritance through stream references.
A second line shows the working: "entered · M36 of your schedule", "= 80% × 51,599.5 ·
<source>", "= 116.6 per account × 240", "= 2× 240", or the feed the stream draws on. Ratios are
computed from the engine's final-period figures (stream ÷ source), so the line always agrees
with the number above it; the source name links to that stream. The editor's Activity tab shows
the same working above the fields (and, for a source, which streams it drives). Notes folded into
"About these settings" now form one box per tab.


## r220 — Driver sources and exact working for feed-driven streams

Presentation-only release on r219. Accuracy rule: every figure shown is read from the run.
- Source rows (◆) open the fee-stream grid when a stream draws on them: AUC (the per-product
  average AUC the engine applied, results.products[].managedNotionalAvg, with month-end alongside
  to tie to the feed's Ending AUC) and Customers (the feed's period-end, average or year-end count,
  matched to the stream's measure). Feeds referenced by id are resolved to their names.
- AUC-driven streams show their rate in authored terms: "= 9 turns/yr ÷ 12 × AUC",
  "= 5%/yr ÷ 12 × AUC", "= 30% × AUC" (rates with growth show the rate in force). Rates are
  stream ÷ AUC from the engine's figures, labelled with the schedule's own period ("(Y7)").
- Entered schedules name the schedule's own period ("Y7 of your schedule"); fixed and one-time
  streams say "no volume driver"; the driver chain starts from its source (AUC → stream).
Verified: every figure on a test product (turns, flow %, stock %, fixed, yearly account
schedule, average customers) recomputed independently from the engine: 11 of 11 match.


## r221 — Customer acquisition: intra-period path options (engine)

Engine release on r220. Each acquisition feed gains three optional settings; absent keys reproduce
the historical calculation byte for byte (full-results sha256 identical on every runnable
configuration before and after).
- intra_period_path: monthly_flows (default) | straight_line
- path_anchor (straight_line only): year (default) | quarter. Month-ends are not offered.
- attrition_timing (monthly_flows only): period_end (default) | spread | period_start. Timing moves
  only the month in which each attrition period's loss lands; amount, basis (book at the period's
  start), rate and ticket are unchanged. With monthly attrition every timing is identical.
Straight-line paths interpolate between the default calculation's anchor balances and record the
implied monthly loss so beginning + new − lost = end holds in every month. With a non-default option
the feed also publishes pathComparison (default vs chosen yearly averages) for the authoring screen.
UI: Configuration → Customer acquisition → each feed, directly under Existing-book attrition.
Validation (foundry/v2/tests_cac_intra_period.py, 66 checks): Engagement B (1.5% monthly churn,
spend ÷ CAC) reproduces its source in all 36 months under every timing; Engagement A (annual
attrition) on straight line / year-ends reproduces its source's monthly averages (Year 1 exact,
Year 7 within input rounding); invariants, closed forms, quarterly engine cadence, end-to-end fee
consumption, and rejection of invalid values.


## r222 — Calculation cards; decluttered stream grid; r221 path row without defaults

Presentation release on r221 plus one read-only API route. Run results are unchanged.
- Fee-stream grid: one line per figure (value, unit, ⓘ). Hovering the figure shows its working;
  clicking the figure or ⓘ pins it; Esc or an outside click closes; keyboard focus also shows it.
  Clicking a figure does not change the selected stream; clicking elsewhere on the row still does.
- Cards and the editor's Activity line are rendered from the same structured steps (operation,
  label, value, total), so they cannot disagree. ◆ Source rows show one number (the AUC the
  engine uses); the card explains average vs month-end AUC and links to the feed roll-forward.
- Intra-period path row: no "(default)" labels and no default/non-default tag; the options are
  alternative conventions. Its ⓘ card shows average AUC (or customers) by year under every option
  side by side, with the one in use marked, computed on demand by POST /api/v31/cac/path-options
  (cac_feeder.path_option_comparison, identical to the engine for the option in use).


## r223 — Remove the intra-period option comparison

Release on r222. The option-comparison card, its API route (/api/v31/cac/path-options) and function,
the engine's extra default-path calculation (pathComparison, computed on every run with a non-default
option) and the post-run refresh hook are removed: none answered a user need, and a user who wants a
comparison switches the option and reads the results. The intra-period path row keeps only its
controls (Path, Anchor points, Attrition timing). The stream and source calculation cards from r222
are unchanged. Results at the defaults remain byte-identical to pre-r221.


## r224 — Attrition within the period: one control in the attrition box

Presentation release on r223. The separate "Intra-period path" box (Path, Anchor points, Attrition
timing) is replaced by one dropdown, "Attrition within the period", inside the Existing-book
attrition box: taken at the end / spread evenly / taken at the start of each attrition period;
straight line between year-ends / quarter-ends. Stored as the r221 keys (end of period = no keys),
so the engine, its tests and saved engagements are unchanged. With monthly attrition a one-line note
says the first three options give the same result. The attrition box is sized to its contents.


## r225 — Attrition Path and Timing as two controls; cards on click only

Presentation release on r224. In the Existing-book attrition box, the single list is split into its
two dimensions: Path (Monthly flows / Straight line between year-ends / quarter-ends) and Timing
(at the end / spread evenly / at the start of each attrition period). Timing is shown whenever the
path is monthly flows; with monthly attrition it stays usable with a note that it has no effect.
Stored as the r221 keys; engine and results unchanged. Calculation cards open on click (or Enter)
and close on Esc or a click elsewhere; hover and show-on-focus are removed.


## r226 — Measured widths across Configuration, notices and editors

Presentation release on r225. Width rules from a measured sweep of every tab and Configuration module:
- Forms: dropdowns and text fields up to 320px, numbers 180px, names 420px, paste boxes 760px; rows,
  setting boxes and control-only sections sized to their content.
- Master-detail (channels, workforce, …): list column up to 640px and detail 400–760px, left-aligned,
  so at 2560px the pair stops at about 1,400px instead of filling the stage; stacked layouts
  (securities) size list and detail to content.
- Warnings, flags and banners sized to their text, capped at 880px.
Sweep results at 1440px: fields wider than 360px 26 → 16 (remaining are paste/name fields within
caps); non-text boxes using under 60% of their width 8 → 0; master-detail Securities 1000 → 688px.


## r227 — Tight without truncation

Presentation release on r226, correcting over-squeezed controls. Measured truncation (selected text
or value not fitting its control) across all Configuration modules, every acquisition channel, the
product editors and the remaining tabs: 31 at 1440 and 1920px before, 0 after.
- fitControls(): after every render of the work area, each dropdown gets a minimum width that fits
  its widest option (stable across selections) and each name input one that fits its text, up to
  420px (it also grows while typing). Controls are only ever widened.
- The 320px dropdown cap is removed (dropdowns are bounded by their container instead).
- Master-detail: side by side from 1400px of stage width (list up to 640px, detail 480-880px);
  below that, stacked (list up to 640px above a detail card up to 880px), so rows no longer wrap
  at 1440px.


## r228 — One place for the working; figures stay current

Presentation release on r227.
- The stream editor's Activity working block is removed: it repeated the ⓘ card for the selected
  stream and was not redrawn after edits, so it could show superseded figures.
- Grid figures and ◆ source rows are now refreshed in place after every run (refreshStreamFigures),
  without redrawing the editor being typed in; the ⓘ card therefore always reflects the latest run.
  Previously both the grid figure and the editor block kept the values from when the stream was
  selected (e.g. 240 accounts after an edit had made it 480).
- Only the ⓘ opens a calculation card; figures carry no underline and are not clickable.


## r229 — No flicker on redraw

Presentation fix on r228. Toggling an option that redraws the Configuration stage (e.g. straight line
between year-ends ↔ quarter-ends) briefly showed dropdowns at their unfitted widths: measured frame by
frame, total dropdown width dropped 18px for ~50-80ms before r227's fitting pass widened them again on
a 40ms timer. fitControls now runs in the mutation callback itself (a microtask before paint), so a
redrawn control is never painted unfitted. Frame-by-frame probe after the change: no movement.


## r230 — Workforce role card

Presentation release on r229, scoped to the box the user identified (Operating expense → workforce role
card). The Compensation row no longer splits the card into three equal thirds (279px each at 1440px):
amount 140px, Per FTE and unit dropdowns fitted to their options (97px, 99px). The role field grid uses
columns of at most 340px and 300px, left-aligned (End and Benefits move from 429px to 352px).
Fitting fixes found while doing it: fitControls now applies its minimum with priority (an older
".wf-comp-value select{min-width:0!important}" had been cancelling it), and also runs when a
Configuration module is selected or a collapsible section is opened (controls drawn while hidden could
not be measured). Truncated controls remain 0 at 1440 and 1920px; the r229 no-flicker probe is unchanged.


## r231a_fix1 — Corrected deposit balance sources and shared retention pools

Validation build on r230-compatible history: r230 `1c3e67d` → r231a `30f7ad8` → this fix.
No r231 deployment is required. r230 remains the last good deployment and rollback baseline.
Incorporates the r231b fingerprint and opening-label corrections, with these further fixes:
- Full legacy output comparison; three r230 public fingerprints and actual frozen verification pass.
- Product Details resolves SOFR/EFFR/Prime from configuration without changing old hashed outputs.
  Resolution follows each engine's family/input order; duplicate names do not select another index.
- New pools explicitly author average swept-balance fees. Configurations without a basis keep r231a
  period-end fees. Opening swept balance is independent and defaults to zero, not period-1 ending.
- Average basis, beginning swept balance and fee are exported for independent audit reconciliation.
- Level/pool retained opening label states that it is before period 1; existing accounting is preserved.
- Equity capacity control says "Equity allocation ratio" and explicitly describes an allocation budget,
  not an enforceable capital/assets constraint. Financial formula unchanged; full capital constraint work
  remains separate. No engagement-specific formula or new deposit product type is introduced.

See DEPOSIT_FIX1_VALIDATION.md for manual checks and full-suite results.

## r231a_fix2 — Unified fee default and atomic pool-mode transitions

History: r230 → r231a → r231a_fix1 → r231a_fix2. Last good deployment remains r230.
- Average swept-balance fee is the only default, including imported pools without a setting.
  Period-end remains available explicitly; r231a was never deployed and needs no fallback.
- Switching a deposit to pool mode creates or attaches a pool in the same action, before preview.
  A sole existing pool is selected; with multiple pools a new independent pool is created.
  New member shares start at zero when the pool already has members.
- Five transition previews tested against the actual API all return 200; one request per action.
- Full inventory includes Python and CJS scripts: 56 entry points, 46 pass / 10 baseline failures.
  No new failing entry points against r230. See DEPOSIT_FIX1_VALIDATION.md for details.

## r231a_fix3 — Clarify outbound sweep labels

Presentation-only iteration on fix2. Pool preview and Product Detail use "Swept out (off-book)"
and "Fee on swept-out balances"; the audit labels match. Series keys stay sweptBalance and
sweepFee. Source guidance asks for gross program balance before retention/capacity limits,
not deposits already expected to remain on-book. Deposit presets and calculation logic unchanged.


## r232 — Fee streams on loans and deposits

Built on r231a_fix3 (6f00909). Results are identical to fix3 for every runnable configuration.
- Loans and deposits get the Fee streams tab fee products already have: the same stream grid, ⓘ calculation
  cards and Activity / Pricing / Timing / Costs editor. The engine already executed their streams (the
  template's Commercial Real Estate loan carries "CRE servicing fee", which moved revenue but was not shown
  anywhere on screen).
- One shared stream workspace (_feeStreamsSectionHtml), lifted unchanged out of the fee-product form; stream
  handlers resolve their product through _stOwner (fee product index unchanged; 1000+i loans; 2000+i
  deposits). All 32 fee-product views render identically to fix3.
- The Setup fee yield is listed read-only beside the streams on loans and deposits ("Fee yield · SETUP"),
  with its own card (yield ÷ periods × average balance), so all fee income is visible in one list. It is
  still authored in Setup → Pricing. Shown even when a product has no streams yet.
- A balance stream added to a loan or deposit starts on the product's own balance (fee products keep AUC).
- Guide Me remains a fee-product tool.
- Validation: deposit fee streams are now validated like loan streams (malformed streams and the
  loan-only funded-flow source are rejected).


## r233 — Loan and deposit Setup grouped by concern

Presentation release on r232. Results are identical to r232 for every runnable configuration.
- Loan Setup: Name and Call Report line above tabs Balance · Pricing · Timing · Credit · Costs; deposit
  Setup: Balance · Pricing · Timing · Costs. The same tab style as the stream editor, each tab with a
  one-line summary from the product's settings (refreshed after every edit). Only tabs with fields appear.
- Deposit balance methods: the Balance tab holds the method's own fields, including r231a's pool picker,
  retained share, pool settings and opening swept-out balance (plan item C).
- Fields are classified by the configuration path they write to and moved, never rewritten; groups are
  display:contents wrappers inside the existing form grid. Unclassifiable fields stay visible below the tabs.
  Grouping runs before paint (first painted frame already grouped). The open tab is remembered per family.
- Funded-flow loans keep their existing sectioned layout. Fee products' 4-field Setup is unchanged.
Verification: every Setup field present exactly once in all 24 loan / deposit / balance-method views
(same fields as r232); 54 tab views at 1440 and 1024px with each field visible in exactly one tab, no
truncation and no overflow; fee-product screens identical to r232 apart from the card's new data-fam /
data-i attributes; full results identical; fingerprints 3 of 3.


## r234 — Workforce role fields and run summary

Presentation release on r233. Results identical to r233.
- Workforce role card entry fields restyled toward the Design reference: two rows (Role / population ·
  Count · Compensation; Start · End month · Escalation % · Benefits / payroll %), uniform 32px controls with
  small labels above, numbers right-aligned in tabular figures, units moved into labels, "month" between the
  start mode and number, "Open" for an open end month, and a same-height "Set by path" box where escalation
  is managed by the compensation path. Scoped to .wf-role-card; Advanced trajectories unchanged.
- Workforce run summary table sized to its content (about 1,000px instead of the full stage width).
Verification: two rows and 32px controls on every role at 1440 and 1920px, no truncation; every role field
still writes to the configuration; the other five Configuration modules are pixel-identical to r233.
Test note: tests_growth_ui has stopped early since the original r198 build because it passes over 131,072
bytes of console source to Node as one command-line argument (143,874 bytes in r198; 169,869 now), so its
later checks never run (it is one of the ten baseline failures). Run once through standard input, r233 and
r234 both pass 67 and fail the same 17 pre-existing checks; r234's only effect there was the escalation label
pin, updated to "Escalation %". Repairing the harness and the 17 decayed checks is left for its own release.


## r235 — Every prepopulated box shows its full value; trigger under Start

Presentation release on r234. Results identical to r234.
- Root cause of clipped boxes ("Metric trigge", "Hire anniversar"): the r227 fitter measured text on a canvas
  using the control's computed "font" shorthand, which Chrome reports as "" when font features (tabular
  figures) are set, so it measured in 10px sans-serif and under-sized controls by about a quarter (e.g. 73px
  vs 100px rendered for "Hire anniversary"). The fitter now measures with an off-screen element styled like
  the control (exact rendering), fits number inputs and placeholders as well as text inputs, re-fits when
  web fonts (Inter) finish loading, and lets a field whose value cannot fit its column span the grid row.
- The truncation audit had the same canvas flaw and under-reported. Re-measured by rendering, with Inter
  served as in production: r234 had 33 clipped controls (19 distinct) across Capital, Operating expense,
  Customer acquisition, Tax and the product stream editor; r235 has 0 at 1440 and 1920px, with no sideways
  page scroll and no control past its card on any screen.
- Workforce: the activation Trigger row (metric, operator, value) moved from below Advanced trajectories to
  directly under the Start row that enables it, styled like the fields above.


## r236 — Toggles, action order, component buttons, role reordering

Presentation release on r235. Results identical to r235.
1. Segmented toggles show the selected option filled (graphite, white text), matching Products' Portfolio |
   Compare. Found by scanning every screen: Operating expense (Simple overhead | Detailed), Capital
   (Formula / level | Asset schedule) and Securities (Flat | Formula / level) all shared the white-on-grey style.
2. Add comes before Paste everywhere it pairs: roles, categories, fixed assets, pre-opening expenses.
3. Additive expense components are slim pill buttons (+ Formula · + Tiered bands · + Cost pool) with their
   descriptions as tooltips. Disclosure summaries (Advanced timing, Advanced trajectories, ...) are quiet
   inline text with thin dividers instead of grey boxes.
4. Workforce roles reorder by drag, like categories. Selection follows the role; Advanced-trajectories state
   is keyed by series id; engine outputs are unaffected (26 statement series identical after a reorder).


## r237 — Operating expense scope card

Presentation release on r236. The "Populations / categories 10 / 18" card now reads "10 workforce
populations · 18 expense categories" (singular forms when a count is 1), large numbers with small words as in
the other KPI cards. That card gets a 1.45 share of the KPI strip so the phrase stays on one line at 1440px;
each half wraps as a unit on narrower screens. Its value aligns with the neighbouring cards.


## r238 — Lists use the room they need

Presentation release on r237. The r226/r227 640px cap on list columns made the Operating expense categories
table (714px) scroll horizontally at every screen width, while the detail card left space unused; the
workforce roles table (646px, after r236's drag column) scrolled by 6px. After each fit, a list whose table
overflows now gets exactly the table's width when the screen has room: side by side, the detail card moves
right and keeps 480-880px; stacked, the list's cap rises to the table width. Too-narrow screens still scroll
rather than squeeze the detail card. The fit also re-runs when an Operating expense sub-tab or a product tab is
selected (those reveal panels drawn while hidden). Measured at 1440, 1920 and 2560px: no list scrolls.


## r240 — Peer Cohort: faster, steadier, redesigned, exportable

Built on r238 (r239 was a separate build that was rolled back; numbering skips it to avoid confusion).
Pro forma engine untouched; run results identical.
Reliability and speed
- The corridor made one request per metric (about seven at once), each needing two or more queries on a small
  bounded connection pool; some queued past the 15-second timeout and failed at random. It now makes ONE
  request: /api/v31/peer-bands/batch runs the existing single-metric handlers one after another (identical
  output), retries once on a transient 502/503, and caches successes for 30 minutes. Peer data do not change
  with the model, so the browser also keeps them for the session: re-renders and model reruns issue no queries.
Min and max of the comparison set
- Curated and lending cohorts: MIN/MAX added to the existing percentile queries (same rows).
- Stored asset bands (pre-aggregated, no extremes): one streaming MIN/MAX over the band's current members,
  withheld with a note if it contradicts the stored percentiles. Vintage ages gain min/max (same values,
  same suppression); curated vintage results include each bank's series by age for the workbook.
Redesign (from the Claude Design proposal, with the requested change)
- Summary cards (inside P25-P75, outside P10-P90, better than median given direction, awaiting data); one row
  per metric with a band strip (P10-P90, P25-P75, median, min/max ticks, modeled dot); the comparison set's
  Min / P10 / P25 / P50 / P75 / P90 / Max with each label ABOVE its value; n; the modeled value stacked over
  its placement and Q12 standalone figure. Vintage tables gain Max and Min rows.
Excel export (Download Excel)
- Built from what the page already holds, so it never re-queries the substrate. Curated cohorts (up to 25
  banks with series): one column per peer per age with min/percentiles/median/max/n and placement as live
  formulas (the template's design, without its #VALUE! titles or the Tier1_RBR column shift). Larger cohorts:
  the distribution per age (n, min, P10-P90, max) plus placement formulas and a Members sheet. Arial, inputs
  blue, formulas black; recalculated with zero errors in testing. File named in Central time.


## r241 — Peer Cohort refinements

Built on r240. Pro forma engine untouched; run results identical.
- Peer corridor bounded to 1180px (strip column at most 320px), so it no longer fills the screen; thin dividers
  between the percentiles, slightly stronger around P10-P90, Min/Max muted.
- Vintage corridor follows the peer cohort. Previously any asset band fell back to "all 2018-2023 charters"
  and an existing corridor was never rebuilt on a cohort switch. Now the request carries the asset band
  (membership: 2018-2023 charters at their current size in that band), the corridor records which cohort it
  belongs to, and a cohort switch rebuilds it. Both vintage endpoints cache results for 30 minutes.
- Vintage metric headings: graphite band, mixed case at about 1.5x size, at least a third of the width (a
  separator, never a full-width rule); the capital footnote sits beneath in small muted text.
- A plot beside each vintage table: min-max range, P25-P75, median, and the modeled bank.
- Excel: a line chart beside each corridor sheet's table and a Charts sheet gathering them (min/max dashed
  grey, P25/P75 gold, median graphite, modeled thick gold with markers). Ages without peer observations are
  left blank so charts show gaps, not false zeros. Sheet and chart names in mixed case.


## r242 — Peer Cohort: width, vintage cohort binding, plot fit

Built on r241. Pro forma engine untouched; run results identical.
- Peer corridor width is exactly halfway between r240 (full width) and r241 (1180px) at every screen size:
  max-width calc((100% + 1076px) / 2). Measured strip widths 421 / 661 / 981 px at 1440 / 1920 / 2560,
  the midpoints of r240 and r241. Percentile delineation unchanged.
- Vintage corridor cohort binding (two bugs): the cohort dropdown cleared the corridor before the r241 sync
  check ran, so a switch never rebuilt it; and a build still in flight when the cohort changed was accepted
  for the new cohort ("still showing 3 members"). Each build now records its cohort, a late result for a
  different cohort is discarded and rebuilt for the current one, and once a corridor has been built every
  cohort switch rebuilds it.
- Build button label rendered a literal ${_vinCohortLabel()} (template placeholder inside a plain string); fixed.
  The loading message names the cohort.
- Vintage data query bounded to the years the corridor can use (charter year through est_to + 7) instead of
  each member's full history; same corridor, far fewer rows. Builds report their time and member count.
- Each vintage plot is as tall as its table, 32px from it, ends on the same vertical line as the peer corridor,
  sits in a 0.5-inch graphite frame, and is redrawn at its exact size (no stretched text).


## r243 — Vintage plot as a soft card

Presentation release on r242. The 0.5-inch graphite frame around each vintage plot is replaced by a soft card:
white, 6px rounded corners, a two-layer shadow (0 1px 2px rgba(0,0,0,.06), 0 4px 14px rgba(0,0,0,.07)), no
outline. The plot still matches its table's height and ends on the peer corridor's vertical line.


## r244 — Vintage leverage and plot height

Presentation release on r243.
- Leverage ratio had no modeled vintage series: the vintage-to-model map listed tier 1, CET1, ROA, NIM,
  efficiency and charge-offs but not leverage_ratio. It now maps to the quarterly filing view's leverage_ratio
  (the same source as tier 1), falling back to the standardized leverage ratio.
- Plots taller than their tables (Leverage, NIM, Tier 1): a feedback loop. The plot was sized from the table's
  wrapper, which flex stretching had made as tall as the plot; once tall, it stayed tall. Plots are now sized
  from the table element itself, the row is top-aligned (no stretching), and plots re-fit on window resize.
  Measured: plot equals table for every metric at 1440, 1920 and 2560px and across live resizes.


## r245 — Vintage corridor for thin cohorts

Built on r244.
- A $2B-$10B cohort holds one 2018-2023 charter, so every age was suppressed (minimum 8) and the page drew a
  grid of dashes while the plot showed the modeled line alone. Now a fully empty corridor shows one card that
  explains why (counts, minimum, and that recent charters are mostly still small) with a "Use all 2018-2023
  charters" action; a metric empty at every age shows its heading and one line; partial suppression shows the
  modeled values (the bank's own numbers) everywhere, with verdicts only where a peer band exists.
- The corridor header names the band ("... chartered 2018-2023 now $2B-$10B") and says when all sizes are shown.
- Accuracy label: earnings metrics (ROA, NIM, efficiency, ROE) now read "item-level FFIEC CDR (earnings family
  migrated July 2026)" instead of the stale "legacy ... migration pending (Work Order M3-6)". Metrics not
  confirmed migrated keep the cautious label.
- Protocol check T33c pinned accuracy_label("nim") as "legacy"; updated to the migrated earnings label, keeping
  its intent (labels differ by family; net charge-off rate still carries the legacy label).


## r246 — Vintage shown in the section title

Presentation release on r245. The section title now carries the vintage after a colon: "Vintage corridor -
de novos at the same age: Chartered 2018-2023" (broad and the all-charters fallback), "... Chartered
2018-2023, now $2B-$10B" (asset band), and for curated peers their actual opening years once built
("Chartered 2019-2024"); no suffix for curated peers before the first build.


## r247 — Governance & QA: data checks

Built on r246. Engine untouched; run results identical.
- The Governance tab becomes Governance & QA: a dark header with counts (Needs review / Worth a look / Info),
  tabs Data checks (default) and Reproducibility (the former Governance content, unchanged).
- Data checks (foundry/v2/data_checks.py, POST /api/v31/qa/checks) read the configuration only. Rules:
  isolated runs in explicit schedules at 8x the surrounding level (Needs review) or 3x (Worth a look); values
  near 12x or 100x flagged as a likely unit mix-up (annual rate in a monthly series; percentage as whole
  number); a 2x jump in the same period as another finding is flagged with it (stale pastes move together);
  annual acquisition attrition taken at period end under monthly flows noted as Info. Step changes and
  smooth ramps are not flagged. Effects of Needs review findings: the model is run on deep copies with the
  flagged values replaced by their surrounding level (ending customers and AUC, net income, fee income,
  deposits). Nothing is saved; the configuration passed in is never modified.
- Recreated incident (17% July attrition in a 1.5% monthly series, CAC 2.2x the same month): both flagged
  Needs review, cross-referenced, with the annual-rate hint and quantified effects. The sound template has
  no findings. Go to opens the relevant module or product.
- Fixed in passing (pre-existing): the run registry stayed on "Loading registry..." on this tab because its
  loader only redrew the Configuration tab.
- Not yet: the balance-measure mismatch rule (needs confirmed fee-stream and cost-pool shapes) and Change
  history (r248, starting with versioned saves).


## r248 — Governance & QA: change history

Built on r247 (deploy together). Engine untouched; run results identical.
- Versioned saves (foundry/store.py): after the engagement file is written exactly as before, each save of a
  NAMED engagement also keeps a timestamped copy (who, when, full configuration) under
  <engagements dir>/_history/<slug>/. Unchanged re-saves are skipped; the newest 50 are kept; working-session
  autosaves are not recorded; any history failure is swallowed so it can never fail or alter a save. The
  listing reads only *.json files, so the history folder never appears. Per-user, like engagements.
- GET /api/v31/engagement/{slug}/history (foundry/v2/config_diff.py): versions newest first with field-level
  changes against the previous save; numeric schedules collapse consecutive changed cells into one entry,
  labelled by the schedule's own cadence (M / Q / Y); plain names for common fields.
- Change history tab, per the mock: dark "<engagement> · saves" bar, newest first, who and when, a one-line
  summary, before (struck) -> after. History starts with the first save after this release.
- Data checks now read a schedule's cadence too (quarterly schedules labelled Q, not M).


## r249 — Change tracking

Built on r248. Engine untouched; run results identical.
- Tracking starts explicitly ("Start tracking" in the Governance & QA header, or "Start change tracking" in
  Change history); freezing a run while tracking is off asks once whether to start it. Before that the
  engagement is in build-out: the header reads "Build-out · not tracked" and earlier saves are collapsed into
  one expandable "Build-out · N saves" line. The marker lives at _history/<slug>.tracking.json, outside the
  versions folder (so pruning can never remove it) and outside the configuration.
- Once tracking, the header shows "Unsaved changes N": the net field difference between the live
  configuration and the saved engagement (twenty edits to one field count once; reverting counts zero), via
  POST /api/v31/engagement/{slug}/status (read-only). Change history shows a "Now · not saved yet" entry with
  those changes. Fields the save path stamps on the stored copy (client, proposed_bank, schema version) are
  not counted. Any save clears the cached status and history.
- Lists of objects are matched by identity (series_id, id, name, role, label): deleting a schedule or a role
  is one "removed" line, adding one is one "added" line, with no knock-on changes from shifted positions.


## r250 — Peer Cohort: Claude Design replicas

Presentation release on r249. Engine untouched.
- Peer corridor rows rebuilt to the Claude Design: band strip (P10-P90, P25-P75, thin black median), the
  modeled value as a ringed gold dot and the Q12 standalone as a small hollow dot; statistics under the strip
  with each label above its value (Min and Max kept, muted); value in 22px monospace with Q12 standalone
  beneath; tone chip and label (green better than peer median, amber worse, red outside P10-P90);
  "directional" chip where the windows differ; "Trajectory ->" opens that metric in the vintage corridor.
- Vintage corridor rebuilt to the Claude Design: metric tabs, like-for-like chip, Chart | Table toggle; one
  chart (P75-P90 and P25-P75 bands, dashed median, modeled line, shaded thin-sample region "n = 2 · p75
  meets p90", Q1-Q12 with n beneath) with a tracking crosshair and a side panel for the hovered quarter
  (n, Modeled with verdict, Max/p90/p75/p50/p25/Min). This replaces the r241-r244 graphite headings and
  separate table-plus-plot per metric.
- Curated vintage title ("Chartered 2019-2024") now reads the opening years from the corridor itself.
- Gate pins on the replaced layout updated to assert the same intents against the new design.


## r251 — Peer Cohort design fixes

Presentation release on r250. Engine untouched.
- Peer statistics (min, p10-p90, max, n) sit in eight fixed equal columns spanning the plot, so each statistic
  is at the same position in every row (previously each row flowed at its own widths and nothing lined up).
- Vintage chart drawn at the chart area's measured pixel width (redrawn on resize), height about a third of
  the width (280-480px), fixed text sizes. Previously a fixed 960x320 drawing was stretched to the panel, which
  enlarged the text and distorted the proportions on wide screens.
- Chart and Table views share one body height at every width (also allowing for the side panel).
- The charge-off "no peer data" message no longer repeats itself.


## r252 — Vintage panel width

Presentation release on r251. The vintage chart/table panel is 80% of its r251 width (981 / 1173 / 1429 px at
1440 / 1920 / 2560); the chart is still drawn at its measured size and both views keep equal heights.


## r253 — Peer statistics block (with r252: narrower vintage panel)

Presentation release on r252 (r252 = the 80% vintage panel width; r253 adds the statistics block).
- Peer statistics are a compact block of eight fixed 64px columns under the start of the strip (aligned row to
  row, as in the Claude Design). r251 spread equal columns across the strip's full width, which made them read
  like axis ticks: the ROA modeled dot (51.49, between P50 and P75) appeared to sit on the "p90" column.
- Vintage chart/table panel is 80% of its r251 width: calc(0.8 * (100% + 1076px) / 2); the chart is still
  drawn at its measured size and both views keep one height.


## r254 — Peer corridor on a percentile axis

Presentation release on r253.
- Every strip uses the same percentile axis: P10 at 10%, P25 at 25%, median at 50%, P75 at 75%, P90 at 90%,
  min and max at the ends, so bands and median bars align across all rows. Band edges are placed by role, so
  tied values (e.g. NIM P25 = median = 3.33) cannot move them. The modeled and standalone dots are placed by
  rank, interpolated between the known percentiles; values beyond the peer min or max are pinned at the edge
  (the chip still says "below p10" / "above p90").
- Statistic labels sit directly under their marks (min, p10 ... max); the count is no longer on the axis:
  one "n = X peers per metric" beside the legend when every metric has the same count, otherwise per row.
- Legend in the panel header: P10-P90 (middle 80% of peers), P25-P75 (middle 50%), median, your bank,
  Q12 standalone.


## r255 — Vintage panel centred

Presentation release on r254. The vintage chart/table panel is centred in the page and 80% of its r254 width
(panel 785 / 938 / 1,143 px at 1440 / 1920 / 2560); the chart is 10% taller than r254 on the same screen
(308 / 340 / 436 px), computed from the r254 chart width since the side panel keeps its fixed width. Chart
and Table still share one body height.


## r256 — Formula component (Claude Design) and rounded corners

Presentation release on r255. Engine untouched; every factor field keeps its existing handler.
- Operating expense formula / driver component rebuilt to the Claude Design: collapsible card ("Formula" chip,
  name, Expense = ... summary), one row per factor with small labels (operator in the label cell; name, value
  or base, unit, path, time basis, display, remove), growth settings or the explicit schedule on a line
  beneath, linked-series factors with their source note, and a live formula line. With only entered factors it
  shows the arithmetic ("= 1 x 140 x 2,080 = 291,200 / year"); with a linked factor it shows names only, with
  the correct operator (the design's mockup printed "undefined" there). Edits refresh the line. On cards
  narrower than 820px (detail beside the list) each factor wraps into two lines; no overflow or clipped fields
  at 1440 / 1920 / 2560.
- Subtle rounded corners across Foundry: fields and buttons 6px; cards, panels and dark title bands 8px;
  pill-shaped controls unchanged. Clipped-control and overflow audits: 0 at 1440 and 1920px.


## r257 — Compensation pools relocated; airier one-line formula factors

Presentation release on r256. Engine untouched; configuration keys unchanged.
- Workforce: "Additive compensation components" become "Compensation pools" (bonus and incentive pools layered
  on role compensation), placed directly under the roles and above the run summary, with a "+ Compensation
  pool" button that calls the existing adder (same workforce.additive_components object). The run summary
  gains a row per pool, read from the engine's existing per-pool output (amounts in $000s): total over the
  horizon and first posting. Previously the summary listed roles only, though pools always posted to
  Workforce compensation (display omission; no numbers were affected). Pool fields sized to their content
  (name up to 560px; timing 230 / 170 / 140px; source up to 540px), scoped so OpEx tiered cards are unchanged.
- Formula / driver component: more generous spacing; every factor on one line, with growth shown as a summary
  chip ("10% / yr · step") that opens its settings beneath on demand; a compact remove control. Narrow cards
  still wrap to two lines.


## r258 — "+ Compensation pool" beside "+ Add role"

Presentation release on r257. The roles action row reads "+ Add role · + Compensation pool · Paste roles"
(the existing "+ Tiered / banded compensation component" entry renamed, same adder and same
workforce.additive_components object); the separate button r257 placed in the pools header is removed.


## r259 — Expired sessions on Governance; collapse all; hideable linked sources

Presentation release on r258. Engine untouched.
- Change history showed "HTTP 401": sessions last 12 hours (FOUNDRY_SESSION_SECONDS, default 43,200) and the
  console has no shared 401 handling. Governance's checks, status and history now say the session expired,
  offer sign-in in a new tab (which renews the site cookie without losing this tab's edits) and "try again".
  The history route itself was verified: it is the only route matching the URL and returns 200 with a session.
- Additive expense components: "Collapse all · Expand all" in the section header when a category has two or
  more Formula / driver components (previously each collapsed separately).
- Every linked-series source preview (formula linked factors and standalone linked components) has "Hide
  source"; hidden previews shrink to "Linked source hidden · Show", remembered per series.


## r260 — Room for formula components; visible open/close control

Presentation release on r259. Engine untouched; no fields changed.
- Categories containing Formula / driver components stack the list above a detail panel of up to 1100px at
  every width (as at 1440px already); formula cards go from 750-846px to 1000-1066px. Fields have 14px gaps
  and roomier columns; the linked-series dropdown, previously clipped past the card edge at 1920px, now fits.
  Measured at 1440 / 1920 / 2560: no row overflow, no clipped text.
- The tiny arrow becomes a 30px bordered chevron button that flips when open; the whole header is clickable
  (hover highlight, Collapse / Expand tooltip, keyboard Enter / Space).
- "Hide source" sits on its own line above the preview instead of over its text.


## r261 — Categories layout fix

Presentation release on r260. r260 stacked the list above the detail for categories with formula components,
but nothing then bounded the list: at 1920 / 2560px it stretched to the full page (1,514 / 2,154px) and its
columns spread across the screen. Now the whole Expense categories section stacks consistently (no layout
jump when moving between categories): the list keeps its table's natural width (716px at every screen), the
detail beneath is up to 1100px (1,034px at 1440). No horizontal page scroll; formula cards unchanged
(1,066px at 1920, 14px gaps, no clipping).


## r262 — Compensation pools in the roles table

Presentation release on r261. Engine untouched; configuration unchanged.
- Pools are rows in the Workforce roles table (after the populations; Count "-", Basis "Pool", Active shows
  the timing, Paths "Tiered"); selecting one opens its editor in the same detail panel as a role (768px beside
  the list at 1920, 880px stacked at 1440; no overflow or truncation). "+ Compensation pool" adds a pool and
  opens it; "Remove pool" sits in the panel foot. Only one row is highlighted at a time. The separate
  full-width pools block below the table is gone (kept only for an engagement with pools but no roles).


## r263 — Categories list and detail aligned

Presentation release on r262. In r261/r262 the categories list kept its natural 716px while the detail panel
beneath was up to 1100px, so the panel overhung the table by almost 400px instead of sitting under it. The
list now matches the panel (width 100%, max 1100px): identical left and right edges at 1440 / 1920 / 2560
(1,034 / 1,100 / 1,100px), panel entirely below the table, no horizontal scroll.


## r264 — Categories side panel restored; one-line formula factors

Presentation release on r263. Engine untouched.
- The Expense categories detail is again a side panel beside its list (the r260/r261/r263 stacking and width
  rules are removed). On screens of 1600px and wider the list takes its natural width (574px) and the panel the
  rest (927px at 1920, 1100px at 2560); narrower screens stack, as before r260.
- Room comes from squeezing the list: Path 64px, Amount 96px (header wraps), "Comp." 52px, Timing 104px
  (wraps), long category names end in an ellipsis.
- Formula factors stay on one line at 846 / 893 / 1066px cards. Column widths come from measured needs
  (x Multiply 100, Growth 84, Per Quarter 110, Number 89, growth chip 92-118px). fitControls gained an opt-out
  (data-nofit) so grid-sized dropdowns are not forced wider than their column (it had set a 572px minimum on the
  linked-series dropdown). No overflow, no clipped text at 1440 / 1920 / 2560.


## r265 — Categories list uses the free width

Presentation release on r264. At 2560px the side panel stopped at 1100px with an empty band to its right while
the list was held at 574px and truncated most names. Now, on screens of 1880px and wider, the panel keeps
880-1100px (one-line formula factors) and the list takes everything left over: 1,040px at 2560 (panel ends
21px from the edge; 0 of 13 long names wrapped or truncated), 574px at 1920. The categories table uses a fixed
layout (narrow columns keep their widths; the name column takes exactly the remainder) and long names wrap to a
second line instead of truncating (8 of 13 at 1920; none truncated anywhere). Narrower screens stack.


## r266 — Cost pool balance row and balance-series close

Presentation release on r265. The Operating Expense cost pool's balance row used equal auto-fit columns, so
Measure, Multiplier and Per were as wide as Balance source. It is now a grid: Balance source takes the remaining
width (386 / 432 / 606px at 1440 / 1920 / 2560), Measure 136px, Multiplier 96px, Per 96px (measured needs);
the dropdowns opt out of fitControls; no clipping or overflow. The same applies to the fee-product cost pool
row. The balance-series preview gains "Hide source x" (remembered per series), like the linked-series previews.


## r267 — Component types in the categories list

Presentation release on r266. The "Comp." count column becomes "Components": chips for the additive expense
components each category uses (Formula, Cost pool, Tiered, Linked), with a count when more than one ("Formula
x2"), "-" when none. The side panel is unchanged (beside the list at 1920 / 2560; stacked below 1880px), and a
new gate check fails if it is ever stacked on wide screens again. When stacked (below 1880px) the list now
matches the 880px panel beneath it, so names no longer wrap at 1440 (0 of 13; was 10). At 1920 the list stays
574px beside the 926px panel that one-line formula factors need, so names wrap to two lines there.


## r268 — Categories columns sized to content

Presentation release on r267. Path, Amount and Components had guessed fixed widths (64 / 96 / 130px): "Explicit"
was squeezed and "41.66667 / month" ran into Components. They now never wrap, and after each render their
widths are set to the widest actual content (e.g. Path 77px, Amount 137px for "41.66667 / quarter"); the
Category column absorbs the difference. No cell overflows at 1440 / 1920 / 2560; the side panel is unchanged.


## r272 — Shared source catalog

See R272_SOURCE_CATALOG.md. Built directly on r271; metadata discovery is outside engine results. Existing Formula components can observe current book/pool balances with explicit measures. Browse/search and typed consumer eligibility are shared across the main quantity pickers. Legacy outputs and pinned fingerprints remain unchanged.
# r273 — Choose expense sources explicitly

Built directly on r272 (8ccc715). New Formula / driver expense components and newly added linked factors start with Select a source. The dropdown and Browse / search both support choosing a source; clearing the dropdown removes the link. No source is silently substituted for an empty or unknown selection. Existing authored links and legacy defaults remain intact.

An incomplete linked factor is rejected with “formula/driver linked factor: select a source” rather than generating expense against an arbitrary series. Production browser coverage creates a component, checks the empty prompt, adds another empty linked factor, and then selects a pool balance through the catalog. Existing rename and measure checks continue to pass. Three pinned fixture fingerprints are unchanged.
# r274 — Responsive expense editor and balance previews

Built directly on r273. The category list and editor use the space available inside Configuration, rather than browser width. Opening Assumptions reduces that space and stacks the category list above the editor; wide workspaces retain the side-by-side presentation. Formula factor controls wrap within the editor, while remove-factor buttons stay at the upper right of their own row.

Catalog balance links now display the selected series from the latest run in $000s, labeled by presentation period. Beginning and average measures use the correct opening stock: deposit/lending opening balances, pool-member deposit opening balances, or explicit opening swept balance. The preview is read-only and does not run the model or alter its numbers. If results are unavailable, the UI asks the user to run the model. The hide/show preview control remains separate from the remove-factor button.

Production Chromium coverage checks editor bounds at 1280, 1440, and 1920 pixels with Assumptions open and closed, remove-factor placement, and engine-backed retained balances ($400,000 end; $200,000 first-period average from zero opening). Prior catalog search, source selection, rename, and measure checks remain covered. Engine code is unchanged.
# r275 — Deposit setup and immediate engagement menu

Built directly on r274. Deposit calculation and posting code is unchanged.

Deposit setup separates the category's on-book balance and retained allocation share from its shared pool. Shared settings follow Source balance → Retention & capacity → Swept-out fees. The pool summary shows the retained-share path, capacity method and fee path; its membership note identifies the other categories affected by editing it. Adjustments and equity-budget inputs have expandable sections that remember their state by pool ID. All existing Enter / Link / Derived and Flat / Growth / Explicit inputs remain, including their Load / Clear / Close schedule controls, pool previews, pricing, interest balance measure, costs and fee streams. Day-count is 86 pixels; path, source and numeric controls have bounded widths instead of stretching across the editor.

The engagement chevron renders cached entries and Save / New actions immediately. With no cache, it shows loading status while retaining the actions. The server list refreshes in the background; simultaneous opens share one request. Failed refreshes preserve the loaded list and show Retry. A completed refresh never reopens a closed menu. Save/delete refreshes wait for any older read, then request a fresh post-write list; a stale pre-save response cannot satisfy that refresh. Save confirmation continues to require the server write.

New detailed-expense setups initialize FDIC assessment at zero. Existing saved values, including the historical engine fallback for a missing field, remain unchanged. The assessment hint reminds the analyst to use zero when FDIC is modeled in a separate category. Example-bank/fixture assumptions are preserved. In the current engagement, the separate FDIC category matched all 36 source values at displayed $000s precision, using retained deposits × 0.15% / 12. Its old built-in assessment must be explicitly zeroed to avoid duplicate expense; this release does not silently alter that saved assumption.

Verification: production Chromium covers cached and cold menu opens against pending responses, request deduplication, close-before-response, failed refresh cache preservation, a post-write refresh following a pre-write response, new/saved FDIC settings, deposit grouping, advanced controls, bounded day-count at laptop widths, and unchanged pool inputs after display interactions. Existing source-catalog and stream-reordering browser checks pass; inline scripts compile. Full suite: 60 Python modules / 9 known baseline failures, 7 JavaScript scripts / 1 known baseline failure; no new failures. Three pinned fixture fingerprints remain unchanged.

Two deposit calculation checks remain separate from this UI release: exercise a binding equity-budget capacity case and verify final financial-statement/audit posting with the old FDIC assessment disabled.
# r276 — Keep Vintage Corridor Build available

Built directly on r275. The Build corridor action is always visible: before a build, after success, and after failure. Cached connection-status checks no longer suppress it. A pending request shows a disabled Building action; it becomes available again on completion. A failed rebuild of the same cohort keeps the previous corridor visible with an explicit error. Results from another cohort are not shown as the current cohort.

Automatic cohort synchronization compares the last attempted cohort as well as the last successful result. A failed attempt no longer triggers another request on every render. A genuinely changed cohort still builds once; if it changes during an in-flight request, stale success/error is discarded and the current cohort is requested. An empty curated selection is rejected instead of silently falling back to the broad cohort. Incomplete response envelopes show an error rather than failing the entire section render. The 25-second abort remains active through response-body reading.

Production Chromium coverage: action visible with stale/unreachable health status; disabled busy state; explicit retry and no render-triggered failure loop; rebuild after success; previous results retained after failed rebuild; cohort switch during a failed request; malformed response recovery; empty curated selection sends no broad request. Full suite has no new failures versus r275 (60 Python modules / 9 existing failures; 7 JS scripts / 1 existing failure). The source-string layout guard was updated for attempt-based cohort synchronization; actual request behavior is covered by Chromium. Three pinned fixture fingerprints remain unchanged. No engine or peer-data calculation changes. This corrects UI retry behavior; availability of the external data service still depends on that service.

# r277 — One Formula editor for linked expenses

Built directly on r276 (accc742). All eight legacy linked-expense sources are presented in the existing Formula / driver card, with Browse / search, source preview, factor editing, consistent chips, and collapse/expand controls. Rendering does not rewrite their configuration. The first edit promotes the component into typed formula factors, preserving its source, rate schedule, rate period, balance measure and dollar units. Workforce amounts are explicitly labeled $ / FTE; periodic growth edits write the actual periodic amount rather than an unused base field.

AUC-linked expenses retain their existing monthly accrual convention after promotion: monthly measured balance × observed monthly rate ÷ rate-period months, summed into the engine period. This matters in quarterly models and with monthly varying rates. A formula's optional monthly accrual pair delegates to the existing AUC calculation; it is validated, cycle-checked and explained in the editor and audit. The audit does not present an incorrect quarter-end balance × sampled rate as the calculation. Additional factors apply to the accrued amount at model cadence. Changing/removing the pair's source or multiply operator explicitly exits that convention. Rate period is separate from rate-observation schedule cadence.

Validation: 66 legacy-to-formula component comparisons at monthly and quarterly cadence, covering income sources, throughput, workforce flat/growth/explicit amounts, and AUC end/average measures with flat/growth/monthly explicit rates. Full-engine income statement and balance sheet comparisons pass for monthly and quarterly AUC cases; quarterly varying-rate expense is independently recomputed. Production Chromium exercises every legacy type, inert rendering, rename promotion, periodic workforce growth editing, rate-period changes, extra factors and Browse source selection. The existing source-catalog browser regression and inline JavaScript syntax checks pass. Full suite: 61 Python modules (9 existing baseline failures) and 7 JavaScript scripts (1 existing baseline failure), with no new failures versus r276. All three pinned fixture fingerprints remain unchanged.

# r278 — Proportional Formula fields and contained input sizing

Built directly on r277 (6696eec). Formula factor rows now use proportional tracks: bounded names and unit labels, a 150px numeric track, and dropdown widths that fit their supported labels. Rows wrap at their own container width, with a separate growth-summary row where needed. Narrow balance-measure controls occupy a full row. Remove buttons retain their reserved edge space.

The global text/value fitter previously assigned inline important minimum widths to Formula inputs after rendering or typing. That could force a numeric input beyond its fixed grid track and overlap the next field. Formula cards now own their input sizing; the fitter clears its minimum width for those controls instead of enlarging them. Numeric steppers are suppressed in factor rows to preserve usable text space. Other forms retain the existing fitting behavior.

Verification: production Chromium checks 18 flat/growth layouts across actual card widths from 360 to 1350 CSS pixels. It asserts contained inputs, no field overlap, reserved remove-button space, supported operator/path/time/display/measure labels fitting, and no injected minimum width after typing a number. Long linked-source names retain their existing dropdown/preview behavior rather than forcing the row to expand. Existing source-catalog and legacy-promotion browser checks pass, as do inline JavaScript syntax, the 66 calculation-equivalence cases and all three pinned fixture fingerprints. The OpEx UI module retains its two pre-existing failed assertions (64 passing). No engine, configuration grammar, calculation or saved-assumption changes.

# r279 — Consistent securities risk weights and zero passive defaults

Built directly on r278 (53401a7). The securities summary uses the same 20% missing-value default as its editor and engine, while preserving explicit 0% and other entered weights. Changing the weight refreshes the summary immediately. This corrects a misleading 0% display for sleeves with no saved risk weight; the capital calculation is unchanged.

Residual securities yield is zero in the embedded starter configuration. Blank engagement creation and the engine's missing-yield behavior already use zero. Explicitly saved yields remain authored inputs. FDIC assessment now defaults to zero in new expense settings, the missing-field UI fallback and the common engine assessment parameter, so both engine profiles use zero when no rate is authored. FIW descriptions reflect the zero default. Explicit saved FDIC rates are preserved. Existing engagements with saved non-zero values require setting those two fields to zero and saving; deployment does not overwrite authored engagement data.

This release intentionally changes results for configurations that previously relied on the missing-FDIC-rate fallback of 5 bp/year. The unchanged core-bank fixture has no explicit rate: its fingerprint changes from f1384367e87a to 02a7295b4351. The identity gate explicitly records this change; it does not strip result fields. The other fixture hashes remain 65c7d71491d6 and f04db06d9389. A core-bank configuration explicitly set to 5 bp produces the same 89f8d8f7231d fingerprint in r278 and r279. Frozen runs relying on the prior implicit 5 bp will correctly report a changed fingerprint; do not overwrite their frozen record to conceal that change. The frozen-run regression now tests both the expected old-hash mismatch and successful verification against the current fingerprint.

Verification includes production browser checks for table/editor agreement at missing, 0% and 50% risk weights, immediate edits, zero missing-value displays and preserved explicit FDIC/yield values; Profile A/B missing FDIC versus explicit zero; explicit 5 bp continuing to accrue; and a $30m residual book earning zero at missing/zero yield and positive interest at an authored yield. Capital/RWA tests, inline syntax and the identity gate pass. Full-suite results are recorded in delivery/VALIDATION.md with a fresh r278 comparison.

Full r279 regression comparison: 62 Python modules / 9 existing failing modules; 7 JavaScript scripts / 1 existing failing script. No new failing modules or failed assertions versus fresh r278. The deliberate missing-FDIC change and its frozen-run consequence are explicitly tested.

## r280 — Activity paste Clear
Explicitly consume visible Activity drafts in coefficient, monetary flow and account count Clear callbacks before authoring restoration. No engine changes. See R280_RELEASE_NOTES.md for regression evidence.


## r281 — Configuration balance-sheet hierarchy

UI-only release on r280. Securities settings now separate simple books, managed portfolios, AOCI, funding allocation, fiduciary balances, affiliated-bank cash, operating cash, Federal Reserve stock and named liabilities. Group headings feed the existing Configuration section navigation. Funding and fiduciary inputs use responsive two-column grids; numeric widths remain bounded and explicit schedules retain previews and existing paste actions. Named liability formulas collapse independently and remember their open state during rerendering. Shared Configuration spacing and action-button sizing are consistent across modules. Top menus and Klaros colors are retained. No engine, schema, pricing, defaults or saved assumptions changed.

Validation: browser checks at 1440/1280/1024/768 pixels, all six module selections, liability expand/rerender persistence, and no runtime errors. Against r280, the same example produces identical configuration and all 42 Securities control values/options/handlers. Existing 18-case formula layout regression, three pinned result identities and inline JavaScript syntax pass. Full engine suite not repeated for this presentation change. This reorganizes the Securities module substantially; it does not claim a complete interaction redesign of every Configuration module.


## r283 (Claude) — Securities & balances redesign; quiet canvas

Built on r281 (7d30485), as an alternative to GPT's r282. Engine untouched; every control keeps its handler.
- Quiet canvas #f0efeb on every page except Balance Sheet, Income Statement and Welcome (left navigation sits on
  it; white cards carry a fine border so they stay outlined on bright monitors).
- Product Detail, Capital & Ratios, Stress Testing, Executive Summary and Peer Cohort: content in a centred
  1440px white sheet (240px of canvas each side at 1920); the breadcrumb stays on the canvas. The sheet is
  wrapped in pageChrome only AFTER the title band is chosen, so the band is always the page heading. (GPT's r282
  wrapped first, which painted the whole sheet graphite on seven tabs.)
- Securities & balances follows the Claude Design: a "Model inputs" rail and five collapsible sections, closed by
  default: 01 Funding allocation, 02 Interest-bearing balances (incl. operating cash & FRB stock), 03 Other
  liabilities, 04 Securities books & AOCI, 05 Managed portfolios. Closed headers show live summary chips; the
  Include-in-model switch and the Flat / Formula-level switch work on the closed header. Existing blocks are moved
  into the sections unchanged and restyled into compact rows (books as one row each; AOCI as a row).


## r284 — Tax-year interim provisions

Direct successor to Claude r283 (`b6655ac`). Replaces period-by-period NOL generation
with a dated tax-year ledger and supported annual-effective-rate interim provision.
Same-year losses offset income fully; the configured carryforward limit applies to
prior-year NOLs only. Future-year loss recognition requires an analyst assessment;
legacy automatic recognition no longer treats cumulative profit as proof.

Compact tax authoring, current/deferred detail, tax assets in the balance/capital
calculation, Call Report other-assets inclusion, and a dedicated Income Taxes audit
sheet accompany the engine change. Results/fingerprints intentionally change.
See R284_TAX_METHOD.md, R284_RELEASE_NOTES.md and R284_VALIDATION.md.


## r285 (Claude) — New Executive Summary view in the Klaros skin

Presentation release on r284 (4ead287). Engine untouched. The New Executive Summary view is a self-contained
document generated server-side (foundry/v2/exec_view_gen.py) from foundry/v2/assets/exec_view_template.html and
shown in a sandboxed iframe, so the console's palette changes never reached it. Its chart palette had already been
moved to warm tones, but its CSS variables, tables and logo were still navy and blue; that left some text dark on
navy (e.g. the gauge's requirement value was effectively invisible). Variables and literals are now Klaros:
warm-white surfaces, graphite text (#1D1C1A / #4A4741 / #8A867D), deep gold accents (#9A7330), graphite table
headers with the gold rule, gold logo; info tone graphite instead of blue. No blue-dominant colour remains
(guarded by tests_r285_exec_skin); rendered check: no blue in computed styles, no light text on light surfaces.


## r286 (Claude) — Governance data checks that catch digit slips; change tracking without phantom edits

Built on r285. Engine untouched.
Why two deliberate fat-finger tests (634 typed as 1,634 in a fee-stream count schedule) were missed:
(1) the scanner read only {trajectory: explicit, values} objects, so level schedules ({period, resolution,
schedule: {period: value}}) were never examined; (2) the only rule flagged values >= 3x the whole-series median
(here 5,457), which cannot catch a slip in a trending series (1,634 is below the median, 1,819).
- Every numeric schedule is scanned: explicit values, period-keyed level schedules, and schedule-like lists.
- Local-trend break detector: residual against the neighbours' interpolation, robust scale (MAD), iterative,
  only points beyond both neighbours (genuine steps are never flagged), interior before edges.
- One-keystroke explanations: extra / missing / transposed digit, x10 / x100 / x1,000 ($ vs $000s).
  "1,634 looks like 634 with an extra 1 at the start."
- Edited since the last save: when the engagement is saved, edits that look like a slip are flagged with the
  saved value (catches edge and noisy-series slips the trend cannot).
- Validation: the user's series caught (expected ~614); x1,000, swapped, dropped and final-period slips caught
  with the right explanation; 0 false positives on 7 named shapes and 300 randomized clean series; 0 findings on
  shipped fixtures. Trend findings inside an existing spike episode are suppressed (no duplicates).
- Governance > Data checks lists "What these checks catch" (8 checks, examples, severity, scope) and
  "Not caught" (5 limits), served with the findings so the list cannot drift from the code.
- Change tracking: numbers equal to within float noise are not changes; real sub-unit differences are shown with
  enough decimals; period-keyed schedules merge into ranges (M1 to M36). The 36-line phantom list collapses to the
  one real change.


## r288 (Claude) — Expanded Securities sections as bands

Built on r287 (e8ff522, deployed). Engine untouched; every control keeps its handler.
- r287's layout layer (_layoutExpandedSecurities and ~70 grid rules) is retired; it produced loose 3+2 grids,
  mismatched product boxes and labels stacked over every field. tools/verify_securities_layout.cjs (r287) checks
  r287's classes and is superseded by tests_r288_securities_bands and the browser checks below.
- One layout grammar: bands with a left header column (product or group name, one-line note) and fields on the
  right; one line per assumption (label | method | value + unit, or sparkline + first -> last + count, cadence,
  Edit). Funding allocation: Policy; Rates, floors & other assets (paired). Interest-bearing balances: four numbered
  product bands; the linked-series selector on its own line with its caption beneath (the r286 overprint is gone).
  Other liabilities: Starting position; one collapsible band per component with a line per term. Managed
  portfolios: target settings on one line; the selected security as Holding / Flows / Yield bands.
- Every section is collapsed when the user arrives on the page (by tab or by module); re-renders while editing keep
  the open section open.
- Dropdowns in these sections opt out of fitControls (it had forced a 418px minimum that overprinted the caption);
  a class collision with r283's section numbers (fsx-n) is avoided (fsx-lab).
- Browser checks at 1280 / 1440 / 1920 px with interest-bearing balances on, four explicit schedules and a linked
  driver: zero overlapping sibling boxes, nothing past a card edge, no truncated or wrapped schedule summaries,
  collapse on arrival; narrow stages stack each band's header above its fields.


## r289 (GPT) — Named balance components and capital presentation

Built directly on r288 (8701c60). Generic, user-named typed balance components replace the fixed four-category structure for new authoring. Existing models retain the unchanged legacy calculation contract; adoption is explicit and reversible. Named accounting destinations, shared inputs, unit validation, income/cost bases, opening stocks and component risk weights are audited. Pre-opening and scheduled assets use summary tables with selected-item editors and top actions; formula assets have distinct opening/derivation/depreciation groups. See R289_RELEASE_NOTES.md and R289_VALIDATION.md.


## r290 (Claude) — Centred sheets on the record pages; chapter notation aligned

Built on r289 (406d528). Presentation only; engine untouched.
- Cause: r283 limited the centred white sheet to five pages, and centred the breadcrumb (chapter notation) at
  1440px on every canvas page. On Examiner Book, Assumption Book, Bank Design Lab and Governance the content ran
  full width while the notation floated centred above it.
- The sheet now covers those four pages (nine in all); Governance, which has its own header path, wraps too.
- The notation is centred only above a centred sheet; pages without one keep it aligned with their content.
- Tables not already inside a scrolling container are wrapped so they scroll inside the sheet. Stress Testing's two
  36-month tables (Net income and Tier 1 leverage by month) previously ran past the sheet onto the canvas.
- Measured at 1920px on all nine sheet pages: content and notation centred (240px each side), nothing past the
  sheet edge, and the title band is always the page heading, never the sheet.


## r291 (Claude) — Placed in service as a box, not a horizon-long dropdown

Built on r290. Presentation and input only; engine and the in_service_period field unchanged.
- Fixed assets / CAPEX: "Placed in service" was a dropdown with one option per forecast period (36 on a
  36-month model). It is now a digits-only box labelled "Month placed in service (max = N)", N being the forecast
  horizon (the period word follows the cadence: Month / Quarter / Year). 0 means at opening, as before.
- Letters and symbols cannot be typed or pasted in; empty or out-of-range entries are refused with a message (the
  saved value is kept), never silently clamped. The asset table shows "Opening" / "M12" and keeps showing the saved
  value while an entry is refused.


## r292 (Claude) — FDIC assessment defaults to 0 bp

Built on r291. Every code default was already 0 bp (engine fallback REG_PARAMS, new-engagement defaults, display
of an unset rate, FIW note "default 0"); the universal template fixture alone set 5.0 bp, and it seeds the
downloadable universal template workbook. It now stores 0.0. Effect on the template (36 months, $000s):
pretax +684.5, tax +143.7 (21%), net income +540.7; the other four fixtures are identical. The template's current
fingerprint pin moves from cef1ab6b99c5 to 6fd77a2f45fe. Saved engagements keep whatever rate they store; an
explicit rate is still honoured. Guarded by tests_r292_fdic_default.


## r293 (Claude) — Bank and version, clearly separated

Built on r292. Engine untouched.
- A saved engagement is a BANK plus a VERSION. "Save as" wrote the whole typed name into the version field, so
  "Bank 1-Aggressive" showed as "Bank 1 / Bank 1-Aggressive": two near-identical plain-text names that ran
  together when truncated.
- Header: the bank in bold, then the version as a gold "VERSION" chip ("Base" before one is named); the bank
  truncates first, the chip keeps its full text; clicking the chip renames the version in place.
- Save as asks only for the version (in-app dialog, bank shown as context, live "Saved as Bank 1 · Aggressive"
  preview); a typed bank prefix is detected and stripped. The unsaved-changes guard does the same.
- Saved list: versions grouped under their bank (as the header names it), "current" marked by storage key.
- Data: scenario_name stores the bank-qualified name ("Bank 1 · Aggressive") so storage keys stay unique per bank
  and consistent with Governance history and change tracking. The key slug of "Bank 1 · Aggressive" equals that of
  "Bank 1-Aggressive", so re-saving an older engagement updates it instead of duplicating. The store list adds
  bank_display (proposed name first) beside the existing bank field.


## r294 (Claude) — Save guard: no false alarms, one save window

Built on r293. Engine untouched.
- Reported: the "unsaved changes" guard appearing with no changes; save windows of different shapes.
- Not reproduced in seven browser scenarios (open/switch, every tab and module, a rich engagement, sign-in and reload,
  edit + autosave + save + reload, guard reopening). The code path that yields exactly the reported symptom is the
  NEW-UNSAVED state: accepting "Recover unsaved work" at sign-in lands the configuration as never saved, so every
  switch raised the guard with an empty list shown as "(changes present)", even when it was identical to a save.
- Fixes: a never-saved configuration identical to any saved engagement is re-marked as that engagement (no guard);
  boot retires an identical recovery draft whatever its name; the guard states why it appeared ("These fields changed
  since the last save: ..." or "has not been saved yet ..."), never a bare "(changes present)".
- One save window: r293 added the "Save as a new version" dialog beside the guard's older embedded form; the guard's
  Save as now opens the same dialog and then completes the switch.
- The current-version marker in the saved list follows saves as well as opens.


## r295 (Claude) — Unsaved-changes guard: visible reasons, no drift, compact

Built on r294. Engine untouched.
- The guard did list the changed fields, but each row was near-black text (#2B2B2B) on the near-black list (#2A2A2A),
  so the reasons were invisible and the empty-looking list made the window tall. Rows are now light text, capped at
  eight with "and N more".
- Changes no user made: a render or engine run that alters the configuration while the engagement was clean is now
  re-baselined instead of counted as unsaved work; each occurrence is recorded in window.__renderDrift (where, when,
  fields) and logged to the console so its source can be named. Genuine edits (made before the render) still count.
- The window is compact (520px, about 300px tall with a full list) and the four choices are evenly sized; no label
  is clipped.


## r296 (Claude) — No "unsaved" state from changes after opening that nobody made

Built on r295. Engine untouched.
- Reported: Discard & switch from A to B, reopen A, leave A: the guard appears again although A was just loaded.
- Root cause not confirmed (not reproducible on the reference configurations; normalizeCfg is idempotent on all
  twelve). Gap found in r295: opening an engagement schedules the engine run 350 ms later, AFTER the clean baseline;
  r295 checked at scheduling time, so any change made during the deferred run (e.g. its in-place normalizeCfg on
  data where that is not idempotent) or by any other post-open timer still made the engagement dirty.
- The deferred run (preview) is now covered, healing only when the user did not interact during it; a settle check
  after every open (0.6 / 1.5 / 3 / 6 s) heals changes made with no user interaction since the open. Trusted user
  interactions (input, change, paste, drop, keydown, mousedown, touchstart) are counted; any interaction disables
  the heal. Each heal is logged in window.__renderDrift with its fields.
- Validation: drift inside the run and from a post-open timer is healed (no guard on leaving); genuine edits made
  100 / 400 / 700 / 1000 / 1500 ms after opening, during the run, all stay unsaved; the reported round trip
  (edit A, Discard & switch to B, reopen A, leave) raises no second guard.


## r297 (Claude) — Editing a legacy expense no longer changes its growth or shows phantom changes

Built on r296. Engine untouched (console conversion only).
- Reported (with screenshot): changing Simple overhead from 1,800,000 to 2,800,000 listed six further "changes",
  every field of a new overhead_flow_spec from "—".
- Cause: an engagement still holding overhead (or a detailed expense category) in the legacy per-period fields is
  displayed through a converted view; the first edit materialises that view as a flow spec. The conversion used
  growth method "smooth", which on a QUARTERLY model sub-steps growth within each quarter: overhead rose about
  0.33% per period (1,800,000 became 1,805,986.73 in Q1; up to 6,679/quarter), categories up to 2,046/quarter.
  Monthly models were unaffected.
- Fix: legacy growth converts to "step" at the model period, which reproduces the legacy path exactly (0.0000,
  quarterly and monthly, overhead and categories). The guard compares against the saved copy's converted view,
  so it lists only the user's change ("Value: 1,800,000 → 2,800,000").
- Engagements saved since such an edit on a quarterly model may carry "Smooth" in Simple overhead or a category's
  growth method; set it to "Step" to restore the legacy profile (not changed automatically: smooth may be intended).


## r298 (Claude) — Governance catalogue collapsed by default

Built on r297. Presentation only.
- "What these checks catch" (8 checks and 5 limits) took over the Data checks tab. It is now a single collapsed line
  ("What these checks catch · 8 checks · 5 limits", with the save note at the right); click to open. It stays as
  the user left it while on the page and collapses again on arrival from another tab.
- The heading ran into its note ("...catchEdits are compared...") because the catalogue's r286 styles were no longer
  in the file; they are restored, with heading, count and note as separate, spaced elements.


## r299 (Claude) — Steady drag-to-reorder for expense categories

Built on r298. Presentation only.
- Expense category rows keep the class opex-item-card from when they were cards; its card-era drop bars are
  ::before / ::after pseudo-elements. On a table row the "drop-after" pseudo-element became an extra table cell and
  re-laid out every column (the Path column jumped 317px), while "drop-before" did not; crossing each row's
  midpoint flipped between the two, so the table jittered. Workforce rows have no such pseudo-elements.
- The pseudo-elements are suppressed on table rows; the layout-neutral inset marker remains. Measured: identical row
  and cell geometry with either marker; a real drag reorders correctly.


## r300 (Claude) — Expense categories reported with their components

Built on r299. Engine calculations unchanged; reporting series added.
- "M1 expense categories" (and nie_detail_series.categories) held only each category's own recurring base path;
  cost-pool, Formula and Tiered component charges, which the engine evaluates separately and posts in the same
  operating expense, were invisible there (the universal template hides 91.56 $000s/month of them in M1).
- The engine now records component charges by category and period (overwritten if the solver re-runs a period);
  results add nie_detail_series.components, components_by_category and categories_total (base paths + components).
- Console: the KPI shows the full total with "base paths X + components Y"; each category editor shows "Latest run ·
  components charge for this category" under Additive expense components.
- Verified: every financial result identical to r299 on all five reference configurations; only run_hash changes
  for core_bank_test_base (f4aa646c3180 -> 3095860cd0b7) and universal_template_bank (6fd77a2f45fe -> 63efab196c93)
  because the results now carry the new series.
- Engine behaviour confirmed by experiment: a category's base path and its cost-pool charge are additive. Entering
  the same base both as the category's base path and inside its cost pool counts it twice.


## r301 (Claude) — Plain Save

Built on r300. Presentation and workflow only; engine untouched.
- The only way to save was the ▾ menu's "Save as a new version". A Save button now sits in the header beside the
  engagement status: gold "Save" when there are unsaved changes (one click writes the open bank · version, no dialog),
  "Saved ✓" (disabled) when clean, "Save…" for a never-saved engagement (opens the version dialog), hidden when the
  workspace is empty. Ctrl/Cmd+S does the same instead of the browser's save-page.
- It uses the existing save path (recovery-draft purge, clean baseline, change tracking, saved-list refresh).
- After a save, the status reads "N changes since save" (an uploaded engagement previously kept saying "since upload").
- Verified: a typed edit then Save keeps a single saved entry and stores the new value; Ctrl+S saves; Ctrl+S when clean
  does nothing.


## r302 (Claude) — Save button visible from the moment an engagement opens

Built on r301. The r301 Save button was refreshed only when the change status refreshed, which on opening an
engagement happens before the engagement is marked opened; the button stayed hidden until the first edit (the r301
test refreshed it by hand and missed this). It now refreshes on every lifecycle change (open, save, clear): "Saved ✓"
right after opening, gold "Save" at the first change, hidden when the workspace is empty. The clean state has a
visible outline. Verified on the real path: sign in, open from the ▾ menu, edit, Save, clear.


## r303 (Claude) — Tiered components: Browse / search and series previews

Built on r302. Presentation only; engine untouched.
- Formula components offer "Browse / search" for linked series and a preview of the selected series; Tiered (piecewise)
  driver terms had only a Source dropdown. Each Tiered term now has "Browse / search" (the shared source catalogue in a
  Tiered mode: only total assets, Customer Acquisition AUC and balance-basis fee-stream quantities are selectable) and a
  preview beneath it: the shared Formula preview for AUC; the run's balance quantity ($000s) for fee streams; the run's
  total assets for total-assets terms.
- An empty preview says why: no run yet, or the last run failed or was rejected (with its message), which is how a
  Tiered term most often goes wrong (e.g. a total-assets term needs a positive observation lag; a balance-stream term
  cannot use one).
- Workforce compensation pools' Tiered terms use income-statement flows rather than catalogue series and are unchanged.

## r304 — named Other Assets

Built directly on r303 (98242c5). Added opt-in non-earning named Other Assets, entered levels and linked source × multiplier terms, with optional configurable days-outstanding conversion. Funding, financial/audit output, Call Report, RWA and editable workbook integration. Legacy outputs are identical; no automatic engagement migration. Corrected opening/ending labels in the tiered asset source preview without changing expense timing. See R304_RELEASE_NOTES.md and R304_VALIDATION.md.
