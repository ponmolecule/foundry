# r420 — Transparent weighted count authoring

Built on r419. Account streams linked to Another stream or Linked stream quantity, with Derived trajectory, now offer “Use a weighted count breakdown”. Each named band contains a Share (%) and Count per source unit, using the existing Flat / Growth / Explicit Series controls. The editor uses the existing weighted-component styling and adds no engagement-specific assumptions.

The equation is source count × sum(share × count per source unit). The existing SharedAssumptions resolver owns weighted math, monthly share validation (100%), units and finite/nonnegative validation. Ratios are dimensionless: no monetary scaling, time division or rounding. Quarterly ratios sample period end; this is not monthly paired-product averaging. Use monthly cadence when within-quarter variation matters.

Existing streams remain unchanged until explicitly opted in. Switching back to a single multiplier preserves the prior multiplier; switching again restores authored bands. An active weighted breakdown cannot coexist with another multiplier. An Index entry explains the feature. No save endpoints, product-specific logic or automatic data migration change.

Validation: four new engine tests cover monthly/quarterly paths over five years, changing assumptions, invalid inputs and legacy equivalence. Editor harness checks names, units, add/remove, read-only rendering and reversible switching. Full engine cross-product quantity checks pass monthly/quarterly. Existing fee-measure tests and JavaScript syntax checks pass. The full universal reference result is exactly equal to r419 before the build stamp changes. The broader fee suite has 57 passes and two pre-existing pinned fingerprint failures; its output is identical on r419. Real-browser visual verification was unavailable; UI verification used the DOM/editor harness and existing styles.

## Entry for an existing derived Account stream
Open Activity and click “Use a weighted count breakdown”. Rename Band 1 and add bands as needed. Enter shares as percentages and sizes as raw counts, not $000s. No need to enter the combined multiplier. Keep pricing/costs at zero for an unpriced population source.
