# r289 validation

## Legacy identity

`python3 -m foundry.v2.tests_result_identity`: 3 passed, 0 failed. Pins were not modified: core_bank_test_base f4aa646c3180; patrick_default_v31 6d7e75a3ea0d; universal_template_bank cef1ab6b99c5.

Full serialized `run_v2` output matches r288 exactly for those three fixtures and a fourth case with the legacy interest-balances model active for 36 months. Nothing is removed before comparison. This covers unchanged legacy configurations, not explicit adoption into the new output schema.

## New engine and audit tests

`python3 -m foundry.v2.tests_balance_components`: passes. Six adoption cases cover monthly/quarterly cadence, current-end/prior-end/average interest bases, and delayed residual income. Common raw financial vectors match within $0.000001. Additional cases cover:

- count × share × raw dollars per customer, with zero-opening average and subsequent-period pricing;
- opening/current earning assets, cash allocations, off-book exclusion and total-asset conservation;
- fee and operating cost posting exactly once;
- component RWA classification, including a $300k asset at 100% versus 0% (RWA difference $300k, identical financial statements);
- opening recognized DTA and earning asset booked once;
- legacy canonical linked customer counts;
- missing and circular shared inputs, dimensional mistakes and current-equity circularity rejected;
- actual workbook save/reload, exact dollars-to-$000s conversion and unrounded annual yield/cost rates.

## Full suite versus r288

All `foundry/**/tests*.py` modules and `web/tests*.cjs` scripts discovered and executed with a 150-second per-module limit.

| Build | Modules | Passing | Failing |
| --- | ---: | ---: | ---: |
| r288 | 75 | 59 | 16 |
| r289 | 76 | 60 | 16 |

No new failures. Existing module statuses are identical. This is not an assertion that the full suite is clean. Baseline failures: foundry.tests_parity, foundry.tests_protocol; foundry.v2.tests_audit_reconcile, tests_change_history, tests_cost_recovery, tests_deposit_fix1, tests_fee_guide, tests_fee_streams, tests_growth_ui, tests_interest_balances, tests_managed_securities, tests_opex_ui, tests_pastebox_hardening, tests_peer_r240, tests_universal_template; web/tests_authoring_stability.cjs. Raw logs and summaries are included under delivery/validation.

## Browser interaction

`tools/verify_r289_balances_capital.cjs` passes in Chromium at 1920×1080, 1440×1080, 1366×1080 and 1024×1080. It exercises the actual console HTML with API/autosave stubs, rather than a separate mockup. It verifies top actions, selected expense edits and amount conversion, spreadsheet append, clearing to an empty list, manual add, formula/schedule asset switching, explicit component adoption/restoration, adding components, safe shared-input removal, and retention of dollars-per-unit typing while switching trajectory. No browser JavaScript errors. These are browser authoring checks, not an authenticated production deployment test.

Authoring-state preservation test passes: drafts, selection, focus, scroll and resize; Load/Clear/Append; engagement isolation; preview routing.

The deployment ZIP carries a full-history `main` bundle descending directly from r288. It is checked by cloning the bundle afresh, rerunning fingerprints/new accounting tests, and validating ZIP CRC and release metadata.
