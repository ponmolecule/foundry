# r332 — externally determined tax rules

## Contract

An opt-in alternative to calculated tax in Configuration → Income taxes → Tax determination. Existing calculated policy/detail settings are preserved, inactive in external mode, and restored on switching back. No tax inputs are inferred from product or engagement names. No source-model values are embedded in this feature. Profile A only; Profile B rejects the mode explicitly.

External mode authors a current provision, settlement and recognized deferred balances. It does not certify a tax-sharing agreement, compute a consolidated return automatically, or allocate OCI/equity tax effects. The analyst supplies the applicable policy and upstream data. Existing DTA capital treatment applies; this release does not introduce a new regulatory DTA classification engine.

## Sources and rules

Named sources have stable identifiers, editable labels, money/scalar units, entered Flat/Growth/Explicit paths, or typed monetary fee-quantity links. A money input distinguishes period flow from ending stock. Money entry boxes are $000s; internal expressions use native dollars. Put monetary constants in named inputs. Scalar rates use decimals. Renaming a label preserves its identifier. Changing an identifier requires updating references; missing references fail closed.

The built-in `bank_pretax` is the live current-period bank pretax amount, before this provision; `periods_per_year` is the model cadence. No net-income or post-tax source is exposed. Rules can use +, -, *, /, min, max, abs, safe_div(numerator, denominator, zero_result), and prior(source_id, opening_input_or_literal). Rule units are explicitly money/scalar and checked. Derived rules resolve in dependency order, independent of authoring order. Current-period cycles, unknown/missing sources, invalid units, arbitrary code, nonfinite values and division by zero are rejected. A prior reference reads only committed periods; repeated funding-solver evaluations never advance a carryforward. `prior` opening inputs must be external inputs rather than another current rule.

A generic allocation composition can be authored from external entity income, adjustments, opening carryforwards, deduction limits, credits and tax rates. Derive group income, available losses via prior(), losses used via min/max, remaining loss balance, tax before/after credits, allocation base/share, and finally the bank provision. None of these formulas is prescribed by the engine. This keeps the feature reusable across tax-sharing arrangements instead of hardcoding this engagement's tax rules.

Money flows resolve monthly then SUM into quarterly periods. Entered stocks sample month-end/quarter-end. Scalar schedules follow the existing entered-series cadence contract. Rules themselves evaluate at the engine cadence, not at a hidden monthly cadence. Nonlinear monthly NOL/credit/threshold rules must use a monthly model; do not assume a quarterly rule is equivalent. This limit is visible in the UI.

## Posting and identities

Positive current provision is expense; negative is benefit. Positive payment is cash outflow; negative is refund. Select either same-period settlement or a separate payment rule/source. A signed opening settlement balance is positive payable, negative receivable.

- Ending net current tax payable = prior net payable + current provision − cash payment.
- Current tax payable = max(net payable, 0); receivable = max(−net payable, 0).
- Deferred expense = change in deferred tax liability − change in recognized deferred tax asset.
- Total tax expense = current provision + deferred expense.
- Net income = pretax − total tax expense.

No deferred asset is inferred from losses or a low tax provision. Deferred mode is either no recognized deferred tax, or explicitly authored recognized asset/liability levels and openings. Nonnegative asset/liability levels are required. Changes are treated as P&L-related; direct OCI/equity tax movements are outside scope. Inactive calculated-tax NOL, VA and annual-estimate settings do not contribute a second provision.

Tax payables and deferred tax liabilities are included in Other liabilities, with separate of-which lines. A current tax receivable is a separate asset; recognized DTA uses the existing dta series. The funding solver incorporates these balances together with NI. A scheduled but unpaid provision does not become a cash payment; recognizing deferred tax alone does not create a cash payment. Do not duplicate these balances in manually authored Other assets/liabilities.

## Audit and limitations

Income Taxes contains current/deferred/total provision, payments, signed settlement, recognized deferred balances, all source operands and named rule expressions. All Series includes the ledger and tax balance-sheet series; Config Snapshot retains the authored rules. Public monetary values are $000s; scalar operands remain unscaled. Calculated-mode complete results remain identical when external mode is absent or inactive.

No external entity framework, automatic group eliminations, tax-credit eligibility verification, legal return computation or tax agreement validation is implied. Links resolve only within the current engagement. The existing fixed-point solver rejects non-convergent tax/treasury feedback instead of publishing partial results.
