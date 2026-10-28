# r408 — Product-owned formula cost streams

A product can now own a Formula cost stream that observes modeled balances, rates, gross acquisition shares and eligible quantities. The implementation reuses the existing typed Formula evaluator and editor, including add/subtract bases, balance measures, annual rate periodization, monthly balance accrual, guards and factor paths. Formula sources are observations, not duplicate postings. Direct costs appear under their owning product and in bank-wide noninterest expense once.

## Existing expense transfer

Under the product's Fee streams, open Formula costs → Move an existing Operating Expense formula. Select the component and choose Move to this product. The server creates an unsaved candidate: it transfers the formula, retains its source bindings and effective gross-up eligibility, and removes only that component from its old category. Other category amounts remain unchanged. It runs the before/after models and verifies balance-sheet values, profit, and total expenses, allowing only the intended corporate-versus-product expense reclassification. If the category is referenced elsewhere, the component is missing, the source is unavailable, or financial totals change, the move is refused. The browser discards a response if the engagement changed during the check. No engagement save is performed by this endpoint.

This supports moving Operating Account Fraud (combined ending operating deposits × annual rate) and Partner Revenue Share (eligible margin × cumulative gross EMR share × participation rate) into separate cost streams under the Operating Account fee product. No product names or engagement assumptions are hard-coded. Existing engagements are not automatically migrated.

## Scope

Formula cost streams have a cost editor and result preview, without irrelevant revenue or activity dials. Existing stream behavior and the Opex editor remain available. Supported sources include product catalog balances, reference rates, deposit interest, gross acquisition shares, acquisition/account flows, AUC and eligible stream quantities, and gross income observations. Workforce-dependent and net-fee-income-dependent product cost formulas are rejected at this stage; current net fee income includes product costs and would require a separate dependency contract. Formula-cost outputs are not exposed as settlement-liability inputs because settlement currently resolves earlier. Existing source formulas keep their original cadence semantics; moving does not invent finer-cadence observations.

## Validation

Tests cover monthly/quarterly formula transfers, live source changes, gross-up at 0% and 8%, unique ownership, duplicate-transfer rejection, missing sources, expense-category references, unchanged input objects, direct-cost attribution, actual HTTP success/rejection, editing the moved formula's product target, reload, and responsive controls at 1440/1024/768 pixels. Existing formula, gross-up, deposit/loan stream and beginning-balance regressions pass. Audit workbook generation includes the moved product costs.

Known baseline issue: the broader settlement test `test_live_engine_posting_once_and_stock_reconciliation` fails its input-mutation assertion because derived customer-flow identifiers are added. The same failure was reproduced on untouched r407; it is not caused by this change. The remaining settlement/HTTP checks in that run passed. This build does not modify the save mechanism.
