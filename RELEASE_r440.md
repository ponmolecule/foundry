# r440 — Review fixes for r433–r439

Built on r439 (806936a). Fixes the five issues from the external review of r433–r439, plus a wording correction and a 4px layout overflow.

**Engine/calculation change: none.** No change to engine code or to any computed number for a configuration that ran before. One validator rule is narrower (below), so a configuration that previously passed validation and then failed in the engine now fails at validation with a clear message.

1. **Validator, distributed-balance fees.** A funded-flow loan with a fee stream on `distributed_balance` was accepted without a repayment profile; the engine then stopped with "distributed balance is unavailable". The validator now requires an allocation group or a repayment profile. Profiled loans keep the fee.
2. **Clear left pasted text behind.** Clear on a schedule emptied the values but not the paste box under the grid. It now empties every paste draft for that path.
3. **Blank schedule cell.** Blanking one period left the old value in force with no sign. It is now refused: the stored value shows again and the status line says "Each period in a schedule needs a value. Enter a number, or use Clear to remove the whole schedule."
4. **Step / Smooth highlight.** The highlight now follows the stored choice even when the edit does not redraw the page.
5. **Parity pins.** Pinned divergence cells are now checked on every run, not only when a cell differs. A reversion to the predecessor's value fails the test (verified by running against the predecessor's snapshots: 5 fixtures fail, as intended).
6. **Wording.** r152 changed NIM to an average-total-assets basis, not an earning-asset basis. Corrected in divergences.json, tests_parity.py and RELEASE_r436.md.
7. **Weighted-table overflow.** The last column of the weighted table is a fixed 34px instead of 4%, removing a 4px horizontal overflow at 1440px (also present at r432). No overflow at 1100, 1366, 1440 or 1536.

New tests: `foundry/v2/tests_r440_review_fixes.py`, `web/tests_r440_review_fixes.cjs`.

ZIP contains delivery/foundry-full.bundle. BUILD_STAMP = foundry-r440-review-fixes.
