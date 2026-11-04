# r464 — Workforce-linked fixed-asset timing, grouping and depreciation

Formula / level components now have optional Driver timing and grouping controls: lag in months, the count preceding M1, driver units per group, and rounding (none/down/up/nearest half up). Resolution order is lag, divide, round, multiply. Defaults preserve existing components. Initial count is explicitly authored and is not inferred from current-period headcount.

Depreciation adds Rates by component: the base and each linked asset contribution have independent Flat/Growth/Schedule rate paths with Month/Quarter/Year rate periods. Existing aggregate-rate and entered-amount methods remain available, and switching does not discard inactive paths. Component rates require Gross PP&E. Depreciation retains the aggregate available-net-book-value cap and existing disposal accounting; this is level-based depreciation, not vintage retirement accounting.

For transformed inputs and component depreciation, the resolver uses monthly economic calculations, samples ending stocks and sums flows for quarterly/annual models. Native workforce hire/end windows, capacity-source cadence and model-period input paths are retained. Calculation audit exposes raw and transformed driver counts, level contributions and authored component depreciation before the aggregate cap. FIW exports timing/grouping/component rate inputs.

No engagement-specific formulas, values, source selections or stored assumptions are changed. This release does not implement multi-source summation within one grouped component; each component selects one published workforce series. It does not change the asset-schedule editor, pre-opening expenses or rent/utilities.

## Validation

Five new Python tests cover lag initialization, grouping thresholds, mixed rates, monthly/quarterly/annual stock-flow parity, native workforce hire windows, invalid inputs, and the net-book-value cap. All 48 existing fixed-asset checks and 11 UI authoring harness checks pass. Full console inline JavaScript compiles; git diff whitespace check passes. No rendered browser check was performed in this session.
