# r496 — Tax sources as aligned rows

Console only. No engine change. Built on r495 (a38ac05).

## The problem

Each tax source opened into a full form: Name and Units on one row, Source and Measure on the next, the value editor in its own box, then a nested "Source identifier" disclosure with an Identifier field. Five sources meant five stacked copies of the same labels; a three-source panel ran well past a screen.

## What r496 does

- **Closed source = one row** with four aligned columns: name, kind (Period amount, Balance, Rate / factor, Linked), current value ("1,737.126162 $000s", "0.065", "Schedule · 60 month values", "Other income × 1") and the identifier as a code chip.
- **Open source = one settings line** (Name, Units, Source, Measure, Identifier) with the value editor under it. Measure drops out for rates and linked sources; the identifier stays in the same line. The nested "Source identifier" disclosure is gone.
- A footer names how rules and blocks refer to the source ("Rules and blocks refer to this source as source_1.") beside a labelled "Remove source" button (was a bare ×).
- Derived rules use the same row treatment.
- Rows are separated by rules; the open row header is shaded.

## Verification

- New: web/tests_r496_tax_sources.cjs (row columns align, kind and value text for flow, balance, rate and schedule sources, one-line settings, no nested identifier disclosure, scalar row drops Measure, edits write through).
- tests_tax_blocks.cjs, tests_external_tax.cjs and r495's disclosure test pass.
- Reference coverage regenerated.
