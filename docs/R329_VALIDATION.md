# r329 validation

Baseline: r328 b3e02f498eb9afb67ce77704075630f315e3c21a. Full-suite harness discovers foundry/**/tests*.py and web/tests*.cjs, runs Python modules and Node scripts with four workers and a 150-second per-module limit.

- r328: 112 modules, 100 pass, 12 fail.
- r329: 114 modules, 102 pass, the same 12 fail. No new failing module or changed exit code.
- New engine tests cover typed signed terms, explicit floors, current deposit/lending links, stable selected-product IDs, increasing/declining annual targets, nonzero prior targets, midyear calendar anchors, independent balance-yield income, periodic entered income, monthly/quarterly ending levels and constant annual income, one-time asset/income posting, exact/public/workbook units, and seven rejected inputs.
- New UI tests cover authoring, immutable rendering, catalog choices, treatment switching and all inline/generated JavaScript parsing. Existing settlement/focused-navigation tests pass.
- Complete serialized engine output is byte-identical for all five runnable baseline configurations. No fields are removed. All three pinned identity checks pass.
- Export validation is exercised by the full-suite settlement HTTP and audit tests; all pass.
- git diff --check passes.

No rendered browser or live-deployment QA was performed. Quarterly equivalence tests concern annual targets and constant annual income; they do not assert that current-quarter pricing reproduces arbitrary monthly balance/rate products. Unsupported finer-than-model entered schedules fail through the existing series resolver.

## Existing failing modules
- foundry/tests_parity.py
- foundry/tests_protocol.py
- foundry/v2/tests_cost_recovery.py
- foundry/v2/tests_fee_streams.py
- foundry/v2/tests_growth_ui.py
- foundry/v2/tests_interest_balances.py
- foundry/v2/tests_managed_securities.py
- foundry/v2/tests_opex_ui.py
- foundry/v2/tests_pastebox_hardening.py
- foundry/v2/tests_r288_securities_bands.py
- foundry/v2/tests_universal_template.py
- web/tests_authoring_stability.cjs
