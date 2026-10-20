# Foundry r360

Direct parent: r359 / 95c6b69bc1eb6cf610ad19ed7c278cff90db986a.

## Resolved stream outputs take priority

The design rule is about the dependency and the stream's output, not its name: a source primitive displays its own value; dependent streams display what they resolve to. A dependent count or volume driver displays its calculated count or volume after transformations. A priced revenue stream displays its actual reported fee income after pricing, and contra-revenue displays its signed reduction. A cost-only stream displays its actual expense. A stream with revenue and direct operating costs displays net stream income, with its own income and cost components in the chart. Revenue-share deductions already included in reported income are not deducted twice.

The compact preview, primary chart, stream-list Result column and lending summary now use one result contract keyed by the stable stream quantity Series ID. Per-stream financial results come from the existing engine-captured economics previously used for the audit workbook; they are newly published in the API as fee_stream_economics.series in native dollars. Presentation converts money once to $000s. Neither pricing nor dependency formulas are replayed in JavaScript. A missing financial result is unavailable, never replaced by parent/source volume or the product's aggregate fees. Quantity provenance remains accessible through the calculation inspection and audit, not as the primary result for a financial stream.

For the charge-card chain, purchase activity remains purchase volume, gross interchange shows interchange revenue, and network assessment shows its negative contra-revenue amount. Zero-priced count/volume drivers retain their resolved quantities. These are consequences of the general pricing/cost contract, with no special handling of names, rates or this engagement. Real zero postings outside a timing window are explicitly published by the observational capture; arithmetic is unchanged.

## Shared definition and selected-menu controls

Stream name, Income presentation and Basis are grouped in a bordered, lightly shaded Stream definition panel, labeled Shared across Activity, Pricing, Timing and Costs. The same controls and handlers remain mounted while tabs change. The duplicate inline remove link is removed; the existing toolbar Remove stream action remains.

Each selected menu has its own heading, short purpose description and controls below the shared definition. CSS retains the existing menu visibility mechanism; tab selection does not relocate or reconstruct the shared inputs. The compact resolved-output preview is outside the menu-specific sections so it remains available across all four menus. Shared definition notes are not swept into each menu's About these settings drawer. The definition grid collapses to one column at narrow widths.

## Verification

Three integration tests exercise actual engine calculation → public output → real compact/chart/list renderers for source counts, dependent shares/counts/volumes, revenue, signed contra-revenue, direct costs, net output, zero timing windows, quarterly totals, renamed products and loan/deposit owners. The tests verify no financial fallback to quantity and no input mutation during result rendering. Renderer checks verify the common definition is outside the Activity/Pricing/Timing/Costs sections, with original field handlers and distinct section headings.

Existing fee-stream economics audit (17), account activity (33), loan/deposit streams (9), flow-lending UI (18), retained linked-source previews (23), stream figure refresh, fee quantity links, r357 precision integration, workforce capacity (7), linked Flat/Derived semantics (2) and r358/r359 renderer regressions pass. Full inline-script syntax and whitespace checks pass. A direct r359→r360 comparison confirms identical financial statements, product outputs and config hashes at monthly and quarterly cadence; only observations/display change. No browser executable was available for pixel/layout verification.

Packaged for user deployment; not deployed. This release corrects the output-priority misunderstanding in r358/r359 while retaining their useful precision/unit fixes. CAC-summary visibility remains deferred.
