# Foundry r356

Parent: deployed r355 / 616d6000feaf27b3cd8b0b9d7769f7a390caf88b.

Workforce now supports Customer capacity as a count method. Select an existing Customer Acquisition feed by its stable customer-count Series ID, then select Active customers (after attrition) or Cumulative acquired (opening customers plus gross new acquisitions, before attrition). Each month, required FTE is zero when the source is zero; otherwise max(source / customers per FTE, minimum FTE). Capacity and minimum use the existing Flat / Growth / Explicit editor. Fractional FTE is preserved; there is no rounding or engagement-specific constant.

Fixed start/end windows apply. Capacity staffing uses a fixed start window; metric-trigger activation cannot be combined with it. Per-FTE compensation consumes the calculated count. Total compensation retains its existing meaning and is not multiplied by count. Quarterly count is average monthly FTE, and payroll is the sum of monthly count × monthly compensation calculations. Existing entered count paths are retained when switching count method, and continue to work as before.

The live dependency can run from sales workforce through acquisition into another workforce role. Genuine circular dependencies, missing sources, nonpositive capacity, negative floors and nonfinite inputs fail explicitly. Account adoption is not needed or enabled.

Engine diagnostics include the source, capacity, floor, required monthly FTE, active monthly FTE and role payroll. The calculation audit adds Workforce Capacity Detail and reconciles capacity role payroll to the monthly calculations rather than multiplying independently averaged paths.

## Entry for the confirmed servicing rule

In Operating expense > Workforce, select the servicing population. Set Count method to Customer capacity, choose the acquisition feed containing Direct and EMR, and select Cumulative acquired · before attrition. Set Customers per FTE to Flat 40 and Minimum FTE while positive to Flat 1. Keep the intended start/end windows, compensation and benefits. Use Per FTE if compensation is per employee. This implements the supplied IF/MAX rule without ROUNDUP and keeps the sales headcount link live. No engagement data is automatically changed.

## Verification

Seven focused calculation/integration tests cover zero source, positive minimum, fractional counts, active/cumulative differences, opening populations, return to zero, explicit floors, live sales changes, source integrity, invalid values, circular links, exact quarterly payroll, original model-period throughput, both engines, public units and audit output. Node checks exercise the actual controls, preserved entered paths, missing sources, trigger conflict and full inline-script syntax.

Existing regressions: Series architecture 40; Workforce activation 22; Workforce additive components 14; CAC intra-period 63; CAC shapeshifter 61; r355 linked sources 26; r350 flow-lending UI 18; typed source catalog checks. All pass. Python compilation and Git diff whitespace checks pass. No browser pixel/layout verification was available in this environment.

Packaged for user deployment; not deployed. Delivery ZIP retains delivery/ with full Git bundle and release metadata.
