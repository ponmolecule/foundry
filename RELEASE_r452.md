# r452 — Population composition Apply and result refresh

Fixes clicks lost when committing composition fields: draft name, opening, units and share edits update totals in place without replacing input or action nodes. Asynchronous result refresh also retains an open composition draft. Feed sidebar counts now refresh with results.

Fixes accepted decimal-share totals such as 100.000001% accumulating a reconciliation residual. The allocator normalizes only shares already accepted by the existing validation tolerance; authored values, IDs, count flows and rounding selection remain saved unchanged. Material share errors still fail validation. Configuration pages display calculation failures instead of unexplained missing figures, and clear the notice after recovery.

Validation: real-browser single-click Add/Apply after editing, latest-field retention, draft-node preservation on result refresh, acquisition headline/sidebar refresh, expense headline recovery, and configuration serialize/reload equality. Population composition and live deposit regression tests pass; workforce growth browser regression passes. Existing fixture fingerprints checked separately.

Deployment: built on r451. No engagement migration, fixture reset, or storage changes. Save the named engagement before deployment; unsaved composition drafts require Apply first. This package does not contain the client engagement. Verify its saved band composition, Marketing schedule and Digital channel after deploying and reopening the same engagement. Saved-data preservation is tested locally, but the actual deployment and client engagement require that post-deploy check.
