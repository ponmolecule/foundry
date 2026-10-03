# r269 — Cross-product fee quantity links

Built on r268 (`66835a5c00f3af3eae3df50ec78a4cedd7a604e5`). No unrelated redesign.

## Authoring

On a Fee Product's balance, transaction or account stream, select **Driver source → Linked stream quantity — across fee products**, then **Source quantity**. The picker identifies the owning product and stream. Choose the coefficient/share and pricing/cost rules on the consuming stream. A quantity link does not copy source revenue or source costs.

The source receives a stable quantity ID when selected. Renaming or moving either card does not change the link. Existing same-card “Another stream” name references remain supported. Balance consumers accept balance stocks; account consumers accept account counts. Transaction consumers use compatible quantities with the existing coefficient mechanics. Flat/event streams have no quantity to link.

Derived monetary quantities are also available to existing deposit-pool and funded-flow lending source selectors. This release adds the new driver to Fee Products; it does not add that driver to deposit/lending fee-stream editors.

Missing/deleted sources, duplicate IDs, incompatible bases and circular dependencies fail validation. Preview waits for a source selection when switching to the new driver.

## Calculation

Fee quantities are evaluated in stream dependency order across all Fee Products, after their own balance contexts are prepared and before downstream deposit pools consume the quantities. A chain can revisit an earlier owner if the stream graph is acyclic. Income and costs post once to their respective owners.

At quarterly cadence, direct entered monthly monetary flow multiplied by a monthly share is calculated as the sum of monthly products, not the product of quarterly aggregates. Unsupported finer schedules continue to fail closed; this release is not a general monthly reconstruction of arbitrary derived quarterly flows.

Configurations without the new driver retain the legacy evaluator. The three pinned financial run fingerprints remain unchanged.

## Verification

- Cross-product quantity/posting, reverse owner order, rename/reorder and true A → B → A stream DAG.
- Missing source, duplicate ID, cycle and stock/flow rejection.
- Quarterly sum of monthly products and inactive-source timing.
- Deposit-pool consumption and audit monetary units/workbook generation.
- JavaScript selector tests and native Chromium selection using the production picker handler.
- All inline console scripts compile.
- Full Python module sweep compared to r268; see delivery VALIDATION.md for counts and baseline failures.

Use this delivery with the existing deployment script. The bundle's main ref points to this release and includes r268 in its ancestry. This is a build for deployment by the user, not an already deployed service.
