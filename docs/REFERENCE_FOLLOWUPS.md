# Reference follow-ups (r394)

Statements the Reference authors could not fully confirm from the code, kept out of the entries until checked. Each line names the entry.

- **loan-structure**: For CRE lines the read-only Term is a display default (p.structure || 'term'); if structure is not stored, the engine condition structure == 'term' would not run level-payment amortization. Confirm presets store structure.
- **loan-structure**: A code comment in prodCardHtml says the engine does not read structure or term_q; engine_q_a.py does read both. The comment appears stale.
- **loan-repayment-model**: Monthly repayment curve illustration assumes age-0 repayment applies in the funding month as stated in the UI hint; the exact cohort arithmetic in repayment_profiles.py was not traced line by line.
- **loan-measurement**: How fair value changes post to earnings was not traced in this pass.
- **deposit-pool-capacity-limit**: The beginning credit term in the committed amount is passed in by the engine; its exact composition (for example, beginning net loans) was not traced.
- **fee-auc-trajectory**: The Growth illustration uses the simple per-period growth path; a growth_spec path resolves through resolve_growth_series and may step annually.
- **fee-rate-behavior**: Tiered rates on transaction basis are applied to the quantity without period division; units of tier breakpoints for transaction counts were not confirmed.
- **growth-rate-period**: Whether a Step method with a Month rate is accepted for level fields in a quarterly model: growth.py raises 'cannot represent stepped month growth inside 4-period/year cadence' for level series, while natural-period flows resolve on a monthly grid.
- **growth-step-anchor**: Exact boundary arithmetic for Calendar year and Fiscal year anchors (growth.py beyond _step_count lines read).
- **operand-source-enter-link-derived**: Whether other product families reuse depositOperandHtml beyond deposit balances and retention pools (only deposit call sites were found).
- **cac-driver-trajectory**: After switching the growth period from /quarter or /month back to /year, the method stays smooth (cacDriverGrowth sets the anchor to model_year but does not restore step).
- **cac-attrition-timing**: Defect: cacFeedWithinSet stores 'monthly_bucket' for 'At the start of each attrition period', but cac_feeder.py accepts only period_end, spread or period_start and raises an error, and the select reads back 'monthly_bucket' as 'end'. The start option does not work as coded.
- **opex-recognition**: Monthly recognition in a quarterly model: the UI offers it, but _timing_interval raises 'monthly timing is finer than model cadence'.
- **formula-linked-series**: The full catalog label list varies with the configuration; labels above are from source_catalog.py and _legacyOpexLinkedDriverOptions.
- **formula-base-balance-measure**: The select always lists all three measures; whether the engine rejects Beginning or Average for a source that publishes only period end (deposit pool available balance) was not traced end to end.
