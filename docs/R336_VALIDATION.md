# r336 validation

Baseline: r335 88de79d08761e7331f2f633b00735cd4de0fd1b9.

Baseline suite: 121 modules; 103 pass, 18 fail. Final suite: 123 modules; 105 pass, the same 18 fail. No new failing module. Both new modules pass:

- python3 -m foundry.v2.tests_rates_workspace
- node web/tests_rates_workspace.cjs

Pinned full-result identities remain 3095860cd0b7, 6d7e75a3ea0d and 63efab196c93. All five complete public fixture outputs are byte-identical: core_bank_test_base, patrick_default_v31, universal_template_bank, parity/pf_a_base, parity/pf_b_base. No field removal or normalization.

New engine coverage: legacy raw economics under an inert workspace; pure previews; annual step path and January transition; monthly/quarterly date consistency; all three indices; schedule precedence over shared policy overrides and basis; inclusive range overrides; linear day weights; annualized units; scenario shifts exactly once on schedules and derived curves; independence from Fed evidence for supplied schedules; invalid/nonfinite/duplicate dates and conflicting units; missing coverage; strict future valuation extension; end-to-end deposit pricing at 3.65% then 3.35% and independent first-month expense math; audit workbook creation/serialization and exact effective rates.

UI tests compile all inline scripts and the external module. They exercise actual JS handlers with actual Python preview calls, isolated Preview/Apply, stale-candidate rejection, engagement switching during requests, refresh preservation and explicit application, pasted Percent/Decimal/dated/multi-column parsing and invalid date rejection, configuration navigation markup and deployment routes. Existing source dates are not reinterpreted by the presentation cadence.

Baseline failures (unchanged): foundry/tests_parity.py; foundry/tests_protocol.py; foundry/v2/tests_audit_reconcile.py; tests_change_history.py; tests_cost_recovery.py; tests_deposit_fix1.py; tests_fee_guide.py; tests_fee_streams.py; tests_growth_ui.py; tests_interest_balances.py; tests_managed_securities.py; tests_opex_ui.py; tests_pastebox_hardening.py; tests_peer_r240.py; tests_r288_securities_bands.py; tests_settlement_http.py; tests_universal_template.py; web/tests_authoring_stability.cjs. Several existing HTTP modules cannot import FastAPI in this runtime; all counts are from the same runtime for both baseline and candidate.

Browser-rendered QA is blocked: no installed Chromium; Playwright installation attempted and failed with invalid downloaded archives. No screenshot or 1920px visual-quality claim. Responsive styles were inspected; rendered verification remains outstanding.
