# r385 — restore the r382 application baseline

This release reverses the application changes in r383 and r384. Runtime and web files are identical to r382. r383/r384 remain in Git history and their release tags; this is a forward rollback commit so it can deploy over those releases without resetting remote history.

Restored behavior includes the original customer-linked deposit amount editor, expense Formula authoring and source catalog. The added weighted-deposit consumer, expression-tree expense builder and r384 shared-assumption lifecycle manager are removed. Existing weighted lending mechanics from before r383 remain as they were in r382.

The Engagement 5 source clarification notes are preserved. The user has elected to enter Operating Accounts afresh; no engagement configuration is automatically converted or stripped. This rollback does not contain a replacement implementation.

The replacement design and code capability assessment are recorded in docs/r382-operating-accounts-reassessment.md: keep live acquisition links; use an optional local breakdown in the existing balance field; consider allocated pricing within Pricing; extend the existing expense Formula and typed observations instead of adding a separate expression-tree tool. These are design recommendations, not implemented features in this release.

Validation: application/runtime files match the r382 tag exactly; all 12 core/parity fixture full JSON outputs match r382. Ten r380/r381 deposit tests pass. The existing source-catalog regression and deposit-pricing browser regression pass.

Not deployed or pushed. Deployment should show foundry-r385-r382-baseline, rather than r383 or r384.
