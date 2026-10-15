# r331 — entered liability levels and posting guidance

Built on r330 commit 2121f728908845b6ed2e37b67d1fbc4cb06327b0. No engagement data is included.

Named Other liabilities formula terms now accept entered Flat/Growth/Explicit stock schedules as well as existing workforce and fixed-asset links. New components default to an entered zero balance and multiplier one, with no automatic workforce assumption. Existing stored terms, base balances and revenue-linked settlement liabilities are preserved. Explicit monthly stocks use quarter-end observations in quarterly runs. Entered driver, multiplier, contribution and named component subtotal are available in the calculation audit; FIW also exposes entered schedules with monetary units.

Securities & AOCI sections now have concise posting footers describing balance-sheet treatment, income effects and funding effects. These are descriptive UI text, not additional accounting postings. They do not infer engagement-specific embedding of depreciation in G&A.

## Entry
Other liabilities → Formula / level → + Add liability component. Name the component, leave Source at Entered level, choose Explicit and monthly cadence, paste period-end liability values in $000s, Load (replace). Keep multiplier Flat 1. Do not duplicate balances already in the base or settlement components. Opening balance remains the aggregate opening base position plus separately configured settlement opening balances; no new per-component opening field is introduced.

## Scope
No new product types, income or expense posting, source-specific constants or automatic migration. Existing linked mode remains available. This release does not change the net-PP&E authoring workaround or invent gross/accumulated depreciation balances. No production deployment or push was performed.
