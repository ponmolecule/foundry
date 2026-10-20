# Foundry r366

Direct parent: r365 / 4860862.

Customer-linked lending now accepts a reusable shared amount plus independent percentage factors, rather than requiring users to paste a precomputed average. Reuses the existing typed shared-assumption registry without activating balance components. Adds a closed weighted-amount equation with any number of user-named component amounts and weights; each amount, weight and product factor has its own existing Flat/Growth/Explicit Series path. No TPV, practice-size, source-model rate or engagement-specific logic is built into the implementation.

In Balance authoring choose Customer count × average lending per customer. In Balance, change Average lending per customer to Shared assumption × factors; select an existing amount or create a New weighted assumption. Expand Edit shared assumption to enter its name, time-basis description and component amount/weight paths. Add product Percentage factors separately. Dollar inputs are plain dollars; percentage inputs are normal percentages. Amount time basis is descriptive and does not periodize the amount.

Results include granular calculation previews and a Lending Assumptions audit sheet. Units, monthly share totals, negative/nonfinite values, missing IDs, duplicate IDs and cycles fail closed. Renaming preserves stable references; in-use assumptions cannot be deleted. Legacy adoption preserves registry-only inputs. Existing entered mode remains available; no saved amounts are guessed or rescaled.

Verification: six engine regressions cover source-equivalent four-segment account recurrence/balances/interest/credit, live changes to constituent amounts and product factors, shared reuse by another loan and existing balance components, renaming, monthly-to-quarterly level resolution, invalid future-period weights, invalid references/units/cycles/values, and public/audit details. Actual UI-handler checks cover dollar/percentage entry, components, product factors, rename and deletion safety, legacy adoption, mode restoration and all inline-script syntax. Existing linked-loan, balance-components and r360 stream-output suites pass. Legacy r365 monthly and quarterly financials, product results and config hashes compare exactly unchanged. Browser pixel verification unavailable.

Packaged for user deployment; not deployed. See docs/shared_lending_assumptions.md for semantics and aggregation boundaries.
