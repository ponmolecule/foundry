# r450 — Keep full precision in Amount per customer cells

Built on r449 (1ca9656). Fixes the review finding on r449: an editable cell displayed a rounded value (404.71) and an incidental edit, such as adding a space and leaving the field, saved the rounded value, losing the stored 404.71192264.

- A cell still shows the short value (404.71 $000s, 73.54%), but on focus it shows the stored value in full (404.71192264, 73.5414627) and selects it.
- An unchanged number is never written back: trailing spaces, re-typing the same value or tabbing through leave the stored value exactly as it was. Leaving the field restores the short display.
- A real edit saves what was typed, at full precision.
- Applies to every editable cell in the table: amount, entered share and balance share.

**No engine or calculation change.**

Tests: tests_r449_deposit_amount_ui reproduces the finding for amount, share and balance share (focus, add a space, Tab: stored value unchanged) and checks a real edit still saves; tests_r389_authoring is strict again (a focused amount equals the stored value to 1e-9).

ZIP contains delivery/foundry-full.bundle. BUILD_STAMP = foundry-r450-precise-cells.
