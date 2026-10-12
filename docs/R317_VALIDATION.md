# r317 validation

Baseline: r316 (39829f9). Full-suite harness discovers every foundry/**/tests*.py and web/tests*.cjs; four workers, 150-second module limit. The release tree discovers 105 modules: 89 pass and the same 16 baseline modules fail. All 104 baseline module exit statuses match. Printed failure counts in failing modules that report counts also match. There is no claim that the entire suite is green.

## New and related checks

- tests_profile_completion: 40 checks. Covers closing-cap transfer accounting, retained and distributed principal identities, no buyback, member order independence, mixed legacy/profile competition, monthly and native-period capacity schedules, deposit cap convention, curve-duration allowance, partial paydowns, lifetime-loss ownership after transfers, opening transfer history, par transfer funding effects, absolute stress replacement and post-window resumption, zero/nonbinding/invalid capacities, public monetary scaling, audit sheets, and exact input-workbook round trip with gross-up eligibility.
- tests_repayment_profiles: 37 checks; the former unsupported term-allowance rejection is replaced by its concrete curve-exposure result. The standalone single-product resolver still rejects a shared group because it must be resolved simultaneously by the group engine; the public engine's group path is tested separately.
- web/tests_repayment_profiles.cjs: passes actual console helper tests for opt-in/removal, preserved legacy settings, curve Load/Clear/Close, opening controls, valid generated actions and new allowance/transfer labels.
- Pinned current fingerprints: core_bank_test_base 3095860cd0b7; patrick_default_v31 6d7e75a3ea0d; universal_template_bank 63efab196c93.
- Complete output equality against r316: all five runnable configurations, including pf_a_base (9ea47ad8c3b8) and pf_b_base (e4ff2d4a236d). No stripping, rounding or field exclusions. JSON evidence includes full-output SHA-256 hashes.
- Python compilation, complete inline JavaScript syntax, git diff whitespace check, and fresh-clone bundle verification pass.

Existing failing modules: foundry/tests_parity.py, foundry/tests_protocol.py; foundry/v2/tests_audit_reconcile.py, tests_change_history.py, tests_cost_recovery.py, tests_deposit_fix1.py, tests_fee_guide.py, tests_fee_streams.py, tests_growth_ui.py, tests_interest_balances.py, tests_managed_securities.py, tests_opex_ui.py, tests_pastebox_hardening.py, tests_peer_r240.py, tests_universal_template.py; web/tests_authoring_stability.cjs. Their logs and baseline logs are included in the package.

No browser executable is installed in this environment, so rendered visual testing is not claimed. The actual engagement is unavailable, so its reconciliation is not claimed. Generic hand checks and accounting/cadence/audit tests supply the evidence above.

Reproduce: python3 -m foundry.v2.tests_profile_completion; python3 -m foundry.v2.tests_repayment_profiles; python3 -m foundry.v2.tests_result_identity; node web/tests_repayment_profiles.cjs. The delivery includes the full suite harness, logs, complete-result comparison helper/report, and bundle ancestry verification.
