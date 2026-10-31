# r428 — Compact linked-channel sums for acquisition pools

Built on r427 (17ecb36). A Pool × conversion Addressable pool can sum multiple selected channel new-customer flows before applying conversion once. Generic across channels/feeds; no engagement or channel-name rules. The source channels retain their own spend and acquisition equations. The consumer creates its own converted additions, without copying source spend.

Layout: reuses the existing Addressable pool row and Enter / Link control. Linked sources appear as closely spaced dropdown rows with a small × control and + Source link. Same-feed options show the channel name; cross-feed options retain feed context. No large card, table, repeated source-preview panels or additional intermediate channel. The compact footer says that live monthly additions are summed and conversion applies once.

+ Source opens one pending row in view state only. Until a source is selected, no assumption changes or recalculation are triggered. Cancelling the pending row is also view-only. Duplicate choices, same-channel and indirect cycle candidates are disabled. Stored malformed, duplicate, missing, ambiguous, circular or incompatible bindings fail closed. Removing down to one source preserves the legacy scalar link contract. Stable source IDs survive names and order changes.

The multi-source extension is link.series_ids, with link.series_id retaining the first selected source for the shared Series identity contract. All sources must be channel new-customer flows with sum aggregation. The resolver adds canonical monthly values before conversion, so monthly and quarterly engines share the same underlying economics. The existing monthly acquisition audit reports the resolved summed pool operand.

Validation:
- Four new integration tests cover the full 60-month Direct + Digital referral example, M1 .937 and M2 1.007 converted additions, full marketing spend retained, live effectiveness changes, cross-feed links, rename/reorder, monthly/quarterly equality, public validation/output/audit and single-source identity. Ten rejection scenarios cover duplicates, missing/self/cyclic sources, blank/empty/malformed selections, mismatched primary ID, wrong kind and aggregation.
- New UI harness checks compact markup, source add/select/remove, one pending row, view-only add/cancel, duplicate/cycle guards, and scalar compatibility.
- Existing channel-link suite, effectiveness tests (5), CAC UI (37), CAC shapeshifter (61), acquisition Numbers and all inline/generated JavaScript syntax checks pass. CAC UI harness now sends its script on stdin to avoid the platform argument-length limit as the source grows.
- Core bank, universal template bank and legacy linked-stream fixture full public outputs are identical to r427.
- No real-browser visual check was available. Controls reuse the existing form styling and bounded flex layout.

After deployment, open EMR Sourced Practices. Keep Direct selected, click + Source, select Digital, and keep conversion at 25%. Expected M1 EMR additions = (0.28 + 3.468) × 25% = .937.

No save mechanism changes or client data. ZIP uses delivery/foundry-full.bundle. Verify BUILD_STAMP = foundry-r428-acquisition-pool-sources.
