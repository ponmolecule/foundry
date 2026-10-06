# r306 validation

- New-default regression module: 3 tests pass across the two server template source fixtures and universal workbook source. Templates are copied, only requested default fields change, and explicit saved cash-yield inputs still generate income.
- Actual /api/v31/template and /api/v2/template function bodies executed by tools/verify_r306_template_defaults.py with auth/response wrappers stubbed: pass. Full FastAPI server not started because FastAPI is unavailable in this execution environment.
- Embedded JavaScript TEMPLATE evaluated in Node: all four funding assumptions zero; FDIC zero where present. Full console script parses.
- Universal FIW built from neutral defaults and imported back: all four funding defaults and FDIC remain zero.
- Existing zero-assessment regression: pass (missing FDIC zero; explicit 5 bp still accrues).
- Frozen fixture fingerprints: 3/3 unchanged from r305.
- Full suite: 92 discovered modules, 76 passing and 16 pre-existing failures. Exact failing module set identical to r305 (91 modules, 75 passing, 16 failing). No new failures.
- Config layout: 107 passing, 0 failing after final template-literal edit. git diff --check passes.

No changes to engine arithmetic or saved-configuration loading. Existing sample fixtures remain intact and serve as explicit-input regression data; only template delivery paths neutralize the defaults.
