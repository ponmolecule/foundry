# r500: Stress testing, scenario design

Built on Claude r499 (4e479ce). Implements r500 of the shared release plan with GPT's amendments: scenario classes and coverage, calibration records, combined scenarios from frozen parts, a parallel shift of the reference rate path judged in both directions, and the delay operation.

## Engine and calculations

Base calculations and results are unchanged; no base output differs from r499. The rate shift uses the engine's existing parallel rate-shock overlay on the stressed copy only (`scenario_overlays.rate_shock_bp`), so it is exactly the shock the standard pack already applies. The delay operation rewrites an entered path on the stressed copy, like the r498 operations.

## Scenario classes and coverage

- Classes: Macroeconomic, Idiosyncratic, Combined, Sensitivity, Method comparison (r498 "Economic" scenarios show as Unclassified until a class is chosen).
- Scenarios shows a coverage panel (macroeconomic, idiosyncratic, combined) and design warnings:
  - a macroeconomic scenario that stresses rates without a credit change;
  - an idiosyncratic scenario that changes an input the macroeconomic scenario already changes;
  - a combined scenario whose parts changed after freezing;
  - incomplete calibration records.
- Scenarios are listed by class.

## Combined scenarios

"Build a combined scenario" picks a macroeconomic and an idiosyncratic part. Each part's changes are copied and frozen with its version; every change remembers its part. Composition rule: two parts may not change the same input over overlapping periods. That is a conflict to resolve, never summed or overwritten. If a part is edited later, the Builder says so and offers "Refreeze parts"; until then the frozen copy runs unchanged.

## Calibration records

Every change carries rationale, data source, data period, applicability and approval (draft, reviewed, approved). Missing rationale or source is a warning, not an error. Records travel with the run and appear in the export (Stress Overrides sheet).

## Rate path

- "Reference rate path, parallel shift" in basis points, whole horizon (a partial window is not available yet and is rejected by name).
- Floating products reprice through their index and spread; cash, securities and borrowing yields move; fixed-rate contracts keep their rates. The Builder lists which products reprice and which do not.
- The mirrored shift runs too. Results show "Which rate direction hurts" for net income and lowest Tier 1 leverage over the window. When earnings and capital disagree, both are shown. Exported as Stress Rate Direction.

## Delay

- Available for entered paths only (single values cannot be delayed). The path moves later by N periods from a chosen period and runs to the horizon.
- Vacated periods are zero for a flow and held at the prior level for a level path.
- Values pushed past the horizon are dropped and disclosed (amount, for flows).
- Committed costs do not move; associated costs move only through existing links.
- Delay is not a reduction in volume; the shifted path is tested to equal the base path moved later.

Macro indicators (unemployment, BBB spread) still do not become loss-rate changes without an explicit calibration; that mapping is not built.

## Validation

- `foundry/v2/tests_r500_scenario_design.py`: 34 checks pass (rate shift equals the engine's own shock exactly, both directions and per-measure adverse, exposure, rate validation, delay arithmetic and disclosure, delay validation, classes, calibration, coverage warnings, combined from frozen parts, conflict, part staleness, combined run with attribution reconciled, export, endpoint).
- `web/tests_r500_scenario_design_ui.cjs` passes; r498 and r499 stress tests still pass.
- Browser walkthrough: macroeconomic (−200 bp plus CRE charge-offs ×2.5), idiosyncratic (six-month delay), combined, run and reviewed.
