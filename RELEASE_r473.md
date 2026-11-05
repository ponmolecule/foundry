# r473 — Optional rounding for customer-capacity staffing

Based on r472. Adds a small Staffing rounding selector to the existing customer-capacity editor: No rounding (default) or Round up to whole FTE. No engagement-specific role, customer source, capacity or minimum is embedded in the implementation.

Each month retains the existing zero-customers → zero-FTE rule. Positive customer counts resolve max(customers / capacity, minimum FTE), followed by optional rounding up. Rounding is applied before active-window aggregation and monthly payroll; quarterly staffing remains the average of monthly results. The same rounded counts feed workforce links and downstream fixed-asset components. Invalid rounding settings fail closed.

Missing rounding preserves the previous fractional results exactly. No migration, automatic opt-in, or re-entry of existing inputs is required. Selecting Round up is an authored choice on each capacity-based workforce population. Total-basis compensation remains independent of headcount.

Verification: 26 unittest cases pass, including capacity boundaries, zero customers, fractional minimum, omitted versus explicit No rounding, invalid settings, monthly-to-quarterly aggregation, end-to-end fixed-asset consumption, existing capacity regressions and r458 frozen All-On output hashes. The Node capacity-editor checks verify selected defaults and opt-in rendering; inline scripts and borrowing checks pass. Reference coverage regenerated. Browser visuals remain unverified here.

A disposable reconstruction of the latest anonymized audit was tested with the agreed opening balances, technology refresh and servicing Round up. Gross assets match all 60 source months exactly. Raw accumulated depreciation, net assets and monthly depreciation match the pasted whole-dollar source values within $0.45. This test does not change the saved user model; the user must select Round up after deploying.
