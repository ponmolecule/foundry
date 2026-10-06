# r305 validation

Baseline: r304 b9f7fea. Opt-in engine changes; legacy outputs unchanged.

- Six numerical/regression tests in `python3 -m foundry.v2.tests_fee_measures`: pass. Covers annual transitions, Growth, Flat equality, monthly/quarterly/annual rate timing, selected balance numbers, invalid inputs, old/raw versus new stock-share equivalence (including explicit zero), and engine execution with/without cross-product fee links.
- Complete serialized outputs compared without stripping fields: 3 public fixtures plus 9 raw Profile A/B parity configurations, 12/12 identical to r304. Comparison files included in delivery.
- `python3 -m foundry.v2.tests_result_identity`: 3/3 fingerprints unchanged (3095860cd0b7, 6d7e75a3ea0d, 63efab196c93).
- Full discovered suite: 91 modules, 75 pass, 16 fail. Same failure set as r304 (90 modules, 74 pass, 16 fail); no new failing module. Initial development failures were corrected before this final suite. Final targeted run adds the sixth case to the new module and passes.
- Config layout: 107 pass, 0 fail. Assertion now expects the source explanation to describe the actual per-stream Average/EOP choice rather than claim every consumer uses Average.
- Chromium checks at 1920 / 1366 / 1024 px: pass. Uses the actual console HTML and JavaScript with API/auth/autosave stubbed; not a production-session test. Legacy identity share displays 100% without mutating saved economics; fresh derivation starts at 100%; balance selector saves; Flat/Growth/Explicit edits and schedule replacement work; schedule collapses after saving; inactive rate path is suspended; no JavaScript errors. Screenshots included. Main card geometry is retained rather than redesigned.
- JavaScript parsing and git diff --check: pass.

Pre-existing failures: foundry/tests_parity.py; foundry/tests_protocol.py; foundry/v2/tests_audit_reconcile.py; tests_change_history.py; tests_cost_recovery.py; tests_deposit_fix1.py; tests_fee_guide.py; tests_fee_streams.py; tests_growth_ui.py; tests_interest_balances.py; tests_managed_securities.py; tests_opex_ui.py; tests_pastebox_hardening.py; tests_peer_r240.py; tests_universal_template.py; web/tests_authoring_stability.cjs.
