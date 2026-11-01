# r438 — "Schedule" everywhere a path holds a list of values

Built on r437 (2392484). Wording only: stored values are unchanged (`explicit` / `explicit_schedule`), so saved models and calculations are unaffected.

- Every path option, list chip and summary that said "Explicit" or "Explicit schedule" now says **Schedule** — the same word as the segmented buttons: path dropdowns, workforce and expense-category Paths chips, acquisition summaries ("Schedule · 12 values / quarter"), workforce run summary, value-count summaries, hints and messages.
- The reference index and Guide Me use the same word (Guide Me's trajectory label and its step instructions, e.g. "Set Count path to “Schedule”").
- Exports: the acquisition audit column is "Scheduled new customers"; data-check locations read "Schedules."
- Names where "explicit" meant "entered directly" were renamed to read naturally rather than replaced blindly: the acquisition method is **Scheduled customers**, and "Scheduled driver path". "Explicit recognized balances" and "Explicit series" keep their wording; they are not paths.
- A scan of every Configuration module, product step and fee-stream step finds no visible "Explicit" path wording left.

Validation: tests_r438_schedule_vocabulary; three existing tests updated for the new word (count-breakdown path options, weighted counts, Guide Me steps). Full suite: see below.

ZIP contains delivery/foundry-full.bundle. BUILD_STAMP = foundry-r438-schedule-vocabulary.
