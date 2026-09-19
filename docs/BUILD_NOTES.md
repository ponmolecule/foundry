
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
