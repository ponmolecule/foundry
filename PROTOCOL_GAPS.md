# PROTOCOL GAPS

## v2 P0 state (2026-07-08)
- T-PAR is GREEN (PA-1): 9/9 fixtures reproduced within ±$1k/line/quarter by
  foundry/v2 (quarterly balance-driven engines, profiles pf_a/pf_b). tests_protocol
  remains the v1 release gate (27/27); the v2 package imports nothing into v1.
- v2 open items: fail-closed validator for the v2 schema (A.13 — T-PAR does structural
  checks only); HTM shock-invariance unit test pending PB rate-scenario work (A.6 partial);
  overrides/FV/tax-semantics/quarterly conventions delivered as parity-mode embryos,
  chassis-native forms due in PB (B.3-B.6).
- Known validate/run seam (step_0a etc.) scheduled for PA item A.13.
