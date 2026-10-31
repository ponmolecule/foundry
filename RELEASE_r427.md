# r427 — Spend/CAC effectiveness multiplier

Built on r426 (c2c8b70). Spend ÷ CAC channels gain an Effectiveness multiplier below Cost per customer acquired, using the standard percent Flat / Growth / Explicit controls and natural source cadence. The formula displayed is New customers = Spend ÷ CAC × Effectiveness multiplier. It applies to any channel using this method, without engagement/channel-name rules.

The dimensionless path resolves monthly before the acquisition equation, then existing aggregation, attrition and downstream customer links continue normally. Acquisition spend remains the full authored amount. Implied CAC is actual spend divided by resulting acquisitions. Default when absent is 100%; legacy channels do not gain a new result operand until the optional path is authored. Values must be finite and nonnegative; 0% produces no acquisitions without zeroing spend. Values above 100% are allowed as improved effectiveness, consistent with the productivity multiplier. Other acquisition methods ignore this reserved setting.

The public monthly operand audit exposes the applied factor, and the calculation workbook includes a separate Effectiveness multiplier column. The Index explains the revised equation. No save mechanism changes or client data are included.

Validation:
- Five new Python tests: missing/unity identity, full monthly digital ramp, unchanged $21,624 spend, M1 3.468 acquisitions at $265 CAC and 4.25%, monthly/quarterly equivalence, Flat/Growth/Explicit quarter/month paths, zero and above-100% factors, invalid factors, public output/validation and workbook audit.
- New UI harness: percent control, default 100%, saved value preservation and displayed equation.
- Existing productivity multiplier tests pass; CAC shapeshifter 61/61, CAC UI 37/37 (expected new driver updated), Series architecture 40/40, acquisition channel links, acquisition Numbers harness and all inline/generated JavaScript syntax checks pass.
- Core bank, universal template bank and legacy linked-stream fixture full public outputs are identical to r426.
- No real-browser visual check was available. The existing form layout and existing path editors are reused.

Enter the effectiveness ramp in ordinary percentage values, not decimals: 4.25, 14, 27.5, 42.5, 62, 75, 100. An Explicit monthly path must repeat each value for the intended number of months; a quarterly path repeats each factor through the quarter. Spending stays 21.624 $000s/month and base CAC stays $265/customer.

Delivery ZIP uses delivery/foundry-full.bundle to match the deployment script. Verify BUILD_STAMP = foundry-r427-acquisition-effectiveness after import.
