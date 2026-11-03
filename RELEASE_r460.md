# r460 — Numbers for product formula costs

Product formula costs now expose a Numbers control immediately below the Cost formula heading. This enables monthly or quarterly inspection and Excel copying for expenses such as Operating Account Fraud and Partner Revenue Share.

The values come directly from each stream's captured engine `fee_product_cost`, converted from dollars to $000s without display rounding. They represent the product expense before any bank-level gross-up. No engine calculation, fee/cost posting, defaults or saved model inputs change. A successful recalculation refreshes the Numbers payload. Existing stale-result protection disables copying after inputs change, until results are current again. A formula without captured results prompts the user to run the model; zero-valued results remain inspectable.

Validation: Chromium checks actual formula editor rendering for fee products, lending and deposits under monthly and quarterly models; exact captured expense, unit/cadence labels, Excel copying, stale protection, refresh, zero results and unchanged configuration. Existing r458 activity-chart browser regression passes. Six product-formula transfer/workflow Python tests pass.

Reconciliation workflow: Operating Accounts — Fees & Costs → select Fraud or Partner Revenue Share → Numbers below Cost formula. Use the $000s output against source dollars after conversion.
