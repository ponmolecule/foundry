# Foundry r402 — Recovery review on demand

Direct continuation of r401 / 45f400a. Includes the r399 browsing, r400 Income Statement display periods and r401 opening-notice corrections.

Remove the automatic Previous recovery copies notice from startup and reauthentication. The old notice was an `aside`, and inherited the application's sidebar presentation on some layouts, producing a large blank panel. No recovery notice element is now created automatically.

Engagement menu > Recovery copies… opens the existing review dialog on demand, refreshing the server's recovery list at that point. An empty list has a clear closeable empty state. Existing checkpoints are not deleted. Opening a checkpoint still uses a separate recovery name and clears the original engagement's overwrite token. Revision checks, history, checkpoint creation, session-expiry warnings and save-failure handling are unchanged. Reference's recovery topic documents the menu entry.

Validation: dedicated real-browser test checks no automatic banner/dialog with a previous checkpoint, preservation before/after review, engagement-menu access and empty-state dismissal. Updated real-HTTP r389 recovery test exercises on-demand access and retains stale-tab refusal, checked repeated saves, isolated browser/server/history recovery, name collision refusal, import token invalidation and clean reload without auto-restoration. All seven r388 backend save-safety tests pass. Inline JavaScript syntax and git whitespace checks pass. No engine or financial calculation changes. No data re-entry required.
