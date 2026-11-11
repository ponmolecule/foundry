# r481 — Operating Expense: warn before leaving Detailed, and name the cause when it breaks a run

Console only. No engine, validation or saved-input change.

Workforce roles and expense categories live inside Detailed Operating Expense. Switching to Simple (or turning the module off) parks that block as a draft, so every input elsewhere that links to its Series stops resolving at once. The run then failed with one message per broken link (11 in the reported case) and no mention of the cause.

**Before switching.** Simple overhead and the module-strip Off now check for inputs outside Detailed Operating Expense that link to its Series (workforce headcount, total workforce, workforce expense, expense categories and category flows). If there are any, a confirmation names them by area before anything changes:

> Switch Operating Expense to Simple? 11 inputs link to Operating Expense series such as workforce headcount or expense categories (fixed assets, account activity, 1 deposit, 3 lending products, 5 CAC feeds). They will stop resolving, and figures will be unavailable, until Detailed is restored. Your Detailed settings are kept as a draft.

Keep Detailed (or Escape) changes nothing. With no linked inputs, the switch is immediate as before.

**When a run fails for this reason.** The banner leads with the cause and the fix:

> Figures unavailable. Operating Expense is set to Simple, so its workforce and expense-category series are unavailable. 11 inputs link to them (…). [Restore Detailed]

Restore Detailed brings back the parked block with every role, category and Series ID. The full message list sits behind "All N messages". Any error not caused by the parked block is still shown under "Also:". Messages the server splits on ";" ("… resolved to 0 matches" / "expected exactly one") are rejoined. Errors unrelated to Operating Expense keep the existing plain banner.

The count is of inputs that link directly. Products that fail only because they consume a broken input (for example a lending product fed by a CAC feed) appear in the full list, not in the count.

Validation: web/tests_r481_opex_guard.cjs (7 checks against the engine's real messages for the universal template with Detailed parked: dependents scan, guard text, Keep Detailed and Escape leave the config untouched, confirm parks the draft, cause-first banner with rejoined messages, Restore Detailed restores roles and categories, module-strip Off guarded, unrelated errors and no-dependent switches unchanged).

Full suite on 0ff8cda9: 319 files. Two harnesses located nieOff by its old signature and were updated (tests_growth_ui also loads the guard helpers); both pass on the final commit. The remaining 12 failures are the same 12 that fail on r480 and r479.
