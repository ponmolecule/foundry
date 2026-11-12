# r493 — Previous-quarter cash interest basis

Adds an explicit previous-quarter average (beginning and ending) pricing basis for remaining bank cash and allocated cash components. Monthly runs hold that basis for the current quarter; quarterly runs use the same rule. The first quarter requires one historical beginning balance. Subsequent quarters use modeled cash history, with no current-period lookahead.

The historical pricing input does not add assets, cash, equity or borrowing. Negative cash boundaries earn no interest. Existing pricing measures remain unchanged. Audit rows expose both historical boundaries and the pricing balance; API values retain the existing $000s contract.

Preserves r492 funding regression fixes and Claude r490/r491 securities editor improvements.

Validation: 67 focused Python tests, 9 parity fixtures, 344 protocol checks, and three Node suites pass (new pricing control, schedule status, shared assumption panel). Browser integration and the complete 329-file suite were not rerun.
