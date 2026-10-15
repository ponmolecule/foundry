# Tax blocks — authoring and calculation contract

Use Config → Income taxes → Externally determined tax. The prior Sources and Derived rules are retained.

1. Loss carryforward: choose taxable income before losses, an entered pre-forecast loss stock (or configured opening NOL), the existing utilization limit and existing tax rate. Preview and Apply. Leave the provision checkbox off if another downstream block will determine the posting.
2. Credit limitation: select the loss block's Tax before credits, the entered period threshold, the retained share above it, and the explicit threshold treatment. Preview and Apply.
3. Entity allocation: select tax after credit, participating entity income sources and receiving entity; choose positive or signed income. Check Use this block's tax result as the current provision when this is the final posting result. Preview and Apply.

Existing signed income and adjustments can be composed through the retained derived rules; blocks consume those existing series directly. Sources and schedules are never pasted again merely to use a block. Amount-period conversion remains on monetary flow inputs; an opening stock is not divided by cadence. Existing configured tax-rate, utilization-limit precedence, and opening-NOL references remain available. A bank opening loss is not silently substituted for a separate group's opening loss.

## Formulas

For signed taxable income I, available losses L, utilization fraction u, rate r:

- L is prior committed closing losses, with the selected pre-forecast opening stock in period 1.
- Positive income P = max(0,I); new losses N = max(0,-I).
- Used losses U = min(L, P × u).
- Closing losses = L + N − U; taxable income after losses = P − U.
- Tax before credits = (P − U) × r.

This is a per-engine-period method. Monthly calculations run in monthly engagements. It does not silently emulate monthly nonlinear loss usage inside a quarterly run or the calculated mode's statutory tax-year policies. Rates u and r must be between 0 and 1; opening losses cannot be negative.

For nonnegative gross tax G, nonnegative period threshold T and retained fraction s in [0,1]:

- Fully credited threshold: net tax = max(0,G−T) × s.
- Fully retained threshold: net tax = G − max(0,G−T) × (1−s).
- Credit applied = G − net tax.

The threshold's annual/monthly conversion is supplied by its monetary input, not hidden in the block. Neither policy is automatically selected. These are mathematical policies, not a claim that a specific statutory credit applies.

Allocation: choose entity incomes e_i. Positive method weights max(0,e_i); signed method weights e_i. Share is selected receiving weight / total weight, zero when the denominator is zero. Allocated amount is the incoming amount × share. Other entities' income is used as a basis and is not posted as bank income.

## Implementation and audit

The server planner foundry/v2/tax_blocks.py returns an isolated configuration using the pre-existing expression grammar. Stored blocks contain their explicit source bindings and generated/reused rule IDs. The runtime still uses ExternalTaxLedger; block metadata adds range contracts, not a second provision path. All generated operations and operands appear on Income Taxes through the existing audit mechanism, in the existing money/scalar units.

Editing a block preserves entered data and standalone rules; referenced generated IDs cannot vanish silently. Current-period cycles are rejected; lagged recurrence reads committed history only. Existing standalone rules are never automatically pruned, including zero placeholders. Generated rules are shown read-only under Advanced; edit their block instead. Direct manual changes to reused standalone rules can affect consuming blocks, like any other source edit.

Recognition and payment policy remain separate: no DTA is inferred merely because a loss pool exists, and a provision does not establish the correct payment date. Finish and validate those settings before drawing a balance-sheet conclusion.
