# Foundry r399 — Customer-flow discovery without publication-map edits

Built directly on r398 / 3989482. No engine, save protocol, revision checks, recovery isolation, financial defaults or page-layout changes.

## Correction

The automatic customer-flow publisher in `_ensureLinkableSeriesIds` wrote `activity_series_ids` onto existing feeds and channels whenever source menus or Customer Acquisition rendered. An engagement with another real unsaved edit could therefore acquire extra Governance differences just by browsing. The render-drift rebaseline was not a solution: it can mask clean-state drift and does not remove extra differences against the stored configuration.

Read flow IDs through `_cacFlowIds` instead. Missing publication maps are derived from the existing feed customer-count/channel new-customer identities, matching Python `account_activity.ensure_flow_ids`; existing custom maps take precedence. No flow maps are written by those browsing paths. Backend resolution already supports these absent maps. Existing source-identity creation for legacy items is unchanged; this is not a blanket audit of every historical renderer's normalization.

Update loan-production gross-flow filtering, channel opening controls and feed-removal link detection to consume the derived IDs too. Gross flows stay available without a publish action. Straight-line feeds remain ineligible; no net flow is relabelled as gross.

## Validation

- New targeted regression: byte-identical configuration on repeat source browsing, with both a clean and already-edited baseline; existing custom IDs retained; exact IDs match Python publishers; genuine input changes remain; straight-line eligibility and derived dependency detection checked.
- New real-browser regression: Customer Acquisition render, feed navigation and channel editing-view opening do not add publication maps; clean lifecycle stays clean; an actual opening-customer edit remains modified without extra changes on render.
- Existing r393 acquisition layout and r396 feed removal browser regressions pass.
- Existing r389 real-HTTP save/recovery regression passes: stale-tab rejection, edits retained on refusal, isolated browser/server/history recovery, repeated saves with stripped headers, collision refusal and original records preserved.
- All seven r388 backend save-safety tests pass. Full inline JavaScript syntax and git whitespace checks pass.

No migration or re-entry is required. Existing falsely added publication metadata is valid and is not removed from saved engagements. This release prevents its browse-time creation. It does not change the intentionally different scope of the legacy leave-dialog and Governance diff engines or hide substantive balance-model changes. Pre-existing fingerprint pins and the old account-activity test harness remain separate maintenance work.
