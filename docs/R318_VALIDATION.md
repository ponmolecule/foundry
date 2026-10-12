# r318 validation

Baseline: r317 (00289dd). Full-suite harness discovers 107 modules: 91 pass and the same 16 baseline modules fail. All 105 baseline module exit statuses match. Reported failure counts in the failing modules that print counts also match; the suite is not claimed to be entirely green.

## New tests

- foundry/v2/tests_engagement_setup.py: 22 tests. Early 36→60 extension preserves capital/pre-opening inputs and unrelated identity; charter resolves regulator; per-period defaults and exact period timings rescale; nonrepresentable timings/native schedules reject; dependent data protects cadence/date/charter/reductions; late extension remains available; metadata edits remain available; dated manual/generated curves preserve source observations and cache prefixes; missing curve dates and missing future source values reject; implicit forecast-length ramps reject; reads/no-ops leave fields untouched; link identity changes are dependencies; creation evidence survives the full input-workbook round trip.
- web/tests_engagement_setup.cjs: actual HTML helper execution covers visible values, scoped bounded/responsive controls, draft editing/cancel, rejection without mutation, Apply and result invalidation, no-op without recompute/autosave, protection reasons, extension option, concurrent-input response rejection, snapshot read-only mode, baseline initialization wiring and generated actions.
- The exact API route body is executed from its AST with a response stand-in; POST route and Depends(gate) wiring are asserted. This environment lacks FastAPI, so actual HTTP integration is not claimed. The existing deployment requirements already include FastAPI; none are changed here.

## Compatibility and delivery

All five complete legacy outputs match r317, without removing any fields: core_bank_test_base 3095860cd0b7; patrick_default_v31 6d7e75a3ea0d; universal_template_bank 63efab196c93; pf_a_base 9ea47ad8c3b8; pf_b_base e4ff2d4a236d. The three pinned identities also pass. Read-only setup does not mutate configs. New authoring metadata is inserted only during new creation or an accepted safe edit; legacy frozen result objects remain unchanged.

Python compilation, complete inline JavaScript syntax and git whitespace checks pass. The package contains full-history main, parent/ancestor proof, baseline/current suite logs, full-result JSON comparison and the reproduction helpers. Fresh-clone setup tests and identities pass before ZIP creation.

No browser executable is available, so rendered visual testing is not claimed. Responsive layout is covered by scoped CSS/HTML contracts and helper execution, not screenshots.

The unchanged 16 failing baseline modules are listed in R317_VALIDATION.md, included with the release. Use python3 -m foundry.v2.tests_engagement_setup and node web/tests_engagement_setup.cjs for targeted reproduction. Full suite and complete-result helpers are included in delivery.
