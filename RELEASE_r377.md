# Foundry r377 — compact expense-category exclusions

Built on r376 / b887a61. Packaged, not deployed.

Named expense-linked Other Liabilities components now choose excluded operating-expense categories through a compact multi-select dropdown. The closed control shows the number excluded and the selected category names as compact chips. The full checkbox list appears only in a bounded, scrollable popup, so a long expense list no longer expands the authoring page.

The native popover supports keyboard activation, Escape with focus returning to the trigger, and click-outside dismissal. Its viewport position avoids clipping by the component card; selected names/count update without remounting the form or closing the list after each selection. Existing exclusions, stable category IDs and all calculation semantics are preserved. Missing category references remain visible and removable.

Validation: real Chromium checks with 22 categories cover multi-selection, immediate selected-name/count updates, stable page height, scroll bounds, Escape/focus, outside dismissal, 1440/1024/768 viewport containment, unchanged configuration after toggling back, and category rename/reorder identity. Open/closed screenshots inspected; no runtime errors. Existing ten Other Liabilities UI checks and JavaScript syntax/whitespace checks pass. No engine changes or engagement migrations.
