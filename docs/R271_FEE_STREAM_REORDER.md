# r271 — Fee-stream ordering

Built directly on r270 (`f807a61`), retaining its unit rules, quantity links and deletion warnings. No engine implementation changes or unrelated redesign.

## Use

Use the compact drag handle beside a stream's row number to move it before or after another stream in the same card. Gold insertion markers show the destination. The same shared stream table supports Fee Product, lending and deposit fee streams. Sources and calculated output rows are not draggable. Streams cannot be dragged into another product.

For keyboard use, focus the handle and press Arrow Up or Arrow Down. The handle retains focus after moving. The selected stream remains selected even when another stream is moved around it.

## Preservation

Reordering moves the existing stream objects, with their pricing, costs, timing and schedules intact. Stable-ID and same-card named links are not rewritten. Index-keyed live paste-field IDs are remapped before the authoring snapshot, so unsubmitted schedule text follows its stream when the detail editor renders again.

Display order does not determine dependency evaluation order. The configuration hash necessarily changes when authored array order changes; this release does not promise identical hashes across two differently ordered configurations.

## Validation

- Browser test using the production shared editor: keyboard move, selection preservation, drag/drop and an unsubmitted migration-share schedule retained at the new index.
- JavaScript regression: before/after moves, boundary and no-op handling, selected object, named/stable references, draft IDs, all three owner families and cross-owner rejection.
- Engine regression: all six permutations of a three-stream chain produce identical economic output for both legacy named references and stable-ID references (financials, ratios, products and quantity values).
- Existing pinned run fingerprints remain unchanged for unchanged configurations. Existing quantity-link and authoring-state tests pass. Inline scripts compile.
- Full module/script sweep against r270 is recorded in delivery VALIDATION.md, including pre-existing failures.

Use the ZIP with the usual deployment script. The bundle main ref points to r271 and contains r270, r269 and r268 in its ancestry. No deployment has been performed by this build task.
