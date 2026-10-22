# Customer Acquisition — deferred fixes

Recorded 2026-10-20. All four items are implemented in r376, pending deployment. Original requests below are retained as scope history.

## 1. Distinguish gross flows from interpolated net movements

Monthly-flows feeds expose modeled gross acquisitions and attrition. Straight-line stock interpolation does not establish a unique gross acquisition/attrition history. Represent any implied net movements explicitly as such; never relabel them as gross flows or invent the decomposition. Inputs requiring gross acquisitions, including per-new-customer origination and CAC, must consume eligible gross flows. Explain eligibility in source selection. Preserve existing timing semantics and saved links; do not silently convert interpolation to monthly flows.

Engagement 5 uses Monthly flows and is not blocked by this limitation. Its account acquisition, origination and CAC should continue consuming actual modeled gross new-customer flows. Account adoption is not required.

## 2. Remove manual publication of customer flows

Eligible CAC feed and channel flows should become available automatically, including existing saved feeds and newly added channels. Preserve existing stable activity IDs and downstream links; assign missing IDs consistently. Remove the Publish customer flows action and avoid a replacement setup step. Publication metadata must not create economic activity, post financial amounts or change acquisition results. Ineligible straight-line feeds need a clear explanation rather than automatic conversion or a hidden publish requirement.

Current Engagement 5 symptom: Receivable Advances Accounts exists and resolves customer counts, but its New customers flow is absent from the selector until activity IDs are assigned by the Publish action.

## 3. Polish the CAC section

Rework visual hierarchy and spacing of feed headers, opening-book inputs, attrition controls, channel navigation and calculated results. Retain the top Create feed action and independent feed expand/collapse behavior introduced in r363. Creating a feed should open it, close other feeds, and make its name easy to edit. Existing r363 presentation was judged unattractive; functional collapse controls alone do not complete this item. Preserve entered values, live links, precision and calculated summaries. Verify the finished layout visually.

## 4. Investigate recurring disappearance of the CAC summary table

User reports that the calculated customer-base roll-forward summary has disappeared again after previously being restored. Investigate result availability, rendering/refresh behavior and feed disclosure state; the cause is not yet established. Restore reliable visibility of the calculated summary for feeds with results, including after edits, reruns, reloads and collapse/expand. Do not assume a missing table means zero customers or require users to recreate feeds. The previously deferred missing-results placeholder is a separate item; this report does not establish that a placeholder alone fixes the recurrence.

## r376 completion — 2026-10-22

- Eligible Monthly flows feeds/channels receive missing stable publication metadata automatically; authored IDs survive. Straight-line stock paths keep their economics and do not publish fake gross flows. Catalog discovery and the feed editor explain eligibility.
- Removed manual publication controls. Counts and expense/revenue posting equations are unchanged.
- Aligned feed identity/opening fields, kept top Create feed and independent feed disclosure, moved explanatory material and optional channel-opening allocation into collapsed details. No additional account-adoption requirement.
- Feed disclosure no longer uses the page-wide positional details restore. New feeds open while others close; detached toggle events cannot overwrite the state.
- Stable-ID result containers update directly. Last completed summaries survive validation/network failures with an explicit stale message; a feed with no completed run gets an explanatory state instead of a disappearing panel. Recovery, rename, input-node preservation and independent disclosure are browser-tested. The cache is scoped to the current in-memory engagement; a reload obtains a new engine run, never another engagement's cached figures.
