# r334 validation

Baseline: r333 13dca3070fcd15f8247acda1fd91aa5403bb5fa3.

Full suite: 119 modules, 101 passing, the same 18 baseline failures, no new failing modules. Full baseline list is in R332_VALIDATION.md. Five complete public fixture results are byte-identical with no fields removed. All three pinned result fingerprints pass. An existing external-tax engagement using configured_tax_rate also produces byte-identical public results.

Tests execute the actual browser selector handlers in Node, pass the resulting expressions into the Python tax ledger, and independently reconcile two periods of NOL usage, remaining losses, provision and allocated tax. Coverage includes selector-generated unit inference, draft Apply/Cancel, incomplete/mixed-unit selection rejection, direct/indirect current-cycle rejection, valid lag recurrence, ratio zero policy, NOL setting policy/detail/regulatory precedence, configured opening stock used as prior opening, invalid assumptions, immutable source rendering, preserved mode state, visible source-field labels, and all inline JavaScript syntax. Targeted tests were rerun after the compact collapsed-rule presentation change. git diff --check passes.

No rendered browser QA is claimed; Chromium is unavailable in this environment. This release adds no engagement-specific constants or allocation formula. The actual engagement's partially authored tax remains unreconciled pending completion of its rules and settlement assumptions.
