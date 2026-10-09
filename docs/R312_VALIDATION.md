# Validation

Baseline r311; release r312. Full suite: 97 modules, 81 passing, 16 failing; identical failing module set to r311 (96 modules, 80 passing, 16 failing). All failures remain visible in the bundled logs; this is not an all-green suite.

New regression module: 4 tests covering index participation, fixed-rate isolation, floor/cap, unchanged lending rate function, new streams versus shorter saved lists (read-only), duplicate-priced links versus zero-price drivers, empty coefficient warning, and real-engine monthly/quarterly deposit rate and interest output. Public rateQ is rounded to 0.01 percentage points; interest assertions allow only that rounding envelope.

Existing Governance schedule regressions pass (6 + 15 checks). Existing strict full-result fingerprints match without deleting fields:
- core: 3095860cd0b7
- patrick: 6d7e75a3ea0d
- universal: 63efab196c93

All inline console JavaScript compiles in Node vm.Script. No deployed AI or live browser test is claimed.
