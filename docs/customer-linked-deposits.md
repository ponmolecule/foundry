# Customer-linked deposit balances

Available in r380, under Deposits → Balance → Balance method → Customer count × balance per customer.

This opt-in Profile A method links the deposit liability to a Customer Acquisition feed by stable customer-count Series ID. Feed names may change without breaking the link. The feed owns acquisition and attrition; the deposit does not independently repeat either calculation.

Inputs are the customer-count source, period-end or period-average count measure, an entered dollars-per-customer Series, and the existing opening deposit balance. Dollars per customer supports Flat, Growth and Explicit schedules through the existing series editor. Enter 950 for $950/customer, not 0.950. Opening deposit balance remains in $000s in the UI. The opening balance is independently authored and supplies the initial interest exposure; it is not silently inferred from opening customers.

Ending deposit balance = selected customer count × dollars per customer.

Monthly observations are resolved before aggregation. In a quarterly model, period-end selects the last month's ending count × that month's amount. Period-average averages the three monthly products, each using its monthly beginning/end average count. This avoids multiplying two quarterly averages when both operands change. No APR division is applied to this stock calculation. Interest still uses the product's existing, separately selected deposit interest balance measure and pricing policy.

The method replaces growth, inflows, runoff and maturity balance mechanics while active. The editor retains their saved draft for switching back; inactive customer inputs likewise survive mode switching. Existing products retain their methods and outputs. Missing sources, unsupported measures, incomplete schedules, negative/nonfinite amounts, and conflicting balance mechanics fail validation rather than returning invented values. Profile B retains the existing rejection of deposit level policies.

The engine reports the resolved calculation under `depositCustomerCalculation`: stable source ID, selected measure, monthly counts, monthly dollar amounts and native ending balances. The public diagnostic preserves the explicit raw-dollar field names. Calculation Audit Product Details exports counts in count units, per-customer amounts in dollars/customer, and calculated balances in $000s. Compact editor readouts continue to show the deposit's resolved monetary balance; no duplicate source-number preview is added.

For Engagement 5 HSA, select HSA Accounts, Period end, Flat $950/customer, opening balance 0. The $950 is source annual purchase volume $1,900 × source balance factor 50% × enabled toggle 1. This release adds the reusable balance method only; it does not create or modify engagement data, HSA fees, or sponsorship pricing.
