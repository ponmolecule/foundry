# Minimum deposit interest expense

r381 adds an optional monetary minimum under Deposits → Pricing → + Minimum interest expense. The amount is entered in $000s; Amount is per selects Month, Quarter or Year. Flat, Growth and Explicit amount schedules reuse the existing series editor. This is a generic deposit-pricing policy, independent of a product's name, balance method or acquisition source. Both projection profiles support it within their existing balance-method boundaries.

For each engine period:

1. Calculate deposit interest using the existing selected balance basis and annual rate, including any index beta, spread, rate floor/cap and product overrides.
2. Convert the authored monetary minimum to a model-period equivalent: amount × natural periods per year ÷ engine periods per year.
3. Post `max(calculated interest, model-period monetary minimum)` once as deposit interest expense. Do not add a second operating expense or fee stream.

A $30,000/month minimum is entered as 30 and Month. Its equivalent minimum in a quarterly engine is $90,000 per quarter. The comparison is once per **model period**. A quarterly run does not claim to sum three separately floored monthly interest amounts; those can differ when a floor binds in only some months. Use monthly model cadence for monthly payment-floor fidelity. Schedule cadence controls when the amount assumption changes; Amount is per controls its flow conversion. The monetary minimum applies even at zero balance when explicitly enabled. A percentage rate floor does not substitute for this monetary rule.

Optional authored contract: `minimum_interest_expense = {period, amount_spec}`. Amount specs must be entered, finite, nonnegative and complete for the required horizon. There is no default policy or inferred engagement value. An omitted/null policy preserves legacy behavior, including negative interest where otherwise allowed; explicit zero is an active zero floor. Removal deletes the policy. Saved amount and pricing schedules remain live and do not depend on pasted calculated expense results.

Diagnostics, unrounded Product Details data and Calculation Audit provide `interestBeforeMinimum`, `minimumInterestExpense` and `minimumInterestTopUp` in the existing monetary unit conventions. Posted interest expense, net interest income, profit, funding and capital consume the floored expense. Rate disclosures continue to report the contractual annual rate; the monetary top-up is separately auditable.

For Engagement 5, HSA Deposits uses EFFR with 50% beta, zero spread, average beginning/end balances and a 30 ($000s) monthly minimum. Other and Strategic Deposits have no monetary minimum. With the supplied account assumptions, first-month HSA interest is $54,031.25 and the $30,000 minimum is nonbinding; the policy must still remain represented for changes to balances or rates.
