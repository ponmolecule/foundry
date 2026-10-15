# r333 — reuse the configured tax rate

Built directly on r332 b1753b04575339e4221aae4f46bb22270df8be92.

External tax expressions can reference `configured_tax_rate`, the existing `assumptions.tax_rate` decimal rate. The compact rate control in external mode edits that same assumption; no duplicate rate input or migration is required. Existing entered sources and rules are preserved. The rate is an annual percentage applied to the period taxable amount, not divided by model cadence. It is validated as finite and between 0 and 1 when referenced.

The distinct name avoids conflicting with previously authored inputs named `tax_rate`. The operand and scalar audit unit appear only in external runs whose expressions reference it; existing external rules and calculated-mode results remain unchanged. No automatic tax formula or rate is added.

Deploy with the usual delivery script. Return to the intended monthly engagement, confirm the configured rate is 27%, retain the five entered sources through Temporary tax adjustment, and continue authoring. The unfinished rule set is not a reconciled tax result.
