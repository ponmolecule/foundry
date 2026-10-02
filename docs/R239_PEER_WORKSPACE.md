# r239 — Peer comparison workspace

Built on r238, commit 93418362bfb6ba72e0f5ebc422d576ae1ecab7d5. Existing model grammar, top navigation, financial calculations and Klaros palette remain intact.

## User-facing changes

- Calendar comparison: modeled Q12, stacked percentile labels/values, true min/max, range bars, metric-specific filing dates, observation counts and placement. Missing data stays unavailable; it is never zero-filled.
- Vintage: modeled and median trajectories with P25–P75 bands and age-specific counts. Detailed quarterly values and filing conventions remain expandable. Leverage now has its modeled overlay.
- Download comparison: exports the displayed snapshot without another substrate query. Broad cohorts export aggregate distributions; selected-peer vintage snapshots include the already-loaded observations and bank-column Excel calculations. Charts and definitions are included. No full-population historical export or background job is introduced.

## Retrieval changes

The calendar screen requests the latest quarter only instead of full histories. Browser requests are limited to three, with a 30-second total scheduling budget, stale-generation protection and aborts. Public peer responses and repeated vintage builds use a bounded 128-entry, two-minute server cache with single-flight requests and three concurrent loaders. Browser caching is bounded to 64 successful responses. Database statement/connect timeouts already existed and remain in force. Cache refresh is not an immediate database refresh; successes can be reused for two minutes.

Stored-cohort min/max uses one SQL aggregate over the selected metric/group/quarter. Extrema publish only when distinct-certificate coverage equals the published count. A failed extrema query preserves valid percentile results. Ad-hoc cohorts compute min/max in their existing aggregate query. Vintage extrema use values already fetched, with existing suppression rules retained.

The existing under-$200M lending-peer selector still caps membership at 150 certificates; this release does not expand that workload or claim it covers all eligible banks.

## Verification

- Complete module inventory: 53 Python modules on pristine r238; 54 on r239. Both have the same nine failing modules; no new failures. Plain test-function modules do not self-execute through `python -m`: the five curated vintage and four quarterly tests were invoked explicitly, all passing.
- New workspace module: four passing tests covering latest-quarter SQL/extrema coverage, single-flight cache and mutation isolation, Excel blank/zero/formula handling, and authenticated export without database calls.
- Three pinned run fingerprints remain f1384367e87a, 65c7d71491d6 and f04db06d9389.
- JS checks pass: curve dates, authoring state, surplus policy, workspace helpers and full-page workspace browser. The existing authoring-stability test fails the same Load-draft assertion on r238 and r239.
- Browser: seven metric requests, peak concurrency three, revisiting requests zero additional metric fetches, no page errors, comparison fits a 1440px viewport. Actual code rendered and inspected at 1440px and 800px; example peer observations are illustrative test fixtures, not live financial data.
- Export endpoint returns a valid workbook while database calls are forbidden by a test mock.

No CHARTERIQ_DATABASE_URL is configured here. Production query plans, latency, real cohort coverage and operational retrieval errors remain to be checked against the deployed substrate. This is a tested code improvement, not a claim that every live retrieval failure has been eliminated.

## Deployment

The full-history bundle advertises main at the new r239 commit, descended from r238. Use the existing delivery script. It has not been pushed or deployed by this build. Keep the r238 ZIP for rollback; an older ZIP may require the established branch/reset deployment procedure rather than merging a reverse history.
