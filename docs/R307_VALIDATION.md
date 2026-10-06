# r307 validation

- New Guide Me regression: 3 tests pass. Manifest/schema source scope and labels; exact reported description passes the full request/validation/render pipeline with a mocked upstream response; Flat/Growth/Explicit annual-change plans retain actual annual_change in engine shape validation and reject monthly change paths.
- Existing fee-measure regression: 6 tests pass.
- Current fingerprints: 3/3 unchanged from r306.
- Full suite: 93 modules, 77 passing, 16 pre-existing failures. Exact failing module set matches r306 (92 modules, 76 passing, 16 failing). No new failing module.
- Existing comprehensive tests_fee_guide now progresses beyond the reported KeyError; its remaining failure is unavailable FastAPI in this environment. No live Anthropic call or production-session test was performed. Mocked tests verify the local pipeline, not external API availability.
- Final targeted run includes Year/Step validation and all three annual change path cases. git diff --check passes.
