# r388 save and recovery behavior

## After deployment

Open Foundry in a fresh browser tab. Select the already-created version ending “Recovered 2026-10-23 00:40”. Its five deposit products and two Operating Account fee streams were verified on the server during recovery. Confirm its calculated values before resuming the seven outstanding Operating Account cost items. No products or assumptions need to be re-entered as part of this update.

Old tabs will receive a save-protocol refusal when they try to save. Their contents are not written. If an old tab contains separate unsaved work, download its backup before closing it; import that work into the new application as a separate version.

## Normal saves

Opening a named engagement reads the configuration and its revision together. The editor retains that revision separately from the editable model. A normal save updates the loaded identity only if the stored revision still matches. A new version name creates a separate record; a conflicting existing name is refused when the editor has not read that version.

If a save conflict appears, the local edits remain. Open the latest saved version to continue from it, or save the local work under a genuinely new version name. There is no force-overwrite action. A revision is checked inside the same file lock used for replacement, so checking and writing cannot race between supported server workers.

## Recovery copies

A checkpoint records when a copy was captured, not when its contents were last the newest saved version. Previous copies are therefore offered through a passive Review notice. Review identifies the browser/server origin, checkpoint time and corresponding server revision where available. Old copies without provenance are explicitly unverified. A network failure does not label a copy current or delete it.

Open saved version resumes the named server record. Open recovery copy always creates a new, unsaved recovery identity. Saving that recovery copy cannot replace the original simply by using its name. Different recovery copies are retained rather than blindly purged on another tab's successful save.

Server recovery drafts are also page-instance-specific. Legacy shared slots remain readable, but selecting one uses the same isolated recovery path.

## History recovery

Governance → Change history shows each recorded version. Expand Build-out if necessary. Open copy reads that version and opens a separate unsaved recovery copy. It does not replace the saved engagement. Inspect the products and calculations, then save the recovered copy to persist a new named version.

## Persistence boundary

The file store preserves the predecessor before atomically replacing the current JSON file. If that predecessor cannot be preserved, the replacement is refused. If recording the new history entry fails after the new file is durable, the save response warns about history; the current file and its predecessor remain available.

The revision-aware protocol protects public save endpoints, including requests from older clients. Trusted internal store callers and operator scripts remain administrative interfaces and must be used deliberately. Existing historical configurations are not silently converted into the current modeling representation. Financial data, links and equations are unchanged by this release.
