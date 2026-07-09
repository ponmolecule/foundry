# PROTOCOL GAPS

## v2 P0 state (2026-07-08)
- T-PAR (foundry/tests_parity.py) is RED BY DESIGN: 9 predecessor parity fixtures are
  frozen (hash-verified, cross-language) with v2 Tier-3 configs, and no v2 engine exists
  yet to satisfy them. Green requires ±$1k/line/quarter reproduction of all 9.
  tests_protocol.py remains the release gate for v1 behavior (27/27).
- Known validate/run seam (step_0a etc.) scheduled for PA item A.13.
