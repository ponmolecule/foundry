# Customer Acquisition — deferred fixes

Recorded 2026-10-20. These items are requested for later implementation; recording them does not change the engine, UI or deployed release.

## 1. Distinguish gross flows from interpolated net movements

Monthly-flows feeds expose modeled gross acquisitions and attrition. Straight-line stock interpolation does not establish a unique gross acquisition/attrition history. Represent any implied net movements explicitly as such; never relabel them as gross flows or invent the decomposition. Inputs requiring gross acquisitions, including per-new-customer origination and CAC, must consume eligible gross flows. Explain eligibility in source selection. Preserve existing timing semantics and saved links; do not silently convert interpolation to monthly flows.

Engagement 5 uses Monthly flows and is not blocked by this limitation. Its account acquisition, origination and CAC should continue consuming actual modeled gross new-customer flows. Account adoption is not required.

## 2. Remove manual publication of customer flows

Eligible CAC feed and channel flows should become available automatically, including existing saved feeds and newly added channels. Preserve existing stable activity IDs and downstream links; assign missing IDs consistently. Remove the Publish customer flows action and avoid a replacement setup step. Publication metadata must not create economic activity, post financial amounts or change acquisition results. Ineligible straight-line feeds need a clear explanation rather than automatic conversion or a hidden publish requirement.

Current Engagement 5 symptom: Receivable Advances Accounts exists and resolves customer counts, but its New customers flow is absent from the selector until activity IDs are assigned by the Publish action.

## 3. Polish the CAC section

Rework visual hierarchy and spacing of feed headers, opening-book inputs, attrition controls, channel navigation and calculated results. Retain the top Create feed action and independent feed expand/collapse behavior introduced in r363. Creating a feed should open it, close other feeds, and make its name easy to edit. Existing r363 presentation was judged unattractive; functional collapse controls alone do not complete this item. Preserve entered values, live links, precision and calculated summaries. Verify the finished layout visually.
