# r284 validation

## Source and result identity

Direct parent: r283 `b6655ac677f5e3502cdf4deca38044782f013986`. A separate detached worktree at that commit supplied the baseline. No client workbooks or engagement data are included in this release.

| Configuration | r283 full-result hash | r284 full-result hash |
|---|---|---|
| core_bank_test_base | `02a7295b4351` | `f4aa646c3180` |
| patrick_default_v31 | `65c7d71491d6` | `6d7e75a3ea0d` |
| universal_template_bank | `f04db06d9389` | `cef1ab6b99c5` |
| pf_a_base | `a8bfb4b7d1be` | `9ea47ad8c3b8` |
| pf_b_base | `6d5436c6bfcd` | `e4ff2d4a236d` |

Hashes cover complete results, including new tax audit data and presentation references. They deliberately differ. Whole-result guards retain historical pins; no keys are removed to pass equivalence tests.

Financial comparison, all values $000s:

- **core_bank_test_base:** all previously published financial series identical. New tax ledger and mapping metadata change the fingerprint.
- **patrick_default_v31:** only the existing NOL memo differs. Within-year losses remain provisional, rather than immediately becoming carryforwards. Ending NOL is unchanged at 16,831.28; pretax, tax, NI, assets, and capital match.
- **pf_b_base:** all previously published financial series identical; new tax audit metadata changes the fingerprint.
- **pf_a_base:** final quarter tax decreases from 0.56 to zero because annual YTD income remains negative; NI rises from 12.71 to 13.27. Ending equity rises from 49,381.87 to 49,382.43. Ending carryforward reflects annual net losses, 10,617.57 rather than the erroneous period ledger's 10,620.22.
- **universal_template_bank:** a same-year current-tax reversal changes period 3 tax from zero to -27.33 and NI from -272.30 to -244.92. Correct cash/retained earnings subsequently affect endogenous investment interest and asset targets. Ending equity changes from 200,193.17 to 200,193.26. The complete first/ending changes are in R284_FINANCIAL_COMPARISON.json.

Flow arrays start at index 0; Profile A balance arrays include the opening at index 0. Display values above are public rounded values; arithmetic and detailed audit tests use engine precision.

## Numerical and integration checks

- 18 ledger tests pass, including same-year offsets, prior-year 80% limits, reversible YTD deductions, annual-estimate revisions, discrete opening-allowance changes, fiscal years, horizon boundaries, supported/withheld loss benefits, duplicate commits, and invalid input rejection.
- A deterministic randomized test independently checks 300 annual closures across full, partial, and unrecognized future-year benefits against annual legal tax, NOL conservation, and DTA movements.
- 10 production/integration tests pass: Profiles A/B, current/deferred reconciliation, balance identities, endogenous cash-interest convergence, monthly/quarterly annual consistency, exact/public audit units, Call Report assets, validation, and console handlers.
- Browser interaction with the actual console passes at **1920, 1366, 1024, and 768 px**: tax inputs visible and within their card, correct fiscal-year estimate rows, dollar/$000s conversion, mode switching, and no page runtime errors.
- Strict whole-result fingerprint check passes, 3/3. Explicit 5 bp FDIC fixture fingerprint is `4c3613f2d783`; missing assessment defaults and entered yields remain tested.

## Full suite and pre-existing failures

The baseline discovers **70 modules: 63 Python and 7 JavaScript**, with 58 passing and 12 failing. r284 discovers **72 modules: 65 Python and 7 JavaScript**, with 60 passing and the same 12 failing. This is not an all-green repository.

The existing failing modules are:

- `foundry.tests_parity`
- `foundry.tests_protocol`
- `foundry.v2.tests_cost_recovery`
- `foundry.v2.tests_fee_guide`
- `foundry.v2.tests_fee_streams`
- `foundry.v2.tests_growth_ui`
- `foundry.v2.tests_interest_balances`
- `foundry.v2.tests_managed_securities`
- `foundry.v2.tests_opex_ui`
- `foundry.v2.tests_pastebox_hardening`
- `foundry.v2.tests_universal_template`
- `tests_authoring_stability.cjs`

Failure assertions were compared, not just exit status. The unchanged Call Report mapping gap for `ebtda`/`msrAmort` and the r283 duplicate-CSS assertion remain. New tax series have explicit presentation references; the recognized tax asset is included in other assets. Tax protocol assertions that expected per-quarter NOL creation and omission of tax audit series were replaced with the correct tax-year contract; protocol remains 341/342 passing, with only its baseline CSS failure.

Old financial parity with the erroneous tax ledger is intentionally not asserted. Updated fingerprints and targeted independent arithmetic tests guard the corrected result. The deposit retention full-result guard now uses the documented current fixture pin rather than stripping tax fields or asserting equivalence with the old engine.

Commands:

```sh
python3 -m foundry.v2.tests_tax_interim
python3 -m foundry.v2.tests_tax_integration
python3 -m foundry.v2.tests_result_identity
python3 -m foundry.v2.tests_zero_assessment_defaults
```

Full discovery runs every `foundry/**/tests*.py` module with `python3 -m` and every `web/tests*.cjs` with Node. Logs and source/current exit summaries are included in the delivery validation directory.

## Deployment and accounting limits

Delivery uses a full-history `main` bundle with one commit on r283; verify a clean fast-forward from r283 before deployment. Earlier frozen configurations can re-verify to different hashes because this release intentionally corrects tax mechanics.

See R284_TAX_METHOD.md for supported assumptions and excluded tax matters. In particular: no annual estimate is silently fabricated, recognition requires documented support, and current-tax provision is not a cash installment schedule. These tests do not establish an engagement-specific valuation allowance conclusion or reconcile the user's entire engagement.
