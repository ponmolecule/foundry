# r429 — User-directed population composition

Built on r428 (2d83198). Optional feed composition allocates each channel's monthly acquisitions among named size bands. A compact matrix holds opening counts, units per customer and channel shares; it publishes reusable active band counts and an associated population count. Channel shares must total 100%; band opening counts must reconcile to the feed. Static shares and units are supported in this release.

Rounding defaults to None, preserving fractional acquisition and customer totals. Only the user's explicit Round up selection followed by Apply activates rounding of positive monthly channel × band wins. It can increase total acquisitions; this is not fixed-total apportionment. Draft edits and Cancel do not alter configuration or calculations. Existing engagements are unchanged until composition is authored and applied.

Band books retain the feed's attrition and timing convention and reconcile to the feed. Associated population is active band customers × units per customer, with no further rounding. Referral pool links retain acquisition-equation outputs before band rounding, matching the source references; selectors and source previews state this. Numbers exposes raw acquisitions, rounding increases, full monthly band additions, active counts and associated population. Calculation Audit gains an optional Population Composition sheet.

Published counts are available through the existing Customer Acquisition count source for fee streams, deposit balances and linked lending quantities. Switching a stream from an existing weighted conversion to a published count reserves the previous conversion as dormant authoring state, avoiding a second multiplication.

Validation: six new integration tests and the compact UI harness pass, including default/no-rounding identity, explicit opt-in, draft/Cancel isolation, source links, monthly/quarterly consistency, attrition, deposit and fee count consumption, workbook roundtrip and invalid configurations. Existing acquisition links, effectiveness, productivity, CAC UI (37), CAC shapeshifter (61), account activity (33), linked deposit/lending and source catalog checks pass. All inline/generated JavaScript syntax checks pass. Core, template and legacy linked-stream public outputs remain unchanged with composition absent. No real-browser visual check was available.

No client data, automatic engagement migration or save mechanism changes. ZIP contains delivery/foundry-full.bundle. BUILD_STAMP: foundry-r429-population-composition.
