# r308 validation

- Guide reference regression: five tests pass. Reported Settlement Turns / annual Explicit scenario and affirmative throughput clarification exercise the full mocked request → invalid response → correction → validated instructions pipeline. Persistent invalid mappings stop after two calls; valid first answers make one call.
- AUC source references remain strictly rejected. Cross-product quantity references are accepted only on the matching source and require a reference.
- Engine arithmetic check: Average AUC $1m, yearly turns 8 / 10 / 12 / 10 / 10 / 10 / 9, fee 0.03%. Annual revenue $2,400 / $3,000 / $3,600 / $3,000 / $3,000 / $3,000 / $2,700; monthly and quarterly periodization tested for all seven years.
- r307 Guide vocabulary / annual-change tests: 3 pass. Fee-measure regression: 6 pass.
- Pinned run fingerprints: 3/3 unchanged (3095860cd0b7, 6d7e75a3ea0d, 63efab196c93).
- Full suite: 94 modules, 78 passing, 16 pre-existing failures. Exact failure set matches r307 (93 modules, 77 passing, 16 failing); no new failures.
- No live Anthropic request or deployed session tested. Mocked responses test recovery and local validation, not a guarantee of future AI output. No financial engine code changed.
- Initial suite ran before a test-only correction from rate to the transaction per_unit parameter; corrected test passes. Final suite below supersedes that initial run.
