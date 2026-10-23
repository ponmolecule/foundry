# r384 — deliberate creation and cleanup of shared assumptions

The weighted-assumption creation button now opens a named Create/Cancel dialog. Opening, cancelling or repeatedly clicking the action does not create dropdown entries. Create rejects blank or duplicate names, creates one record, selects it, and opens its editor.

A discreet Manage assumptions action lists all shared entries and their linked consumers. Unused entries—including duplicates created by the earlier immediate-create button—can be deleted. Referenced entries are protected, including references from other shared assumptions and preserved configuration drafts. Unlink here explicitly clears the current field's selection; deletion remains blocked while any other consumer refers to the entry.

The same lifecycle applies to deposit and lending weighted assumptions. This is an authoring UI change; calculation engines, existing assumption IDs, values and links are unchanged. No automatic cleanup, migration or deletion occurs.

Validation: browser tests pass for create/cancel, repeated opening and submission, duplicate-name rejection, automatic selection/editor opening, protected referenced entries, explicit unlink, legacy duplicate cleanup, lending creation, and modal containment at 1440/1024/768. Existing r383 weighted-deposit/expression editor regression passes. The manager screenshot was visually inspected. No financial retesting was needed for this UI-only change.

Not deployed or pushed.
