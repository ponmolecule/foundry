# Named balance component authoring

Use Configuration → Securities & AOCI → Interest-bearing balances. Add a component, name it, and choose its accounting treatment. Separate on-book assets consume funding once; a part-of-cash allocation is a suballocation of existing bank cash; off-book balances never become bank assets.

## A derived stock with an offset
Add a monetary term linked to completed current-period deposits and multiply by an entered multiplier. Add another term linked to the relevant lending product(s), selecting Subtract for each. Select Floor calculated balance at zero only when the economic rule explicitly requires it. Select Current period end if that is the intended interest basis. Use the existing index plus spread or entered yield schedule.

## Annual closing targets
For a balance source choose Enter → Explicit → Year; load the annual target balances. Enable Values are year-end balance targets, choose Ramp to each year end or Full target throughout year, select the year anchor, and state the prior year-end target. Opening component balance is the actual pre-period-1 booked stock; the prior year-end target is the ramp's reference point. They are separate inputs, particularly for a midyear launch.

## Independent income
For a separate asset or off-book component choose Income calculation:
- Yield on modeled balance: normal current/prior/average basis × annual yield.
- Yield on a separate balance basis: enter/link the intended balance for pricing; this input does not book another asset. Costs still price the modeled balance measure.
- Entered income amount: enter Flat/Growth/Explicit income and choose its amount period. An annual amount is divided by 12 in a monthly model or 4 in a quarterly model. No asset-yield multiplication occurs. Annual yield is retained but unused in this mode.

Cash allocations/residual cash use yield on the modeled allocation. For every method, Income begins is explicit and income posts once to the selected destination.

## Validate
In the audit workbook inspect Balance Components for ending stock, pricing stock, independent income basis/amount (where selected), rate and income posted. Review the balance sheet earning asset aggregate and bank cash together: changing asset allocation must consume funding once, not create free assets. Comparisons with another model require matching rate paths and all upstream deposits/lending/expenses; these controls alone do not reconcile an engagement.
