# r335 validation

Baseline: r334 41f8a280b42e9052fca9dfc0f40500909b0ea66f.

Full final suite: 121 modules, 103 passing, the same 18 baseline failing modules. Baseline r334: 119 modules, 101 passing, 18 failing. The two added modules pass. Full baseline failure list is retained in R332_VALIDATION.md. No new failing modules.

All five complete public fixture outputs are byte-identical with no fields removed. Three pinned identities remain 3095860cd0b7, 6d7e75a3ea0d, 63efab196c93. An existing external-tax engagement also has unchanged complete public output.

New engine tests independently reconcile carryforward utilization, exhaustion, new losses, committed prior state and repeated-evaluation purity; credit below/at/above threshold under both explicit treatments; positive/signed/zero-base allocation; cadence; expression-based reuse; isolated preview; retained inputs and placeholders; editing IDs; missing/unit/invalid-bound rejection; public/audit units; and balance-sheet identity. Complete raw engine results equal those from the same materialized rules without block metadata. Configuration fingerprints appropriately differ after explicit metadata changes; no hash fields are stripped to establish legacy compatibility.

New UI tests run actual handlers against the Python planner for all three blocks, preserve entered inputs, verify opt-in current provision selection, Preview/Apply/Cancel isolation, stale-response rejection, engagement switching, checkbox selection, visible controls and responsive layout declarations. All inline scripts compile. Existing external-tax tests pass. Preview endpoint authentication is checked in app.py. git diff --check passes.

Browser binaries are unavailable: no rendered browser QA or pixel-fidelity claim is made. The actual engagement's external tax is still partially authored and remains unreconciled until its blocks, payment timing and deferred-tax choices are completed.
