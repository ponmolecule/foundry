# Foundry r357

Direct parent: r356 / f58640fbcc433a4a184140624f31115fedbaeb68.

Fixes two authoring/display issues without changing engine calculations or authored assumptions.

## Attrition precision

The attrition editor previously rendered Flat values, Growth bases/rates and Explicit previews to two decimal places in percentage units. Entering 0.83333% stored 0.0083333 correctly, but the field displayed 0.83%. Re-editing that rounded field could overwrite the precise input. Editable values now retain up to 15 significant digits, accept arbitrary decimal steps and have enough width to show the percentage. Growth fields and Explicit previews follow the same precision convention. The feed row wraps at narrow widths. Saving and loading continue to use the existing numeric JSON representation.

Existing values are not guessed or automatically repaired. If a rate was already overwritten with 0.83%, re-enter the intended rate. For a nominal 10% annual assumption applied as 10%/12 monthly, enter 0.833333333333333% Per month.

## Calculated customer-capacity staffing

Capacity roles now show calculated FTE in the workforce Count field and population table, labeled with the selected model period. The capacity editor adds a period selector and a horizontally scrollable schedule of the engine's active FTE path. It starts at the final model period and retains selection by stable role Series ID when navigating/reordering. Selecting a period changes UI state only, not model inputs or calculations.

All three output surfaces refresh through the existing engine-preview mechanism. Missing role results show a dash and a run instruction. Real zero FTE is shown as zero. Monthly counts are active monthly FTE; quarterly counts are labeled as average monthly active FTE. The calculation source is engine workforce.counts, not a second frontend staffing formula. Engine output and audit precision are unchanged; UI count rounding is presentation only.

## Verification

The Node regression executes actual attrition handlers and the Flat field template through edit, JSON save/load, render and re-edit; covers 0.83333%, longer fractions, small/zero rates, and checks all attrition paths are free of the two-decimal formatting. Staffing checks cover stable IDs, missing results, fractional/zero FTE, period selection without input mutation, quarterly labels and preview hooks. Full inline-script syntax parses.

The Python integration test feeds the resulting authored rate to the acquisition engine and checks monthly losses and the 12-month customer book against the unrounded recurrence. Existing workforce capacity tests (7), capacity controls, CAC UI (37) and r355 linked sources (26) pass. No browser pixel/layout verification was available.

Packaged for user deployment; not deployed. The CAC summary's visibility behavior is outside this release, per the user's instruction.
