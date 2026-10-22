# Foundry r376 — deferred authoring enhancements

Built on r375 / f4f2232, including the subsequent enhancement-log commits. Not deployed.

All six deferred enhancements are implemented:

1. Named Other Liabilities components can link recognized operating-expense categories (one category or an aggregate with exclusions). Optional Days payable, Days per year and multiplier reuse the receivable day-conversion grammar. Audit and assumptions-workbook paths include day inputs and exclusions. Existing pasted schedules are preserved. No expense is posted twice; overlapping deferred category settlement is rejected. Payroll, product costs, depreciation and overall gross-up remain separate from the explicitly labeled category aggregate.
2. Eligible CAC feed/channel gross flows are available automatically, without Publish. Existing IDs and links are preserved; missing identities are assigned consistently as publication metadata.
3. CAC summaries use stable result containers and retain the last completed run during incomplete inputs or failed requests, visibly marked stale. New feeds get an explicit waiting state. Cached results are scoped to the current engagement instance.
4. CAC feed identity/opening inputs are aligned; help and channel-opening allocations are collapsed. The top Create feed action stays visible. Each feed expands independently; creating a feed opens it and closes others. The positional details-restore bug and detached toggle events no longer override feed disclosure.
5. Straight-line stock interpolation is explicitly distinguished from gross flows. Its economic path is preserved; ineligible gross-flow sources are explained rather than relabeled or silently converted.
6. Entered income and shared monetary explicit editors show $000s beside the paste control and closed schedule. Amount basis and schedule cadence are distinct; existing values are not rescaled.

Validation: six new backend tests cover automatic stable IDs, unchanged acquisition economics, legacy interpolation, live category expense liabilities, additive expense inclusion, no duplicate P&L, source/exclusion/basis failures, overlapping settlement and both engines. Existing acquisition (61), intra-period timing (63), account activity (33), Opex (121), Other Liabilities (24), Other Assets (7), CAC UI (37), liability UI (10), source-catalog checks and annual compensation (6) pass. Browser checks at 1440/1024/768 verify CAC control containment, creation/disclosure, automatic sources, stale summary recovery, rename continuity, mounted input nodes, payable controls and explicit monetary units. Screenshots inspected. Monthly and quarterly Profile A plus Profile B legacy financials/products/annual/workforce/presentation/faithful outputs match r375 exactly for comparison fixtures. Inline JavaScript syntax and whitespace checks pass.

Boundaries: payable day conversion uses a native-period average-flow convention, not invoice aging; explicit balances remain available. Straight-line gross-flow eligibility is deliberately not fabricated. No engagement-specific assumptions or automatic schedule rewiring are introduced.
