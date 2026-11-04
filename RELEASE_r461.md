# r461 — Linked acquisition spend

Flat streams with Product cost — periodic amount now offer **+ Add linked source**. Select total acquisition spend for a feed or spend for an individual channel, then set Allocation (%). Add multiple sources to sum allocated dollar flows without formula authoring. This replaces the entered amount path; source flow cadence is preserved and quarterly models sum monthly spend exactly once. Ordinary entered costs remain unchanged.

The publisher covers acquisition spend calculated by all existing acquisition methods, including spend/CAC, explicit acquisitions with authored spend, FTE/productivity and pool conversion. It reuses the canonical acquisition calculation, not counts or inferred CAC multiplication in the consumer. Stable feed/channel identities survive renaming and reordering after authoring. Missing sources, duplicate selections, nonfinite/out-of-range shares, and a feed total combined with its own channels fail validation. The source catalog labels dollar flows explicitly.

Acquisition spend remains a non-posting calculation; selecting it here posts the allocated amount as this product’s Fee Product Costs. It does not transfer or remove any separately authored expense. Replace an existing manual cost in place and check any separate Marketing expense ownership. No saved engagements are automatically migrated. This release exposes acquisition spend flows, not arbitrary downstream statement totals or previously posted expense flows.

## Operating Account Digital CAC

Open the existing Operating Account Digital CAC Flat stream → Costs → Product cost — periodic amount → + Add linked source. Select the relevant Customer acquisition feed → Digital channel → Spend. Leave allocation at 100%. Recalculate and inspect Numbers: a $21,624 monthly source resolves to 21.624 $000s monthly. Changing the source spend updates this product cost. Add the link to the existing stream rather than creating another expense stream.

## Validation

Seven focused Python tests cover live spend changes, $21,624/month, cadence, additive allocations, all three product families, multiple acquisition methods, timing, identity, missing/invalid sources, feed-total overlap rejection, zero/scheduled spend posting once, and legacy entered amounts. Browser checks exercise catalog selection, replacing the entered amount, two linked sources, allocation editing, removal and entered fallback. Existing fee suite (62 checks), cost recovery (71 checks), product formula tests (4), component switches (14), source catalog and acquisition channel dependency suites pass. Existing r460 formula Numbers browser regression passes.
