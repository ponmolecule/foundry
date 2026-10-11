# r314 validation

## Baseline and lineage

Built from the attached r313 full-history bundle, commit `900890f1fd9069d541eefeb5c89bd4dfb7cdeac1`, with no intermediate failed-build files. Release 1 only.

## Full suite

The same discovery harness ran every `foundry/**/tests*.py` and `web/tests*.cjs`, with four workers and a 150-second per-module timeout.

- r313: 98 modules, 82 passed, 16 failed.
- r314: 100 modules, 84 passed, 16 failed.
- All 98 baseline module statuses are unchanged; two new modules pass. Existing failures remain; this is not an all-green suite.
- The account-activity module passes **32 checks**: population identities, live links, closures/exits order, no reopening, annual probability compounding, explicit periods, account cost cadence, varying monthly prices, cross-product owner resolution, source catalog, direct/indirect expense cycles, public validation/output and workbook audit.
- The Node authoring test executes actual console helpers: opt-in stable publishers, source choices, exclusive adoption modes, opening state, cost-period defaults and bounded control widths.

Baseline failures:

- `foundry/tests_parity.py`
- `foundry/tests_protocol.py`
- `foundry/v2/tests_audit_reconcile.py`
- `foundry/v2/tests_change_history.py`
- `foundry/v2/tests_cost_recovery.py`
- `foundry/v2/tests_deposit_fix1.py`
- `foundry/v2/tests_fee_guide.py`
- `foundry/v2/tests_fee_streams.py`
- `foundry/v2/tests_growth_ui.py`
- `foundry/v2/tests_interest_balances.py`
- `foundry/v2/tests_managed_securities.py`
- `foundry/v2/tests_opex_ui.py`
- `foundry/v2/tests_pastebox_hardening.py`
- `foundry/v2/tests_peer_r240.py`
- `foundry/v2/tests_universal_template.py`
- `web/tests_authoring_stability.cjs`

## Legacy result identity

All five runnable configurations were executed on the clean r313 tree and r314. Their **complete result objects compare equal**, without stripping any fields. The delivery includes the comparison script and JSON containing full-output SHA-256 hashes and run hashes. `python3 -m foundry.v2.tests_result_identity` passes all three current fingerprint pins:

- core_bank_test_base: `3095860cd0b7`
- patrick_default_v31: `6d7e75a3ea0d`
- universal_template_bank: `63efab196c93`

## Hand checks

- 1,000 opening customers, 600 opening subscribers, 10 new customers and 60% target share: ending subscribers 606; inferred additions 6. Servicing at $10/account/month costs $6,060; onboarding at $175/addition costs $1,050. Both post once.
- A flat 600 subscribers cost $72,000 annually at $10/account/month in monthly and quarterly models.
- Flat beginning subscribers with a 12% annual closure probability retain 88% after twelve monthly applications, without attrition or adoption.
- Active subscribers → $23,000/account/month purchase volume → 2.2% interchange produces $306,636 in month 1 for 606 subscribers. Quarterly economics sum monthly products.

## Test maintenance and boundaries

The r313 deposit-beta coverage test previously asserted the exact r313 build stamp. Its stamp assertion now accepts r313 or a successor; all 17 substantive coverage assertions are unchanged. The new authoring test separately asserts the exact r314 stamp.

Full inline-console JavaScript passes `node --check`; Python compilation and `git diff --check` pass. Browser-rendered screenshots were **not verified**: the available Playwright browser installation failed, so no pixel-level or laptop/1920px visual verification is claimed. The authoring behavior and bounded CSS are tested with Node.

Guide Me's existing schema remains unchanged; the new shared adoption/account-cost controls are authored manually. Repayment profiles, new loss/allowance policies, commitments and gross-up eligibility are deferred. Existing gross-up treatment is preserved.
