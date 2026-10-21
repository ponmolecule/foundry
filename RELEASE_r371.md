# Foundry r371

Previous release: r370 / f85ad60.

## Working-copy saves

The save-current authoring endpoint explicitly preserves incomplete rate selections. A newly added loan with no yield can be saved and reopened without losing its entered production, repayment or other settings. Completion warnings are returned as advisory metadata, and the save confirmation distinguishes persisted work from rate-input readiness. The stricter default store contract remains in force for other callers; schema-version safeguards are unchanged. Preview/run validation still rejects missing yields and invalid rate paths.

Fixed lending yield validation now recognizes an active entered yield Series without requiring a duplicate legacy scalar. Empty Explicit yield paths fail with a completion error rather than acting as a zero yield. No missing rate is fabricated. Network exceptions on the normal save action now produce a visible failure message and leave the editor intact.

## Stable authoring layout

Product grouping and control fitting now finish synchronously before scroll/focus/textarea state is restored. Rerenders retain the visible clicked/changed control's position, rather than anchoring an old offscreen focused header. This prevents the raw intermediate layout from clamping the scroll offset before the lending sections are rebuilt.

Standard lending toggles retain their input nodes and anchor the section header. Funded-flow lending now keeps section bodies mounted and expands/collapses them locally, including the all-sections controls, instead of rebuilding the entire page. Native disclosure and shared textarea recovery remain in place. No new visible editing panels were introduced.

## Validation

- HTTP save-current/save-load round trip for an unfinished fixed-rate loan; original inputs preserved; strict store caller still refuses the same incomplete rate contract; running that draft still fails validation.
- Valid fixed-yield schedule with an empty legacy scalar runs successfully; an empty Explicit path remains blocked.
- 13 Python tests across working-copy saves, r369 loan accounting and r367 yield schedules pass.
- Real Chromium checks at 1440 and 768 pixels verify settled animation-frame scroll positions after rerender, anchored trajectory changes, and mounted input identity across standard and funded-flow section toggles. The same browser test against r370 reproduced an 803-pixel editor jump; the updated implementation passes a 2-pixel tolerance.
- All 35 r370 browser layout cases pass across 1920–768 pixels, including Growth/Explicit schedules, expanded settings, feature-off and legacy controls. Existing flow-lending, product-layout and Numbers inspector checks pass. Inline JavaScript syntax and whitespace checks pass.

No lending equations or posting signs changed. Packaged; not deployed.

## Updating with unsaved work open

Keep the existing Foundry browser tab open during deployment. After the updated server is running, save from that same tab before refreshing it. Refresh only after a successful save confirmation. The older page calls the same save-current endpoint, which now accepts the unfinished loan; a page refresh is not required to benefit from the server-side save fix.
