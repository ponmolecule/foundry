# Live loan production and deferred origination fees/costs

Available in Profile A, monthly or quarterly, opt-in under Lending → Balance → Production & repayment method → Live production + balance-based repayment. Existing saved products retain their original calculations until selected. Profile B rejects this contract explicitly.

## Authoring

Keep Balance authoring at Loan roll-forward and Measurement at Amortized cost. Origination sources are an entered new-loan count, a published Customer Acquisition gross-new-customer flow, or entered monetary originations. Loan-count sources multiply a separately authored dollars-per-new-loan Series. Counts are flows, never changes in active balances. Existing CAC pool-conversion channels can apply take-up before the loan consumes the feed; no Account adoption object is required.

Entered amounts/counts are totals per **model period**. A yearly schedule selects the per-model-period value for each year, rather than an annual total to spread. Quarterly runs aggregate linked gross monthly counts, then apply the loan recurrence once per quarter; they are not a reconstruction of monthly interest/runoff. Use monthly modeling for monthly source reconciliation. A finer-than-model entered level schedule fails closed through the shared Series resolver.

All new schedules reuse Flat/Growth/Explicit, schedule paste, cadence, and Step/Smooth controls. Rates are annual percentages. Loan amounts and per-loan costs/fees are plain dollars; opening loan, allowance and deferred balances are $000s in the UI. Explicit paths hold their last value under the shared Series editor's existing convention.

## Principal

For native period t and periods/year p:

- Funding = new-loan count × loan amount, or entered funded dollars.
- Principal payments = beginning principal × annual payment rate / p.
- Prepayments = beginning principal × annual prepayment rate / p.
- Charge-offs = beginning principal × annual loss rate / p (positive loss magnitude).
- Ending principal = beginning + funded − payments − prepayments − charge-offs.

New funding starts repayment next period. This is a beginning-balance-rate model, **not** a constant-payment loan schedule. It has no automatic maturity balloon. Legacy term/maturity and runoff scalars do not govern this explicitly selected method. Conflicting legacy production/runoff overrides fail closed. Mortgage sales, shared caps, repayment curves, fair value and alternative allowance modes are rejected rather than silently combined.

## Deferred fees/costs

Under Costs & accounting, enable Deferred origination fees & costs. Select dollars per new loan or percent of funded amount. Enter costs, fees and an independent common cost/fee multiplier (for example a source inflation factor); monetary-only production requires the percent-funded basis. Opening net cost may be negative for net deferred fees.

- Costs added = source operand × cost Series × multiplier.
- Fees added = source operand × fee Series × multiplier.
- Scheduled amortization = beginning signed net cost × annual amortization rate / p.
- Prepayment catch-up = beginning signed net cost × annual catch-up rate / p.
- Ending net cost = beginning net cost + costs − fees − amortization − catch-up.
- Carrying amount = ending principal + ending signed net cost.
- Gross contractual interest = average beginning/ending principal × annual yield / p.
- Net interest = gross contractual interest − amortization − catch-up.

Costs therefore reduce interest through amortization; net fees increase it. This is explicitly balance-rate amortization, **not an effective-interest-yield calculation** or a claim of accounting-policy compliance for every loan portfolio. No charge-off-driven deferred-cost write-off is assumed. New deferrals start amortizing next period. Do not also enter the same origination cost as operating expense. Carrying amount enters gross loans, funding, reporting and capital calculations; principal remains a distinct result for source reconciliation.

## Allowance

Credit & allowance accepts an explicit opening allowance, a scheduled target share of ending **principal**, and a release policy. Allow releases is the default; Floor provision at zero is an explicit election.

- Target = ending principal × target rate.
- Required provision = target − beginning allowance + positive charge-offs.
- Provision = required provision, or max(required provision, 0) if elected.
- Ending allowance = beginning allowance − charge-offs + provision.

A zero target still requires provision to replenish charge-offs when beginning allowance is zero. A zero provision floor can leave allowance above target. It never reverses charge-off signs. Blank source spreadsheet cells must be deliberately represented as zeros when that is their confirmed arithmetic effect; Foundry does not infer missing economics.

## Inspection and integration

Discreet Numbers dialogs expose principal, production, count, repayments and carrying amount in Balance/Timing; gross/net interest and amortization in Pricing; target/actual allowance and provision in Credit; deferred additions, fees and balance in Costs. Exact diagnostic dollars are scaled once to $000s. New Loan Rollforward audit sheet uses the same unrounded base-engine results. No chart geometry or browser financial reconstruction is used.

Existing reserve and origination stress overlays apply to the opt-in target and live loan production; charge-off and yield overlays continue through the common rate dispatch. Origination volume haircuts also reduce count-driven deferred additions. Saved configuration is never mutated by calculation.

## Source reconciliation exceptions identified during design

The supplied three loan sections store charge-offs as negative values but subtract them in allowance roll-forwards; these signs must be reconciled against consistent allowance accounting. CRE's first three allowance-target cells are blank; Equipment's first four Direct CAC links are blank although the underlying costs are calculated. These are source/data questions, not implementation defaults.

The supplied interest formulas also pin particular rate columns: CRE references `$S54`, Equipment `$P93`, and Practice In/Out `$R133` in the displayed formulas. Confirm whether later cells retain those absolute-column references before reconciling a changing yield schedule. Foundry supports either a flat yield or a changing schedule; it does not decide which source intention is correct.
