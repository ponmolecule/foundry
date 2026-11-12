# r488 — Shared assumptions: a visible panel instead of a hidden disclosure line

Console only. No engine change. Built on GPT's r487 (8974f05).

## The problem

On a lending product that uses a shared assumption (for example Receivable Advances using "Annual TPV per practice"), the shared editor sat behind a one-line disclosure: "▸ Edit shared assumption · changes affect every consumer". The most consequential control on the section was the easiest to miss, and the warning did not say who the consumers were.

## What r488 does

- The shared assumption is a bordered panel with a "Shared assumption" tag, its name and a one-line summary (for example "Weighted average · 4 components · annual amount").
- The panel lists every product that uses it by name and family, marks "this product", and states the count ("Used by 2 products").
- "Edit shared assumption" is a real button. Opening the panel turns the header gold, changes the button to "Done editing", and puts a note above the editor: "Changes apply everywhere. Edits here change 2 products: Receivable Advances, Practice Line of Credit." With one user it says so and notes that later users will share the values.
- Open or closed is remembered per assumption, so every product using it shows the same state.
- The settings that follow (weight source, band mapping, percentage factors) sit under a "This product only" label: they apply to this product and do not change the shared assumption.

## Verification

- New: web/tests_r488_shared_panel.cjs (panel, consumers, button state, impact note before the editor, product-only label, per-assumption open state).
- Updated: web/tests_r366_shared_lending.cjs opens the panel before checking the editor and checks the new impact wording.
- r453, r454, r455 and r340 shared-assumption tests pass.
- Reference coverage regenerated.
