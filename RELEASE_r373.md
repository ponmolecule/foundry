# Foundry r373 — session continuity and recovery

Previous release r372 / c6e7482. Includes the subsequent Engagement 5 source-clarification documentation commit.

## Behavior

- A valid session renews during active foreground use. The existing lifetime, HttpOnly/SameSite/Secure cookie policy, and authentication checks remain in force; expired sessions require sign-in.
- Session health is checked every minute and on return to the tab. API 401 responses produce a persistent recovery notice rather than leaving the user unaware that server access has stopped.
- Explicit Save on an expired session offers an in-place password prompt. Reauthentication is bound to the original account, never calls boot or reloads the workspace, and retries the requested save once against the still-open engagement. Switching engagements meanwhile cancels that automatic retry. Passwords are cleared from the input and never placed in browser draft storage.
- Browser recovery copies checkpoint committed configuration edits, including edits to previously saved engagements that the old server recovery slot skipped. Copies are scoped to account and tab; another account's copies are not offered. After sign-in/boot, restoration requires an explicit choice and is marked unsaved. A successful save retires the corresponding copy. The expired-session notice and prompt include a direct JSON backup download.
- Quota/private-mode storage failure and connection failure are visible; the interface does not describe a failed browser write as protection. Browser recovery is local to the browser and is not a server save or a guarantee against cleared browser storage. Configuration fields committed to the model are captured; uncommitted text buffers are not a separate form-history store.
- Authentication failure retains last successful calculation results with a stale-results explanation, including the workforce summary, instead of clearing them. This does not change treatment of genuine invalid model inputs or solve unrelated summary failures.
- Current-save requests declare the expected account; the server refuses a cross-account save if another tab changes authentication. Existing clients without that field retain compatibility.
- Explicit Save compares the submitted snapshot with the live inputs before marking clean. Edits made during the request remain dirty and recoverable. Save-and-switch also refuses to discard newer edits.

## Validation

- 15 Python tests pass: authenticated renewal, expired/absent-token rejection, cookie properties, same-account reauthentication, cross-account save refusal, prior working-save and lending regressions.
- Real Chromium verifies saved-engagement recovery, input/result retention after 401, in-place reauthentication and one retry, password clearing, account-scoped draft offers, explicit restoration marked unsaved, in-flight edit preservation, offline warning and storage-quota warning.
- Existing real Chromium authoring stability checks pass at 1440 and 768 pixels. All 35 lending layout cases pass at 1920–768 pixels.
- Recovery prompt visually inspected; normal authoring has no new permanent panels. No engine equations, engagement migrations or numerical assumptions change.

Packaged; not deployed. Preserve a downloaded configuration before updating an older page; the new client protections take effect after that page is reloaded.
