# r316 validation

## Lineage and scope

Built directly on r315 `feb12c0`, which continues r314 `73b1170` and supplied r313 `900890f`. The final bundle includes both gross-up and repayment work; intermediate deployment is unnecessary.

## Full suite

Same discovery harness as r313/r314: every `foundry/**/tests*.py` and `web/tests*.cjs`, four workers, 150-second per-module timeout.

- r314: 100 modules, 84 pass, 16 fail.
- r316: 104 modules, 88 pass, 16 fail.
- All 100 r314 statuses match, and existing FAIL assertion counts match. Four new modules pass.
- Activity/account-cost tests: 33 checks (including the added percentage-cost diagnostic assertion).
- Gross-up tests: 13 checks.
- Repayment tests: 37 checks, covering explicit opening state, balances, repayments, annual/lifetime loss bases, quote locking, remaining allowance, provision, linked purchase sources, retained/distributed split, growing monthly flows, quarter aggregation, monthly fee/cost/interest sums, diagnostic units, public posting and both repayment audit sheets.
- Node tests execute actual authoring helpers for gross-up and repayment: source-object overrides, inheritance, stable fee identities, mode restoration, explicit curve Load/Clear/Close, valid generated actions and manual opening cohorts.

Known baseline failures (not resolved by this release):

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

## Identity and import

All five complete legacy fixture result objects compare equal to r314. No field is stripped. The delivery contains comparison JSON and the reproducible comparison script. All three `tests_result_identity` pins match: `3095860cd0b7`, `6d7e75a3ea0d`, `63efab196c93`.

A combined repayment-profile/gross-up-eligibility configuration was exported to FIW and imported with no edits. The complete configuration compares equal. Existing saved configurations and template fixture data are not rewritten; only new template creation defaults the gross-up rate to zero.

## Other checks and limitations

Full console inline JavaScript passes `node --check`; Python compilation and `git diff --check` pass. Browser rendering remains unverified because the browser binary installation was unavailable in this environment; Node checks are not a substitute for visual QA.

No actual charge-card engagement or contractual repayment/loss conventions were provided. The numerical tests are generic reproductions, not a reconciliation of that engagement. The new curve must be chosen from its actual specification. Unsupported combinations, including shared caps, exposure-term allowance and DFAST annual-balance overlays on lifetime-volume profiles, explicitly reject rather than converting basis or fabricating results. Guide Me remains unchanged for these controls.

See R315_VALIDATION.md for the documented build-stamp and intentionally added neutral-template default test maintenance. R316 also corrects optional monthly diagnostic aggregation to preserve balance-price annual units and percent-of-revenue cost percentage units; it does not alter the legacy result objects.
