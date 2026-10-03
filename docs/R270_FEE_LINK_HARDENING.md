# r270 — Fee-link hardening

Built directly on r269 (9e2bd61), which is built directly on r268 (66835a5c). Compatible with fast-forward deployment from either release. No unrelated redesign.

## Changes

- A single structural unit classifier is used by the legacy fee evaluator and the cross-product planner. Stale monetary-flow metadata on a nonconstant driver cannot override its actual source type. Monetary conversion coefficients, account/count sources and balance stocks retain their legacy precedence.
- Removing a linked stream or a product with linked streams displays the affected consumers before deletion. Cancellation leaves the configuration untouched. Confirming deletion preserves the consumers' references so the existing missing-source validation blocks runs until those links are repaired; it does not silently clear or zero them. The warning includes direct stable-ID deposit/lending references and same-card named fee references. It is not a full transitive impact explorer.
- Linked stream summaries, Activity tab summaries and provenance show the source product and stream name rather than its internal ID. The persisted reference remains the stable ID.

The monthly-to-quarterly calculation scope from r269 is unchanged: direct entered monthly monetary flow multiplied by monthly shares is evaluated month by month before aggregation. This release does not reconstruct arbitrary derived quarterly flows into monthly observations.

## Verification

Shared-rule regression cases cover stale nonconstant flow tags, source types and conversion precedence. An additional seeded comparison of 2,000 eight-stream configurations matches r269's legacy unit classifier exactly. The complete output of the linked fixture matches r269. Existing pinned fingerprints remain unchanged.

Deletion tests cover dependency labels, cancellation without mutation, confirmed deletion retaining the consumer reference, same-card references and readable source names. Native Chromium checks exercise the production selection and deletion handlers. Existing cross-product quantity, deposit retention and lending/deposit stream tests pass.

See delivery VALIDATION.md for the final module sweep against r269 and its baseline failures. This ZIP is for deployment by the user, not an already deployed service.
