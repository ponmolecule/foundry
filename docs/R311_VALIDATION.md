# r311 validation

- Six new tests pass: linked-source distinction and original description; missing period returns one clarification without a correction call; incomplete plan rejected by Apply; explicit invalid period rejected; supplied periods preserved; existing question preserved; linked migrated TPV materializes and computes revenue/cost without a second coefficient; raw percentage limit represented as unsupported.
- r310 Apply regression: 28 checks pass. Its release-specific build stamp assertion is now a general Foundry stamp assertion so it does not falsely fail on subsequent releases.
- r308 reference-repair tests: five pass. r307 vocabulary tests: three pass.
- Pinned results: 3/3 unchanged (3095860cd0b7, 6d7e75a3ea0d, 63efab196c93).
- Full suite comparison: r310 95 modules / 79 passing / 16 failing; r311 96 modules / 80 passing / 16 failing. Identical failing module set, no new failures.
- Mocked upstream only; no live AI or deployed-session validation. No financial engine changes.
