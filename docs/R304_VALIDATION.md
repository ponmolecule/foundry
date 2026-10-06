# r304 validation

Baseline: r303 / 98242c5527d6404d048cd630c2fc2c3bd42faeaa.

- Full Python and web/tests*.cjs suite, each discovered module executed separately with a 150-second timeout and four workers: r303 89 modules, 73 pass, 16 fail; r304 90 modules, 74 pass, the same 16 fail. No new failures. Full logs and both summaries are included in the delivery.
- New tests_other_assets: 7 tests pass. Checks monthly/quarterly days conversion, entering balances, signed terms, declining stocks, opening stock, cash offset and unchanged income at zero residual yields, rejecting invalid/circular sources and days, duplicate IDs, inactive setup, public units, exact audit save/reload, monthly engine use, Profile B integration, editable workbook round trip and capital inclusion.
- Whole serialized outputs, without removing fields: identical for 3 run_v2 fixtures and all 9 parity engine fixtures. 12/12. SHA-256 equality evidence included.
- Fingerprint pins: 3095860cd0b7, 6d7e75a3ea0d, 63efab196c93. 3/3 pass; pins were not changed.
- Configuration layout: 107 pass, 0 fail. r303 tiered browse tests: 4 pass, 0 fail.
- Actual HTML in Chromium, 1920, 1366 and 1024 pixels: editor rendered and opened, source/day authoring, adding/removing components and terms, mode preservation, correctly labeling asset opening observations, no page JavaScript errors, no controls overflowing their section. Existing browser request/auth/autosave calls were stubbed; this is not a live deployment/session test. Actual-code screenshots included.
- git diff --check passes.

## Existing failing modules

foundry/tests_parity.py; foundry/tests_protocol.py;
foundry/v2/tests_audit_reconcile.py; tests_change_history.py; tests_cost_recovery.py;
tests_deposit_fix1.py; tests_fee_guide.py; tests_fee_streams.py; tests_growth_ui.py;
tests_interest_balances.py; tests_managed_securities.py; tests_opex_ui.py;
tests_pastebox_hardening.py; tests_peer_r240.py; tests_universal_template.py;
web/tests_authoring_stability.cjs.

The suite is not clean; the same baseline failures remain. This release does not resolve those unrelated historical test failures.
