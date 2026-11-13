# r506: Stress Testing title band, Capital sections sized to their content

Built on Claude r505 (85643fe). UI only.

## Engine and calculations

Unchanged.

## Stress Testing gets the graphite title band

Stress Testing now opens like every other tab: breadcrumb, then the graphite "Stress Testing" title band, then the side menu and the content. The menu card's own heading is removed so the name is not repeated.

## Capital & pre-opening sections no longer stretch across the page

Each section is now sized to what it holds:

| Section | Width |
|---|---|
| Staged raises | up to 420 px |
| Scheduled borrowings | up to 680 px |
| Pre-opening expenses | up to 680 px |
| Fixed assets / CAPEX | full width (its table needs it) |

- **Scheduled borrowings:**
  - The row no longer scrolls sideways or squeezes its inputs.
  - Name, month, amount, rate and term each have a fixed column under their header, and rate and term no longer overlap.
- **Pre-opening expenses:** the amount column now sits next to the expense names instead of across the page.

## Build stamp

`BUILD_STAMP` is `foundry-r506-stress-band-capital-widths`. `tools/release_check.py r506` passes.

## Validation

`web/tests_r505_config_pattern_ui.cjs` now also checks:

- the capital section widths;
- that the borrowing row fits its card, with each input apart from the next and under its header;
- the Stress Testing title band.

The stress UI tests and the earlier Configuration tests pass.
