# Foundry r367

Parent: r366 / 7961bf6.

Fixed lending yield now uses the existing Flat/Growth/Explicit Series editor in both standard and funded-flow lending Setup. Explicit schedules accept pasted percentages with Month/Quarter/Year cadence, Step/Smooth resolution and last-value extension. Rates are annualized levels, not period totals. Editing the path initializes from the existing scalar yield; unchanged legacy products retain scalar behavior. Floating pricing ignores the inactive fixed path. Both engine profiles resolve the new path, and per-period yield overrides apply last. Override cells indicate the schedule baseline rather than implying the old scalar applies. Pricing summaries disclose an authored trajectory.

Verification: four regressions cover monthly boundaries, yearly schedules, override precedence, public results, quarterly profile B, growth, invalid rates, floating gating and unchanged scalar defaults. Actual UI handlers confirm five-value percentage paste, initialization from saved yield and last-value extension. Existing flow-lending renderer, shared-lending and customer-linked balance suites pass. Full console syntax and whitespace checks pass. No browser visual QA available.

To enter Receivable Advances: Setup → Pricing → Fixed yield → Explicit → Year. Paste 11, 10.7, 10.4, 10.4, 10.4 and Load (replace). Leave yield overrides blank unless an intentional exception is needed.

Packaged; not deployed.
