# r323 validation

Baseline: exact delivered r322 bundle, b7bee17. Full suite on baseline: 107 modules, 91 pass, 16 fail. Final r323 suite: 109 modules, 93 pass, same 16 failures. Every baseline module exit status matches; the two new modules pass. The full suite is not wholly green. Raw baseline/current logs are included.

18 settlement/cash tests pass: supplied M1–M5 formula inputs and outputs; payable above cash; strict/capped priority; opening cap; no manufactured borrowing; cash-interest flag; signed weighted history; explicit net cost measure; missing/duplicate sources; wrong sign; explicit cadence; integrated stock and income posting identities; audit workbook creation/reloading and dollar/$000s scaling; deleted/ambiguous sources; mutually exclusive balances models; inactive source periods; missing active observations; rejection of regulated repricing sources.

Node executes actual settlement and cash authoring helpers: blank source selection, signed history with thousands separators, invalid-input preservation, typed liability and index selectors, bounded inputs, collapse state, linked deletion protection, index/spread fields, and generated action syntax. All inline JavaScript parses. Whitespace checks pass. This is helper/HTML validation, not rendered browser QA.

All five complete run_v2 outputs match r322 byte for byte under canonical JSON serialization; no fields are stripped. All three pinned result identities pass. This establishes legacy equivalence on those configurations, not proof across every possible engagement. New opt-in configurations correctly create new result/audit series and new fingerprints.

No browser executable or live HTTP verification is claimed. The API surface is unchanged; existing preview/run/audit routes are reused. Unsupported monthly→quarterly holding reinterpretation and runtime-regulated source pricing fail closed. The benchmark uses supplied cash stocks and rates; the user's full engagement remains to be entered/reconciled.
