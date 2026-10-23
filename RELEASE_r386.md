# r386 — extend existing deposit and Formula mechanics

Built on r385. The existing deposit customer-count equation now has optional local weighted detail, a link to another deposit's per-customer amount, and an optional balance share. The existing weighted evaluator and Series editors are reused. No shared-assumption registry or create/delete lifecycle is required for deposits. Inactive amount-method inputs survive switching and configuration save/reload.

Different portions continue to use ordinary deposit products and existing pricing. There is no new pricing engine. Acquisition, attrition, streams and ordinary costs retain their existing mechanics.

The existing expense Formula accepts an optional flat Add/Subtract base; its ordinary factors apply afterward. New read-only catalog observations expose actual product deposit interest, resolved reference rates and current/cumulative gross acquisition shares. An optional selected-balance condition supports zero-activity gating. No separate expression-tree driver, arbitrary formulas or engagement-specific runtime defaults are introduced. Existing source checks and cycle guards apply to base items as well as ordinary factors.

Precision and layout: local dollar amounts and weights retain supplied precision, optional breakdowns collapse, linked assumptions are selected through ordinary controls, and the existing real-time product views remain. Source clarification notes remain unresolved unless explicitly recorded otherwise.

Validation:
- 5 new backend cases cover 60-month live linked balances, source-equivalent split balances, rename identity, source edits, native quarterly observations, missing/cyclic/invalid inputs, mixed ending/average margin economics, time-varying gross attribution, negative results, zero handling, conditions, isolation from unrelated deposits, actual Profile B interest including minimum top-ups, and audit units.
- 10 existing r380/r381 deposit cases pass. All 121 existing expense checks pass. Existing source-catalog regression passes.
- New browser checks exercise actual grouped product controls, local row editing, amount links, saved/reloaded inactive inputs, existing Formula base edits, actual source-catalog selection, linked rates, zero-share policy and 1440/1024/768 containment. Existing pricing browser checks, 18 formula layouts and legacy expense browser promotion checks pass.
- All 12 full core/parity fixture JSON outputs are identical to r385/r382.
- Full audit workbook export succeeds with the new balances and Formula.

See docs/r386-existing-mechanics.md for the authoring map and explicit limitations. Monthly source reconciliation requires monthly cadence; native quarterly ratios/conditions are not silently reconstructed from monthly results. Operating Accounts still requires user data entry and reconciliation. Not deployed or pushed.
