# r474 — Formula factor schedule cadence

Based on r473 (460de3ce). Entered, non-periodized formula factors now expose Schedule cadence separately from Time basis. Year and Quarter schedules offer Hold (the default) or Interpolate between source points, using the existing Series engine. A yearly inflation multiplier remains dimensionless: it is not divided by 12. The same editor is used for Operating expenses and product expense formulas.

Existing authored inputs are not migrated. Merely rendering preserves them; existing monthly schedules and natural-period expense factors keep their prior behavior. Periodized factors still use their natural flow period and do not show the independent level-schedule controls. Explicitly changing cadence resizes the value list to the selected cadence using the existing schedule convention; values should then be pasted for that cadence.

Verification: three engine tests cover five yearly held factors versus all 60 monthly values, quarterly aggregation, quarterly schedules, interpolation and existing monthly schedules. Editor-handler tests cover cadence selection, Hold default, interpolation, inert rendering, natural-period separation and both renderer paths. All inline scripts parse. Existing Opex checks pass (121), as do 66 legacy formula equivalence cases. Reference coverage regenerated. Browser interaction test is included but could not launch Chromium in this environment because socket creation is restricted; browser visuals remain unverified.

After deployment, expand each Rent formula and add an entered Inflation multiplier with Display Number, Time basis No period, Path Schedule, Schedule cadence Year and Between source points Hold. Paste the five annual multiplier values. Existing Rent components do not require re-entry.
