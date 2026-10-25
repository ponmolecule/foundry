# Foundry r401 — Clear completed engagement-opening notices

Direct continuation of r400 / 01cdc0b. Includes r399 browsing correction and r400 Income Statement display periods.

The engagement-menu wrapper displayed Opening engagement before checking the unsaved-work guard. Its success branch was unreachable because openEngagement awaited the inner load but never returned the success value. The busy banner could therefore survive a successful load or merely opening the discard guard.

Move the busy notice to the actual _openEngagementNow operation and clear it in finally, guarded by the notice's identity. Return the load result through openEngagement and engMenuOpen. Success leaves no persistent status strip. HTTP failures retain their error; network/read failures get an error instead of an immortal busy strip. Finishing a load cannot clear a newer unrelated notice. Recovery-copy messages keep their existing separate-copy explanation. No model, financial, save/revision or recovery-permission changes.

Validation: real-browser tests exercise successful menu open/result propagation, hidden status after completion, unsaved guard without fake busy state, HTTP/network errors and preservation of a newer notice during an in-flight load. Real-HTTP r389 save/recovery regression passes, including stale-tab refusal and isolated recovery. r400 Income Statement view regression passes. Inline JavaScript syntax and whitespace checks pass.
