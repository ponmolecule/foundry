# r409 — Deliberate formula-cost creation and stable product selection

The + Formula cost stream action now opens a small name dialog. It does not create a stream, change the model, or invoke refresh while the dialog is open. Create is disabled for blank/whitespace names. Cancel and Escape leave the configuration unchanged. Submitting a name creates exactly one stream with that name, selects it and opens its cost formula. Duplicate names within the same product are rejected. A changed engagement/owner while the dialog is open prevents stale creation.

A reconciled Opex transfer replaces the configuration's product objects. The Products navigator previously interpreted those new object identities as a newly added product and selected an unrelated first product. Formula creation and transfer now explicitly preserve the target product, Fee streams view and selected formula stream, and mark the replacement objects as known to the navigator.

No expense arithmetic, server save behavior, or existing stream data was changed. Existing unnamed/default-name streams are not deleted automatically; users can remove unwanted placeholders explicitly.

Validation: full Products-page browser test covers cancel, Escape, blank and duplicate names, named creation, actual reconciled transfer, and repeated rerenders without navigation drift. Existing r408 transfer/editor, engine/API and formula checks pass. The dialog was visually inspected.
