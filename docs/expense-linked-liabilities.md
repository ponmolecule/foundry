# Expense-linked liability stocks

Named Other Liabilities components retain Entered levels and existing headcount / fixed-asset links. A new `operating_expense_flow` link selects either one stable-ID operating-expense category or `operating_expense_categories`, the aggregate of all categories. Aggregate terms accept `exclude_category_ids`; several ordinary terms can also select an explicit set of categories.

The observed source is recognized expense: recurring expense after recognition timing plus category additive components. Payroll, product costs, depreciation and an overall gross-up are not silently included. This matches the category ownership boundary; labels state it explicitly. Missing categories and exclusions fail closed. Category cash settlement must be Recognition (or its equivalent Monthly mode); an independent deferred cash schedule or opening settlement balance is rejected to avoid posting another accrued/prepaid balance for the same selected source.

A term can use a plain multiplier or `days_spec` with an explicit positive `year_days`:

`liability = expense for native period × days payable / (days per year / periods per year) × authored multiplier`

The same day conversion helper serves asset receivables. This is an average daily flow convention: quarterly expense × DPO / 90 on a 360-day basis does not reconstruct monthly invoices or payments. Use an explicit ending-balance schedule when that convention is insufficient.

The link observes recognized expense without posting another expense. The resulting ending liability enters the existing cash/funding calculation. Sources are resolved before the funding solver; no new current-period net-income or cash dependencies are introduced. Signed terms remain supported; the final liability must remain nonnegative. Existing models are unchanged until the user explicitly selects expense links. In particular, pasted payable schedules are preserved and are never silently replaced with computed balances.

The public formula detail, calculation audit and editable assumptions workbook expose the source, effective multiplier, day assumptions, exclusions and contribution. Monetary source and result amounts follow the existing public $000s convention; day counts and coefficients remain natural numbers.
