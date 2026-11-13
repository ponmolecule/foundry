# r508: Faster, bounded preview updates with retained results

Based on Claude r507 (c7dceae). No engagement-specific assumptions or financial-formula changes.

## Problem and evidence

On the last reconciled large monthly engagement, an ordinary r507 calculation took 29.4 seconds. Two concurrent calculations in one Python process each took 63.9 seconds, beyond the browser's 60-second cutoff. The browser then cleared its shared result, making every numerical view disappear. These measurements reproduce a failure mechanism; they do not prove the cause of the earlier production incident.

Profiling identified repeated account-activity/fee evaluation as the main CPU cost. Those dependencies and compensation checks have deliberately not been rewritten in this corrective release.

## Changes

- `run_v2` accepts an explicit `scope="base"`; its default remains `full`. Base scope runs the same base projection, compensation checks, component comparisons, financial statements, products and workforce outputs, without the legacy scenario pack. The result explicitly records its base scope; constraint tests include only calculated scenarios. Full-run callers, formal stress, reporting and exports keep their existing default behavior and hash contract.
- Routine browser updates use account-bound background jobs. Each service process permits one active preview job and at most eight pending jobs. New inputs replace pending work from the same browser tab. Identical current jobs/results are reused within that tab for two minutes. Input configs are copied, result ownership is checked on every poll, and old completed results expire.
- The browser polls short status requests, displaying queue/running state. The former 60-second engine request deadline no longer governs ordinary updates. Each network request has a 15-second connection/response limit; a ten-minute overall guard reports unusually long calculations honestly.
- Previous successful figures remain visible after an update failure, with a persistent warning and a calculation-state label. Stale results are not marked current. Existing engagement-switch logic still clears the previous engagement's results. Old responses cannot overwrite newer edits.
- The legacy standard pack runs explicitly on its screen. Audit snapshot preparation also requests a full job; it does not pin a base-only preview as a full audit run. Workbook generation itself retains its existing endpoint.
- Runtime logs include job ID, scope, queue time, calculation duration and outcome. Configuration contents are not logged by the job wrapper.

## Verification

- Large-engagement real jobs: first preview 9.17 seconds end-to-end (9.07 calculation); second preview 17.14 seconds including waiting for the first (7.98 calculation). Full run 29.10 seconds.
- Both preview results exactly match the full run for financials, products, workforce, funding, fee economics, fee quantities and interim tax. Financials also match the saved reconciled baseline.
- New Python tests cover queue bounds, serialization, replacement, account isolation, snapshot copying, expiry, validation/runtime failures and recovery, authenticated endpoints, base/full parity, unchanged input config and scope-specific hashes.
- New JavaScript tests exercise actual preview orchestration: routing, polling beyond 60 seconds, validation/network failure retention, recovery, late responses, engagement isolation and full audit snapshot routing.
- Existing stress and reporting regression results are recorded in the delivery validation notes.

## Deployment and limits

The committed Procfile starts one Uvicorn process. Preview jobs are process-local and ephemeral, matching that deployment. Do not scale this implementation to multiple web workers/replicas without a shared job backend or explicit session affinity. A restart loses an in-flight job; polling reports the missing job and previous results remain available in the open tab. Saved engagement inputs are unaffected.

This bounds preview CPU work; formal stress, Design Lab and workbook-generation endpoints retain their existing execution model and can still compete for server resources. Further fee-evaluation optimization and shared durable job infrastructure are separate work. This release does not establish a client-load capacity guarantee.

Not pushed or deployed. Import `main` from the delivery bundle using the existing deployment workflow. Full release check: `python tools/release_check.py r508`.

### Completed regression checks

- r498 stress: 35 passed, 0 failed.
- r499 reporting: 47 passed, 0 failed.
- r504 corrections: 20 passed, 0 failed.
- r505 release identity: 4 passed, 0 failed.
- r508 job tests: 5 test cases passed.
- r508 actual JavaScript orchestration/notice tests passed; extracted console JavaScript syntax check passed.
- Full browser rendering was not independently exercised in this environment. New tests execute the preview functions with controlled DOM/network substitutes. The earlier 354-module suite was not rerun; this release does not claim that suite's known baseline failures were resolved.
