# Foundry r359

Direct parent: r358 / 27f948da4ef6f37902af128c9afc4e2798275898.

## Linked Flat and Derived semantics

A linked Flat driver follows the upstream quantity unchanged each period; it does not freeze the first observation. Derived applies an authored share or multiplier to that source quantity. Flat and Derived with a 100% dimensionless share produce the same quantity and fee revenue when other settings match. Pricing remains a separate operation. For example, a network assessment can follow purchase volume unchanged and apply 0.14% under Pricing.

The existing trajectory-change handler removes active derived coefficients when the user selects another trajectory. Switching a 60% share to Flat therefore changes the quantity to 100% of the source; switching an amount-per-account conversion to Flat removes that conversion. The change is real authored economics, not an engine rounding bug. Linked Flat is now labeled Follows source unchanged (100%), with an inline explanation that quantity scaling uses Derived and the fee rate belongs under Pricing. Saved values and engine arithmetic are unchanged.

## Stream display sweep

The r358 compact result preview, stream list and right-hand chart all read the stream's own engine-resolved quantity by stable quantity Series ID. The matching purchase, interchange and network quantities in the screenshots are expected because pricing rates are applied after the volume driver. These Activity outputs show quantities, not the resulting fee income. Product fees in the chart footer are explicitly labeled product totals.

The sweep found a narrower, confirmed defect: the chart's local unit heuristic did not follow linked monetary quantities or amount-per-source coefficients, so monetary values appeared as raw dollars labeled units. Charts now reuse the same count/money/native classifier as compact previews: monetary quantities convert once to $000s; counts retain fractional FTE/customer/account values. Lending fee-summary chips also use that contract instead of dividing every quantity by 1000. Provenance/list classification now follows links across fee-product, lending and deposit owners and recognizes account-activity counts. Result values use six significant digits consistently; explicit source/provenance descriptions remain clearly identified as source descriptions.

No chart was changed to display fee income in place of activity volume. No additional source-number previews were added.

## Verification

Two engine tests prove Flat follows each period, Flat equals Derived 100%, a 60% share scales quantity before pricing, and an authored coefficient with a non-Derived trajectory is rejected. Node checks execute actual right-hand chart and lending chip renderers for purchase/interchange/network, fractional counts, shared units, and the actual trajectory-change handler. r358 compact result regression, stream figure refresh, loan/deposit stream checks (9) and r355 retained source-preview checks (23) pass. Full inline-script syntax and whitespace checks pass. Browser pixel/layout verification was unavailable.

Packaged for user deployment; not deployed.
