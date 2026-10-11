# r314 — Customer activity, account adoption and account costs

Direct continuation of r313 (`900890f1fd9069d541eefeb5c89bd4dfb7cdeac1`). Release 1 only. No new product family, repayment engine, commitment state or gross-up policy.

## Optional capabilities

- Customer acquisition can publish stable, linkable count flows for gross new customers and customer losses, for the feed and each channel. Channels use proportional attrition of their attributed customer stock. Enter channel opening customers to attribute the opening book; unallocated opening customers remain in the aggregate only.
- Shared account adoption sources live under Customer acquisition. They reference the existing feed by stable customer-count ID, and publish active subscribers, additions, cancellations/closures and customer exits. These sources do not post income or costs.
- **Target share** sets subscribers to share × ending customers. Exits follow customer attrition proportionally. Positive / negative reconciliations publish additions / cancellations. These are inferred flows, not observed gross openings or simultaneous openings and closures.
- **Gross flows** takes new-customer adoption, surviving existing non-holder adoption and subscriber closure probabilities. Customer exits happen first, then closures on surviving beginning subscribers. Existing non-holder adoption excludes accounts closed in that month; newly acquired customers have their own take-up probability. One subscriber per customer is the supported population contract.
- Both methods require explicit opening subscribers and the proportional-customer-attrition assumption. Methods cannot be combined. Impossible or nonfinite populations are rejected, rather than clipped.
- Probabilities carry Month / Quarter / Year units and compound to monthly equivalents. An annual 12% closure probability becomes `1-(1-.12)^(1/12)` per month. Adoption shares are levels and are never divided or compounded.
- Account fee streams support an optional participation-share path, plus **Cost per account** with an explicit billing period. $10/account/month becomes $30/account/quarter. Account prices/costs and downstream quantity chains calculate monthly before quarterly aggregation. This avoids multiplying quarterly averages by a sampled monthly price.
- Origination/acquisition event costs can consume additions on Transaction basis with dollars per event. Operating Expense formulas can also consume the count flows, retaining the existing gross-up treatment. Publish or post a cost only once: CAC's spend remains observational, not an automatic expense.
- New audit sheets: **Account Activity** (native-period source values) and **Adoption Monthly** (opening + additions − closures − customer exits = ending). Fee Stream Economics retains pricing/cost diagnostics and correct dollar units for account costs.

## Entry points

1. Configuration → Customer acquisition → an existing feed → **Publish customer flows** and/or **+ Account adoption**.
2. Set method, opening subscribers and paths. The exit and no-reopening assumptions appear beside the controls.
3. Fee Product → stream → **Account** for subscriber levels, or **Transaction** for additions/losses → Driver source **Customer flows / account adoption** → choose the stable source.
4. For recurring servicing, choose **Cost per account**, set billing period and cost path. For onboarding, link additions and use cost per unit. A quantity-only driver has zero price and no costs.
5. Operating Expense → Formula → Browse / search → the new count flow, multiplied by an entered dollar cost per event. This continues to enter that engagement's configured gross-up base.

## Compatibility and boundaries

Absent opt-in settings preserve legacy complete outputs and fingerprints. Existing engagements are not migrated, existing templates gain no adoption assumptions, and no costs are turned on automatically. Stable IDs survive display-name changes and reordering. The deployment bundle continues `main` from r313.

The current flow-based lending average-days balance approximation is unchanged. Purchase cohorts, actual repayments, loss/allowance profile changes and commitments remain separate work.

CAC straight-line display paths contain implied losses; they cannot be published as gross activity. Use CAC monthly flows for these sources. Account activity fee chains require canonical monthly operands; unsupported current bank aggregates, legacy model-period schedules, revenue ramps and incompatible stock/flow links fail closed. Profile B can observe activity flows in Operating Expense; the new fee capabilities require Profile A's fee-stream engine.

Guide Me's existing fee-only schema/materializer stays intact. It does not yet author the shared adoption sources or per-account cost kind. Use the explicit controls above for these new features; existing Guide Me mappings continue to work.
