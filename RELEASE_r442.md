# r442 — Label repayment-profile loss rates locally

Built on r441 (e273c320). Presentation only; no engine or calculation changes.

The repayment-profile loss-rate Series now owns a dedicated field row. The field-system decorator no longer lifts Annual loss rate to the top of the entire Monthly repayment cohorts panel. Annual loss rate (or Lifetime loss at funding) stays beside the relevant controls below the loss-exposure selector. The numeric input has the matching accessible name.

Validation: new browser regression checks local label placement, single label, editing 4% stores 0.04, unchanged configuration on redraw, and lifetime-basis naming. Five existing repayment-profile, field-layout, space, r440 and r441 regressions pass.
