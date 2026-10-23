# r387 — deposit authoring and practical period overrides

Built on r386. Existing engagement data does not require re-entry.

- Deposit Pricing keeps Fixed/Floating and its dependent rate controls in one visual group. Fixed deposits reuse the existing Flat/Growth/Explicit Series editor, including annual/quarterly/monthly source cadence, Step/Smooth resolution where supported, bulk paste and a saved preview. Annual rate levels are accrued by the existing deposit engine; individual period overrides still apply last.
- Deposit amount breakdowns are compact tables: component, dollars per customer, weight, remove. Per-field path controls open on demand. Flat totals show the weight sum and weighted per-customer amount, with a clear invalid-weight message. Existing assumptions, links, shares and precision are retained.
- Product period overrides support a selected field, inclusive range fill, range clear and row/column paste from a chosen starting period. Validation happens before the batch mutates the model; a zero is a genuine override, while blank tab-separated cells remove overrides. Existing overrides are summarized as contiguous ranges. The original individual-period grid remains available under a closed detail view.
- Dollar-valued inflow overrides use $000s consistently in both the range tools and the individual grid. Stored raw-dollar overrides do not change on load.

Compatibility: scalar fixed deposit rates remain valid and unchanged; no schedule is created by rendering. Switching Fixed/Floating retains inactive authored values. Schedules use the existing Series resolver in both engine profiles. A finer source cadence than the model fails closed, just as existing entered level schedules do. Period overrides are exceptions, not a forward-fill schedule. No source-model accounting assumptions have been changed.

Validation:
- 18 backend cases pass across r387 deposit schedules, r386 linked breakdown/expense calculations, r380 customer-linked deposits and r381 interest minimums. New cases verify annual paths, final override precedence, actual accrued interest, legacy scalar behavior, floating gating, growth, invalid paths and both quarterly engine profiles.
- All 12 core/parity fixture outputs are byte-for-byte identical as canonical JSON to r386.
- Browser checks pass for flat table editing, per-field paths, adjacent pricing controls, legacy-value seeding, yearly schedule paste, saved previews, Fixed/Floating preservation, range/paste/clear, atomic validation, zero/blank handling, dollar units and save/reload. Layouts are checked at 1440, 1024 and 768 pixels and inspected visually.
- Existing r381 pricing and r386 authoring browser checks pass. All 18 existing Formula layouts and 121 operating-expense checks pass.
- The older r367 lending-yield test's configuration-immutability assertion fails because it initializes acquisition flow IDs. The same failure was reproduced unchanged on the r382 baseline; it is not introduced by r387. No claim is made that the entire historical test suite passes.

Not deployed or pushed. See docs/r387-deposit-authoring.md for entry instructions.
