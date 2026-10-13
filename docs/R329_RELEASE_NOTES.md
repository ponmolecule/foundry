# r329 — generalized balance formulas and independent income

Built directly on r328. Opt-in enhancements to the existing named balance-component model; no new product type and no engagement-specific engine branches.

- Add/subtract typed monetary formula terms. An explicit optional zero floor is applied only after finite-value checks; negative stocks still fail without it.
- Link completed current-period on-book deposit/lending product stocks through existing stable catalog IDs, or use total deposits/gross retained lending. Current equity and assets remain prohibited because they would create circular dependencies.
- Explicit annual schedules can represent closing balance targets: ramp from a separately stated prior target, or hold the full target throughout the year. Model/calendar year anchors are explicit. Ordinary Step/Smooth schedules retain their prior interpretation.
- Income can use the modeled balance, an independently specified monetary balance, or an entered amount with a stated month/quarter/year/model-period unit. Separate income inputs do not book another asset. Costs retain their selected modeled-balance basis.
- Cash allocations and residual cash continue to price their actual allocated balances; independent income methods are restricted to separate assets and off-book components.
- The Balance Components audit exposes independent income inputs and posted income, with correct public/workbook money units. The name input now has a visible editing cue.

All new controls use the existing compact local editor and theme. Existing engagements are not migrated. Stored names, rates, target values, choices and links are engagement inputs. The engine does not know spreadsheet references or client product names.

## Limits
A separate on-book asset is shown in the existing other earning asset aggregate, never automatically classified as an AFS/HTM security. The user supplies the appropriate accounting treatment and risk weight. No new security classification or capital rule is implied. Monthly entered schedules cannot be silently reduced to quarterly models; unsupported finer-grained paths fail through the existing series contract. Quarterly annual-target stocks are measured at quarter end; income uses the selected quarterly basis/rate. A separate income basis is a modeling choice, not an endorsement of a source workbook's accounting policy.
