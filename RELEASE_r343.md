# Foundry r343

Extends the existing FTEs × productivity acquisition method with a separate dimensionless Productivity multiplier. Parent: r342 / 8de4d85.

New customers = linked or entered FTE count × base customers per FTE × productivity multiplier.

The multiplier defaults to 100%, supports the existing Flat/Growth/Explicit authoring controls, and is a level: a 50% assumption remains 50% regardless of source or model cadence. It is not divided by 12. Values above 100% are permitted; negative and nonfinite values fail validation. Compensation used for the CAC memo remains workforce × compensation, independent of the productivity multiplier. Customer counts remain fractional; no rounding was added.

Existing configurations without the multiplier preserve their existing monthly outputs and audit operands. Monthly acquisition audit adds a separate multiplier column, showing 100% for an unmodified FTE channel.

For the confirmed source equation, keep Acquisition FTE count linked to Workforce Count · Sales Team; enter base New customers / FTE as 2.75 Per month; author the source ramp percentages separately under Productivity multiplier. The source label says daily, but its displayed monthly acquisition formula contains no days multiplier. Actual ramp percentages remain to be provided; no engagement-specific values were inserted into engine logic.

Validated live workforce changes with independently authored base productivity and ramp; Flat/Growth/Explicit and month/quarter level semantics; monthly/quarterly equivalence; 100% default identity; invalid-value rejection; public engine and audit agreement. CAC UI 36 checks, CAC shapeshifter 61 checks, intra-period 63 checks, account activity 33 checks, linked lending and r342 portfolio-paydown checks passed. Packaged for the usual Git-bundle deployment; not deployed.
