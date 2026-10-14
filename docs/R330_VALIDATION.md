# r330 validation

Baseline: r329 `aea102fcb74b55d45d14a37c918f06d1f9429ef1`.

- Full suite: baseline 114 modules, 102 pass, 12 fail; candidate 116 modules, 104 pass, the same 12 fail. No new failing module. Harness runs all foundry/**/tests*.py and web/tests*.cjs with four workers and a 150-second limit.
- Five complete public results are byte-identical to r329. No fields are removed or normalized before comparison. All three pinned fixture fingerprints pass. Empty Other income also preserves exact engine output.
- New engine tests verify monthly-to-quarterly SUM aggregation, model-period amounts, annual amount conversion, typed monetary quantity links, missing/count source rejection, signed amounts, duplicate IDs, posting once, unchanged fee/NII lines, tax reconciliation, and exact/public/audit units.
- New UI tests verify immutable rendering, add/remove, typed source choices, configuration navigation, inline JavaScript syntax, explicit compensation wording, failed-switch retry preservation and successful switching through the actual engagement loader with a mocked HTTP response. Existing balance/formula UI tests pass.
- No live deployment or rendered browser QA: Playwright is installed but its Chromium executable is unavailable in this environment. No visual screenshot evidence is claimed.
- git diff --check passes.

Existing failures remain those listed in R329_VALIDATION.md: parity, protocol, cost recovery, fee streams, growth UI, legacy interest balances, managed securities, Opex UI, pastebox hardening, r288 securities bands, universal template, and authoring stability.

Other income uses the configured general income-tax policy; its classification is descriptive and does not implement a special dividend tax adjustment. Entry is an income flow, with no manufactured investment balance, ownership hierarchy or consolidation eliminations.
