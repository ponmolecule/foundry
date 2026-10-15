# r331 validation

Verified recovered delivery release metadata, BUILD_STAMP and bundle HEAD: r330, 2121f728908845b6ed2e37b67d1fbc4cb06327b0.

Full suite on this environment: r330 116 modules, 98 pass / 18 fail; r331 117 modules, 99 pass / the same 18 fail. No new failures. These counts reflect a fresh baseline run here, not copied r330 delivery counts. Harness runs foundry/**/tests*.py and web/tests*.cjs with four workers and 150-second per-module timeout.

All five complete serialized public results are byte-identical, with nothing removed or normalized. All three pinned fingerprints pass: 3095860cd0b7, 6d7e75a3ea0d, 63efab196c93.

New regression verifies entered stocks, quarter-end sampling, audit operands, workbook labeling, input-workbook schedule exposure, validation, funding direction, and negative aggregate rejection. Existing 24 liability checks pass. UI harness verifies new default, source switching, existing links and mode preservation (10 checks). Inline JavaScript compiles; git diff --check passes. No rendered browser QA is claimed: Chromium executable is unavailable.

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
