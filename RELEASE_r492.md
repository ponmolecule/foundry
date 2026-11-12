# Foundry r492 Funding regression contracts

Based on Claude r491, commit 47efaca2615aad19231e8f111270698ba66447b1. The production engine and console HTML are byte-for-byte unchanged from r491. This release preserves the shared-assumption panel, securities target layout, cadence conversion safeguards and isolated-editor helper guards.

Three regression checks are corrected for the deliberate r489 funding change:

- Parity A.8 checks exact authored-constraint/scenario coverage separately from one funding-feasibility check per scenario; extra checks no longer incorrectly fail an old hardcoded count. Missing or duplicate checks still fail.
- Protocol T41f/T42b explicitly enable automatic financing for their legacy financed CRE concentration cases. Severe concentration flags remain required. New T41h/T42d exercise the same portfolios without financing, requiring zero generated borrowing, a severe funding warning and a failed funding-feasibility check.
- The r414 browser test locates the renamed cash-position row. A new browser-independent test exercises the real row-rendering and stock-sampling functions across monthly, quarterly, annual, opening, partial and missing observations, plus the unfunded-plan verdict.

Validation: complete foundry.tests_parity PASS (9/9 financial fixtures and A.8); complete foundry.tests_protocol PASS (344/344); all 16 funding regressions PASS. Node shared-panel, schedule-loaded-status, factor-cadence unit and new funding-contract checks PASS. The browser-based r414 test could not launch Chromium here (socket/permission restriction); r480 browser harness also lacks its expected bundled Chromium. No passing browser integration claim is made. No 329-file full-suite rerun was performed for these test-only changes.

Deploy this release instead of r491 if the updated regression suite is desired. No saved engagement assumptions are rewritten.
