# Foundry r370

Previous release: r369 / 2fe46c7. Replacement package for the pre-deployment layout review; includes all r369 lending capabilities. Financial calculations are unchanged.

The opt-in loan-production editor now uses scoped, aligned field grids within the existing lending sections. Origination source, amounts, repayment rates, allowance policy and deferred-cost controls retain consistent labels, widths and spacing. Narrow layouts use one column. Calculation explanations, opening allowance, origination fees and opening deferred balance use compact native disclosures, preserving their open state across rerenders. The inherited flexible-label behavior is overridden locally so labels and selectors cannot drift vertically when a neighboring schedule expands. The production summary identifies separate repayment rates rather than the inactive legacy runoff scalar.

Verification: 35 real Chromium layout cases across 1920, 1440, 1280, 1024 and 768 pixels, covering Flat, Growth, Explicit, an open schedule editor and expanded secondary settings, monetary funding, deferred-cost off, and the original loan-mechanics selection. Automated checks cover control containment, control overlap, stretched labels, page overflow, runtime errors and disclosure state across rerender. Flat and expanded screenshots visually inspected. Existing r369 editor, product layout, flow-lending and numeric inspector regressions pass; inline console syntax and whitespace checks pass.

No changes to financial engines, configuration values, stored numeric precision or posting behavior. Packaged; not deployed. Deploy this delivery instead of the previous r369 ZIP.
