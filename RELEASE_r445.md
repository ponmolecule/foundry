# r445 — Consistent product controls and provision inspection

Built on r444 (6aad32b3).

Product setup: native funded-flow fields now use the same 150px label column, fitted controls, compact segments and field spacing as loan-production, basic roll-forward, deposit and fee/exposure editors. Managed yield and credit-factor Series use their local field labels. Responsive labels wrap rather than overlap. Nested repayment-profile labels retain their consistent local layout.

Section placement: basic roll-forward runoff is under Structure & timing, matching other repayment controls. Funded-flow Interest accrues on is under Pricing, matching interest-balance controls on other lending paths. All lending methods keep the same six sidebar sections; method-specific mechanics remain intact. Existing handlers and saved assumptions are unchanged.

Reporting: publish provision and target allowance for lending paths that omitted those product series. Provision uses the engine allowance ledger identity (ending minus beginning allowance plus charge-offs); fair-value products have no allowance provision. Contract-authored target/provision values are retained. Existing Numbers views automatically expose the added values, including unrounded diagnostic series. No financial calculation changes.

Validation: all 273 modules pass. Browser coverage traverses every fixture product's setup sections, checks stable lending navigation and field alignment, verifies no render-time config mutation, inspects responsive pricing layouts at 2048/1440/1100px, and opens the actual Numbers dialog to verify provision access. Provision tests cover contracts, legacy and repayment-profile lending at monthly/quarterly cadences. All financial fingerprints remain unchanged.

Complete-result pins move only for the new reporting fields: core 670ae7ca4342 -> a4e10638df79, universal 85bcf524cf2c -> c4cad373c1a3, explicit-FDIC core 7c01eeede6ff -> 39ca913ffca3. The r434 layout test now expects the two origination fields in Balance because runoff moved to Structure & timing; label-alignment checks remain.
