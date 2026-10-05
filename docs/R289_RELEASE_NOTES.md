# r289 — Named balance components and presentation-first capital inputs

Built directly on r288 (Claude 8701c604a5252862e6ac9374b742c9ae6730041c). Full main history is retained; no merge or alternate lineage is required.

## Interest-bearing balances

New authoring starts with an empty list of user-named balance components, rather than four engagement-specific categories. Components choose their accounting treatment: an allocation within bank cash, remaining bank cash, a separate on-book earning asset, or an off-book administered balance. An allocation within cash does not create another asset. An administered balance creates neither bank assets nor deposit liabilities.

Balances use a sum of terms. Each term is a monetary stock multiplied by dimensionless assumptions, or a count multiplied by a dollars-per-unit assumption and optional dimensionless assumptions. Entered assumptions reuse Flat / Growth / Explicit series and the existing paste controller. Shared inputs have stable IDs and may be reused by multiple components. Sources include entered series, canonical fee-product counts/balance quantities, customer-acquisition counts, prior equity or assets, and prior/current deposits. Monetary flows cannot masquerade as outstanding stocks. Current equity/assets cannot feed their own earnings. Only one component can own remaining cash.

Income and optional cost use an annual rate and an explicitly selected current-end, prior-end or average balance, divided once by periods per year. Non-residual components can post income to interest or fees and costs to interest expense or operating expense. Opening stocks and separate balance/interest start periods are explicit. On-book components carry configurable standardized risk weights; off-book administered balances carry no bank-asset RWA. Component additions start at zero.

Example: 10 customers × 50% participation × $20,000 per customer = $100,000 administered balance. At 12% annual yield, end-balance monthly income is $1,000. With zero opening balance and average-balance pricing, the first month's income is $500, then $1,000 at a constant balance. These are illustrative test values, not client assumptions.

### Existing engagements and frozen runs

Existing `interest_balance_model` configurations retain their original engine and series names. Rendering or importing does not adopt the new model. The compatibility editor uses neutral labels, and offers **Use named components**. This explicitly copies the saved operands into components and shared assumptions; no re-entry is necessary. It disables, but preserves, the original configuration. **Restore original setup** reverses that choice.

Unchanged configurations retain complete results and frozen fingerprints. Explicit adoption adds named component output/audit series and changes the configuration and run fingerprints; it is not fingerprint-identical even where financial calculations reconcile exactly. Capture a new run after choosing to adopt. Custom component modifications are not copied back into the legacy configuration on restoration.

The Calculation Audit gains a **Balance Components** sheet only for the new model: ending balances, price balances, annual yield and cost rate, and posted income/cost, with stable IDs. Exact engine amounts are converted to $000s once. All Series also includes the component output. The Balance Sheet and Excel exhibit show separate earning assets; Income Statement interest detail shows user-named components.

### Supported boundaries

Profile A only. Stock schedules must be representable at the model cadence; a finer stock path is not silently added or averaged. Supported bank sources are explicitly whitelisted, rather than arbitrary result-row references. Remaining cash earns interest only; independently sourced components can carry costs/fees. Inputs are nonnegative, rates annual, and risk weights range from 0% to 250%. This is a typed sum-of-products grammar, not an Excel evaluator. Component outputs are audited but are not new upstream OpEx/fee-catalog sources in this release.

## Pre-opening expenses and fixed assets

**Add one manually** and **Paste from spreadsheet** sit at the top of the expanded pre-opening card, including while pasting and when the list is empty. Existing Replace / Append / Clear / Close mechanics are retained.

Expenses and scheduled assets appear as readable tables with named rows and totals. Selecting a row reveals its existing input controls immediately below it; compact amount fields replace the old sprawling authoring rows. Remove actions remain available per row. Asset rows show cost, in-service period and useful life. The Formula / level asset editor separately delineates **Opening position**, **Balance derivation** and **Depreciation**. Asset modes, assumptions and accounting calculations are unchanged.

The r288 theme, top menus and collapsed-on-arrival Securities sections remain. Browser verification covers 1920, 1440, 1366 and 1024 pixel viewports; previews included in the delivery are actual Chromium screenshots of this code.
