# r483 — Two corrections to r482 from review

Engine. No console change.

## 1. Smooth schedules keep their lookahead point

r482 stopped the final modeled interval of a smooth schedule from interpolating toward a point supplied beyond the horizon. Example: annual smooth values [1, 2, 3, 4] on a 36-month model. r481 ran M36 at 3.9167 (11/12 of the way to Y4); r482 flattened Y3 at 3.0. That changed an already complete schedule.

r483 restores the r481 rule: when the schedule supplies the next point it is used; when it does not, the final interval stays at its own value. A blank supplied next point is rejected (as in r481). Quarterly smooth behaves the same way.

## 2. Errors name the schedule that actually failed

r482 attached component names by matching the failure's cadence and first missing period against every saved schedule, so an active schedule missing Y3 could also implicate a dormant schedule missing Y3.

r483 records the identity of the failing schedule where it fails. Each strict resolver records the schedule's content (its values, or its period-keyed mapping, plus cadence) at the moment it raises; the error is then named only by saved schedules with that exact content. A dormant schedule with different content is never named. If a failure cannot be attributed, the engine's own message is shown unchanged.

Limit: two schedules with identical content (same cadence and every value equal) cannot be told apart by content, so both would be named.

## Verification

- Differential run of all 12 fixture configs on r481 and r483: identical results for every one (config and run hashes excluded). This is the basis for "complete schedules give identical results".
- New: foundry/v2/tests_r483_schedule_identity.py (7 checks: smooth lookahead annual and quarterly, smooth without lookahead, blank lookahead rejected, dormant-only runs, active-plus-dormant names only the active schedule, two active failures each named by their own component).
- r482 checks (17) still pass.

Full suite on 94ecc0f7: 322 files, 12 failing, the same 12 that fail on r482, r481, r480 and r479.
