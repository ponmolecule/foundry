# r463 — Cost multipliers for entered and linked periodic costs

Product cost — periodic amount now offers the same optional multiplier controls as other product costs: Flat, Growth and Schedule, with the existing natural-period, Step/Smooth and paste controls. This applies whether the base dollars are entered or linked acquisition spend. No multiplier means 1, preserving existing results.

Cost = sum(source spend × allocation) × multiplier. In quarterly models, each canonical month’s cost is multiplied by that month’s factor before aggregation, so intra-quarter multiplier changes are applied correctly. Entered amount paths receive the same treatment. The multiplier is dimensionless and is not divided by cadence. Existing timing, source allocations, gross-up eligibility and cost posting remain in place. Finite nonnegative multiplier validation applies, including schedule values.

Adding a spend source preserves an existing multiplier and the inactive entered amount path. Removing the final link restores the entered path and retains the multiplier. Existing r461/r462 links remain valid; engagement inputs and source selections are not automatically modified.

## Use

Operating Account Digital CAC → Costs → + Add multiplier. Choose Flat, Growth or Schedule. The default factor is 1. Leave the Digital spend source selected; no relinking is necessary. Recalculate to refresh Numbers.

## Validation

Four dedicated Python tests exercise Flat (including zero), Growth, Schedule, monthly/quarterly/yearly paths, Step/Smooth resolution, entered/linked bases, intra-quarter variable source spend, additive source allocations and invalid multipliers. All quarterly costs match the sum of monthly costs. Seven acquisition-spend tests, 62 fee-suite checks, 71 cost-recovery checks, four product-formula tests and the cost-control UI harness pass. Browser tests exercise adding a multiplier, Flat/Growth/Schedule switching, schedule paste/load, adding/removing sources without losing the multiplier or entered path, allocation editing and wide/narrow source layout. The rendered cost panel was inspected.

The broad legacy growth-UI extraction harness reports 73 passes and 11 failures from missing swControl stubs; the same 11 failures reproduce on unchanged r462. Actual full-page browser checks pass.
