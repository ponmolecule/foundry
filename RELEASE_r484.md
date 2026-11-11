# r484 — Schedule errors attributed by path, not content

Engine. No console change. No calculation change: all 12 fixture configs give byte-identical results on r483 and r484, config and run hashes included.

## The r483 gap

r483 named a failing schedule by matching its content (values plus cadence) against the saved schedules. A dormant schedule with identical content was named too. Example: an active unit-fee schedule {Y1, Y2} missing Y3, and a dormant level schedule with the same two values. r483 reported both; only the unit fee blocks the run.

## What r484 does

1. Before validation or a run, every saved explicit schedule (active or dormant) is tagged with its path in the assumptions. The tag rides on the list or mapping itself, survives copies, and serialises exactly like a plain list or dict, so hashes and outputs do not change.
2. The resolver that fails records the tag of the schedule it was given, together with its error text. Converted copies (values coerced to numbers, normalized series specs, periodized flows) keep the tag.
3. The error names only the recorded paths whose error text is in the raised message. Content is never compared. A dormant schedule is never resolved, so it is never recorded and never named.
4. A failure without a tag (for example a schedule replaced by a scenario overlay) leaves the engine's own message unchanged rather than guessing.

Year-end balance targets are now attributed as well ("Interest-bearing balances · component 'X' · ... Y3 missing").

The r483 smooth interpolation fix is unchanged.

## Verification

- New: foundry/v2/tests_r484_schedule_path_identity.py (14 checks). The review case: active and dormant schedules with identical values and cadence, only the active component named. On r483 the same config names both. Also: the level schedule is named when it is the active one; untagged or unknown-path failures stay unchanged; validated config serialises identically; year-end targets named; a sweep that shortens each of the 18 active template schedules by one period and checks that each is named alone; smooth lookahead.
- r482 (17) and r483 (7) checks pass.
- Differential run of all 12 fixture configs on r483 and r484: identical, including config_hash and run_hash.
