# Foundry r372

Fix the completion gate for the live loan-production and separate repayment-rate method. This method no longer requires the hidden legacy runoff_per_period field. Legacy roll-forward loans still require that field; absent new payment/prepayment Series still reject calculation. No inputs are fabricated and no lending equations or UI layout changed.

Validation: 12 tests pass across the new absent-runoff regression, working-copy saves and loan-contract accounting. Public output is identical with or without the unused legacy field, and authored inputs remain unchanged. Packaged; not deployed.
