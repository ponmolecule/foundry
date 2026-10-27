# r405 — Product balance-linked operating costs

Balance streams on deposits and loans can select their own period-end balance instead of the legacy average and apply a direct annual operating cost rate to that balance. For a monthly model this is ending balance × annual rate ÷ 12. Native quarterly models use quarter-end × annual rate ÷ 4; loan repayment profiles with canonical monthly replay accrue the monthly observations. Existing streams without a measure retain the average balance.

The stream's cost posts to bank-wide noninterest expense and product contribution now includes direct stream costs. This corrects product attribution for existing direct stream costs as well: product contribution and the treasury residual can change, but the bank-wide income statement is not reposted. Existing Opex formulas are not moved or removed. If an existing formula is replaced by a stream, the user must remove the old formula after reconciling to avoid duplicate expense. Gross-up eligibility follows the existing stream-cost policy.

Validation: dedicated monthly and quarterly calculation, saved UI authoring, product contribution and single-posting tests; existing deposit, loan-stream, audit, and repayment-profile checks.
