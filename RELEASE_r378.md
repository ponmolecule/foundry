# Foundry r378 — inclusion-based Accounts Payable authoring

Built on r377 / 678401b. Packaged; not deployed.

The payable expense-base dropdown now says Include categories. Checked categories contribute to the liability base; the closed control shows the included count and selected names. Long selections show three name chips and +N more, with the full checked list in the scrollable dropdown. New aggregate expense sources and formula terms start with no selected expenses; their expense-flow multiplier defaults to one.

Explicit included stable IDs are resolved by the engine and exported in the existing formula detail and assumptions workbook. Empty, missing, duplicate, incompatible or ambiguous selections fail closed. Existing expense-timing overlap checks remain in force.

Saved r376/r377 exclusions remain readable with identical financial calculations. The UI shows their equivalent inclusions without rewriting the saved model on render. Editing the selection writes explicit included IDs and removes the old exclusion list. Existing exclusions retain their historical all-except semantics until edited; explicit inclusions do not automatically acquire later-added categories. Category renames/reordering preserve links. No numerical assumptions or pasted schedules are changed automatically.

Validation: five new backend tests cover monthly/quarterly financial equality between legacy and equivalent explicit selections, live edits, future-category behavior, stable identity, invalid/ambiguous selections, public formula detail and assumptions export. Six preceding deferred-enhancement tests pass. Real Chromium checks cover legacy display without configuration mutation, empty new selections, checkbox inclusion behavior, selected-name/count updates, long-list compactness, Escape/focus return, outside dismissal, 1440/1024/768 containment and stable IDs after rename/reorder. Open/closed screenshots inspected. Existing deferred-feature browser checks and liability UI checks pass; inline JavaScript syntax and whitespace checks pass.
