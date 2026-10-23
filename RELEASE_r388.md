# r388 — revision-checked saves and isolated recovery

Built on r387. Existing configurations and calculations are retained. No engagement data migration or re-entry is required.

## Corrected failure path

A previous recovery copy could survive a newer save, be described as unsaved work without a server comparison, retain the named engagement's identity, and then overwrite its newer saved configuration. The incident history establishes that a good configuration existed before an older-format configuration replaced it; it does not identify the exact originating browser copy.

## Protection

- Both public engagement-save endpoints require the revision-aware save protocol. Old application tabs are refused with an upgrade message. A missing revision is create-only; it cannot replace an existing engagement.
- The editor keeps the revision read from the server outside the model configuration. Saves compare that revision under a cross-process file lock. Two writers starting from one revision cannot both replace it. Conflict responses leave edits in the browser and do not rewrite the stored file or history.
- Current files are written via flushed, fsynced temporary files and atomic replacement. The predecessor is recorded before replacement; failure to preserve it refuses the overwrite. A failure to append the new history record after a durable save produces a history warning while retaining the predecessor.
- Local browser checkpoints retain their base revision. Startup shows a passive review notice, not a claim that the previous session failed to save. Reviewing a copy checks the related server revision and distinguishes changed, unknown, unavailable and current bases.
- Browser, legacy/server and historical recovery always open under a fresh recovery name without overwrite permission. Even renaming the copy back to an existing engagement cannot grant a missing revision.
- Autosave recovery slots are unique to the page instance and use their own checked revisions. Successful saves do not blindly delete unrelated shared recovery copies.
- Governance → Change history → Open copy opens a historical snapshot as a separate, unsaved recovery version. This removes the need for an operator terminal to recover a recorded version.
- A loaded engagement retains its actual stored identity when saving, including operator-created recovery files whose slug differs from the display name. Importing/replacing a configuration invalidates the old read token.

## Verification

- 31 backend cases pass: seven new save/recovery tests, six prior working-save/session tests and eighteen deposit/linked-calculation regressions.
- The new tests cover old-client refusal, create collisions, both public save routes, stale revisions, actual separate-process contention, user-scoped historical reads, recovery-copy creation, failed predecessor backup, failed atomic replacement, history-warning behavior, restart/read revision stability and identical financial output after a complete linked-model save/load.
- The browser integration test starts the actual FastAPI app with temporary storage. It verifies two-tab conflict handling, edit retention, passive recovery notice, freshness comparison, independent browser/server/history recovery, collision refusal, saving a separate copy, import token invalidation, custom stored identities and reload behavior.
- Prior session-expiry/in-place reauthentication tests and r387 deposit-authoring tests pass. Twelve existing history checks pass, with the old “ignore history failure” expectation deliberately changed to predecessor preservation.
- All twelve complete core/parity fixture outputs match r387. No financial engine equations changed.

Not deployed or pushed. A recovered engagement must still be opened and verified after deployment. This addresses the identified overwrite mechanism; it is not a promise of immunity from every possible storage or infrastructure failure.
