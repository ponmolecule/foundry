# r471 — Independent asset components in Formula / level

Based on r470. Retains Claude’s component-table design and the 30/70 capital layout.

## Authoring

- Add asset component creates an independent asset-level path with its own name and depreciation rate. Asset level supports the existing Flat / Growth / Schedule editor in $000s.
- Each component source can be Entered asset level, Entered quantity × amount per unit, or Linked workforce quantity × amount per head. Entered quantities can represent branches, locations, machines, or other units without creating workforce roles.
- Quantity components retain lag, pre-M1 quantity, grouping and rounding controls. Direct asset levels hide those irrelevant controls.
- Switching sources retains each mode’s paths and timing/grouping settings in the component, so returning restores prior inputs. Existing workforce components retain their saved structure and calculations without migration or re-entry. Add linked component remains available.
- This release adds entered asset and quantity paths; the linked source picker continues to expose workforce quantities. It does not claim support for every source-catalog link.

## Engine and precision

The existing Series resolver now accepts entered quantity paths as fixed-asset component drivers, as well as linked Series. A direct asset-level component uses a neutral quantity of one and the entered dollar level. The stock, CAPEX, depreciation and disposal equations are unchanged. Derived generic formulas remain rejected. FIW exports entered quantity paths as counts.

Component depreciation diagnostics remain in $000s but preserve precision instead of rounding each month to 0.01 ($10). This fixes an executive premium of 1.5 × 20% displaying as 0.4 rather than 0.3 over twelve months, and avoids the associated false cap notice. The engine’s calculated depreciation expense is unchanged.

## Verification

- Reconstructed the ten technology/furniture components visible in the supplied screenshot; complete raw engine output is exactly equal to r470, including M1 gross assets of $56,000.
- 29 unittest cases pass: new independent asset/quantity/cadence/precision tests, r464 driver tests, r467 unit tests, and r459 component-switch tests including frozen All-On output hashes.
- Existing fixed-asset checks: 48/48. Existing fixed-asset UI: 11/11. Growth UI: 84/84.
- Node tests render each source mode, verify source-path restoration and existing linked timing restoration, check scheduled borrowing additions, and compile inline scripts.
- Reference coverage regenerated. Browser visual checks remain unavailable in this environment; no browser pass is claimed.

The conference-room component remains the next Engagement 5 authoring/reconciliation step; it is separate from the completed technology and furniture entries reviewed here.
