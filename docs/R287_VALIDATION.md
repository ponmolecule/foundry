# r287 validation

## Engine identity

`python3 -m foundry.v2.tests_result_identity`: 3 passed, 0 failed. Existing pins were not changed:

| Fixture | run_hash |
| --- | --- |
| core_bank_test_base | f4aa646c3180 |
| patrick_default_v31 | 6d7e75a3ea0d |
| universal_template_bank | cef1ab6b99c5 |

No engine, schema, fixture, audit or calculation files changed.

## Full suite compared with r286

Discovered and executed all `foundry/**/tests*.py` modules and `web/tests*.cjs` scripts (150-second per-module timeout, four concurrent workers):

| Build | Modules | Passing | Failing |
| --- | ---: | ---: | ---: |
| r286 | 74 | 58 | 16 |
| r287 | 74 | 58 | 16 |

Identical module statuses; identical FAIL/Error assertion lines for all 16 baseline failures. This is not a claim that the entire suite passes. Baseline failures: foundry.tests_parity, foundry.tests_protocol; foundry.v2.tests_audit_reconcile, tests_change_history, tests_cost_recovery, tests_deposit_fix1, tests_fee_guide, tests_fee_streams, tests_growth_ui, tests_interest_balances, tests_managed_securities, tests_opex_ui, tests_pastebox_hardening, tests_peer_r240, tests_universal_template; web/tests_authoring_stability.cjs. Raw logs included under delivery/validation.

## Actual browser rendering and interaction

Chromium, 1920×1080, 1440×1080, 1366×1080 and 1024×1080. Representative monthly model with explicit fiduciary schedules, linked MAB source, two expanded liability components, and three managed securities.

- No page JavaScript errors, page horizontal overflow or controls extending beyond their section in r287. The r286 case overflows at 1024 pixels.
- Full configuration equality with r286 after rendering (stable source-catalog IDs assigned before rendering).
- All 95 inputs, selects, textareas, buttons and links preserved: same values, handler expressions and complete select option sets. Ordering deliberately changes.
- Source dropdown bottom precedes help-text top: no overlap.
- Opening, typing into and closing an uncommitted schedule leaves configuration unchanged.
- Funding edit updates its header value and retains all six summary chips.
- Switching entered yield → curve → entered retains the schedule editor; selecting GSE updates the detail while preserving all three table rows.
- Selecting average affiliated-cash interest basis writes the existing configuration property.

| Expanded section, 1920 px | r286 height | r287 height |
| --- | ---: | ---: |
| Funding allocation | 427 | 393 |
| Interest-bearing balances | 1618 | 1052 |
| Other liabilities | 918 | 824 |
| Managed portfolios | 1407 | 1219 |

Narrow layouts intentionally wrap rather than squeeze; compactness is not obtained by hiding controls. Screenshots are from the actual HTML, not mockups. Sticky global bars are made non-sticky only during isolated section capture so they do not obscure the screenshots. API calls were stubbed; this browser check verifies authoring and layout, not an authenticated production save or server preview.

Reproduce with Playwright and Chromium:

```
CHROMIUM_PATH=/path/to/chromium node tools/verify_securities_layout.cjs /path/to/repository /path/to/output
```

Set NODE_PATH if Playwright is supplied outside the repository. Add `--baseline` for comparison renders of r286. `git diff --check` passes.
