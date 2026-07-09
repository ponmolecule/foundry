# PROTOCOL GAPS

## v2 P0 state (2026-07-08)
- T-PAR is GREEN (PA-1): 9/9 fixtures reproduced within ±$1k/line/quarter by
  foundry/v2 (quarterly balance-driven engines, profiles pf_a/pf_b). tests_protocol
  remains the v1 release gate (27/27); the v2 package imports nothing into v1.
- v2 open items: HTM shock-invariance unit test pending PB rate-scenario work (A.6 partial);
  overrides/FV/tax-semantics/quarterly conventions delivered as parity-mode embryos,
  chassis-native forms due in PB (B.3-B.6).
- Known validate/run seam (step_0a etc.) scheduled for PA item A.13.

## PA-2 (2026-07-09)
- A.13 delivered both sides: v2 fail-closed validator (validate_q, wired ahead of every
  parity run, negative controls in T-PAR) and the v1 validate/run seam closed
  (TOP_REQUIRED extended; T16 guards it; harness now 29/29).
- A.7 delivered: ratio layer with MSR threshold deduction + intangibles, attested
  against predecessor ratios within 0.02pp inside T-PAR.
- A.9 re-phased to PB per reconciliation note (results-dict change moves run hashes).
