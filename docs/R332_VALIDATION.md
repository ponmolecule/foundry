# r332 validation

Baseline: r331 278e9d724483e09b7ce04305ec6c740d00d381e8.

Full suite: baseline 117 modules (99 pass, 18 fail); candidate 119 modules (101 pass, same 18 failures). No new failing modules. Both are measured in this environment using all foundry/**/tests*.py and web/tests*.cjs, four workers and 150-second module timeout. Baseline failures are listed below.

All five complete serialized public results match r331 byte-for-byte, with no fields stripped. Pinned fingerprints remain 3095860cd0b7, 6d7e75a3ea0d, 63efab196c93. All 18 interim-tax and 10 tax-integration tests pass.

New tests verify live allocation, committed prior-loss recurrence, safe zero denominator, arithmetic/unit/source rejection, current-period cycles and unsafe-code rejection, repeated-evaluation purity, duplicate-commit rejection, monthly flow sum vs ending-stock sampling, separate payments/refunds and opening settlement, deferred provision identities, noncash deferred recognition, engine balance-sheet identities, runtime monetary-quantity links, exact/public/audit units, backward-compatible calculated mode, distinct UI IDs, immutable rendering, source/rule controls and mode roundtrip. Current bank-pretax dependency is checked through the funding solver. Inline JavaScript compiles and git diff --check passes.

No rendered browser QA is claimed; Chromium is unavailable. No real engagement's external tax configuration has yet been authored or reconciled; configuration will follow deployment.

Baseline failing modules:
- foundry/tests_parity.py
- foundry/tests_protocol.py
- foundry/v2/tests_audit_reconcile.py
- foundry/v2/tests_change_history.py
- foundry/v2/tests_cost_recovery.py
- foundry/v2/tests_deposit_fix1.py
- foundry/v2/tests_fee_guide.py
- foundry/v2/tests_fee_streams.py
- foundry/v2/tests_growth_ui.py
- foundry/v2/tests_interest_balances.py
- foundry/v2/tests_managed_securities.py
- foundry/v2/tests_opex_ui.py
- foundry/v2/tests_pastebox_hardening.py
- foundry/v2/tests_peer_r240.py
- foundry/v2/tests_r288_securities_bands.py
- foundry/v2/tests_settlement_http.py
- foundry/v2/tests_universal_template.py
- web/tests_authoring_stability.cjs
