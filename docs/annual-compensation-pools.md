# Annual compensation pools

The existing `piecewise_linked` Workforce compensation component keeps its weighted Income Statement sources and literal marginal bands. No new revenue-threshold dialect is introduced.

## Optional contract

- `allocation`: omitted / `event` preserves the existing event cadence and model-year-to-date observation; `model_year_equal` evaluates complete model-year Income Statement flows and recognizes the award equally over that year's native periods (12 monthly, 4 quarterly, 1 annual in Profile A; quarterly in Profile B).
- `salary_floor`: optional `{role_series_ids: [...], rate: fraction}`. For equal full-year allocation, the minimum is the selected roles' actual base compensation for that model year times the rate. Actual counts, amount basis, schedules, start/end dates and resolved hiring are inherited from the Workforce runtime. Role payroll load and additive pools are excluded. Stable role IDs are required; missing, duplicate or ambiguous references fail validation/calculation.
- Award = maximum of the existing band's result and the selected-pay minimum. Without a minimum, the band result is used directly.
- `payroll_load_rate`: optional nonnegative fraction, default zero, applied once to the award. It is separate from selected roles' payroll loads and posts with the component to Workforce compensation. Also available for existing event recognition.

No engagement names, role names, thresholds, participation percentages or payroll-load percentages have computational significance or built-in defaults. UI additions are opt-in controls on the existing compensation pool. The role picker appears only when the selected-pay minimum is enabled. Existing components are not migrated. Turning off a selected-pay minimum is an explicit user action before returning to event recognition.

## Full-year dependencies

An initial projection observes the complete income paths and actual selected-role base pay with full-year pools suppressed. A posting projection allocates each award evenly. The same inputs are re-observed after posting and must match; if compensation changes its own input revenue/payroll, the run rejects the feedback dependency. It does not silently accept a forecast from before the pool was posted or guess a circular solution. Existing event-based pools continue to operate in both passes.

All existing Income Statement flow metrics can be selected. Stock / balance terms require event recognition. Net interest and total operating revenue commonly depend on funding costs or cash income affected by compensation and may therefore fail the feedback check; an independent fee-income source may be appropriate when that is the actual contract. This is an economic source choice, not an automatic substitution.

Equal annual allocation currently requires complete model years and zero observation lag. Saved event cadence/first-event settings are retained but do not govern annual allocation. Model years are consecutive projection-year blocks; a calendar/fiscal-year reallocation or a partial-year estimate is not inferred.

## Evidence and presentation

The raw engine and public result include `workforce.annual_pool_calculations`, explicitly labeled in dollars, with component IDs, selected role IDs/rate, annual source values and weighted contributions, role base pay, minimum, band result, award, payroll load, and period allocation. This block stays in dollars even where public compensation paths are presented in $000s.

A collapsed **Annual award calculation · latest run** table presents the key amounts in $000s. The existing **Workforce Component Detail** calculation-audit sheet carries full-year observations and the minimum/award/load reconciliation in raw dollars. Existing event diagnostics retain their previous behavior.
