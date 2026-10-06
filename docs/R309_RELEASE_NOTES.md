# r309 — New products open on Setup

Built on r308 (a79d70b). New products open on Setup, including when the previous product was on Fee streams. The default tab is Setup when no valid tab has been selected. Deliberately selecting Fee streams still survives ordinary rerenders. No configuration or engine arithmetic changed.

Validation: actual console HTML in headless Chromium with API/auth stubbed: new fee product resets prior Streams selection to Setup; clicking Fee streams works and persists through rerender; missing tab defaults to Setup. git diff --check passes. Full engine suite not repeated for this two-line presentation change.
