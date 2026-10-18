# Foundry r344

Completes an existing acquisition link: Pool × conversion can now consume another acquisition channel's calculated new-customer flow. Parent: r343 / 4340812.

## Authoring

Keep the existing source channel. Add a dependent channel using Pool × conversion. For Addressable pool choose Link, then the source channel's New customers. Enter the independent conversion/share path normally. In the current engagement, the user-authored channel names are Direct and EMR and the dependent conversion is 25%; these names and values are not embedded in engine logic.

References use stable derived-series IDs, not channel names or positions. Consumer channels may appear before sources and references may cross feeds. The resolver reads canonical monthly acquisition flows, applies the consumer's own conversion path, and then the normal feed roll-forward aggregates both channels. It does not link cumulative customer balances or divide monthly source flows by cadence again.

Self-links are disabled in the picker. Imported self-links, multichannel cycles, missing/ambiguous sources and incompatible count-flow uses fail validation. The picker shows missing saved references instead of visually substituting another source. Linked-source text explains live ownership.

Existing acquisition methods, source assumptions, workforce links and productivity multipliers are preserved. No new acquisition method, customer population subsystem or rounding convention was added. The source workbook's ROUNDUP is not replicated; this flow remains fractional.

## Verification

New tests cover dependent-channel totals, source edits, changing workforce, monthly/quarterly equivalence, stable identity across rename/reorder, consumer-before-source, multihop and cross-feed dependencies, public engine and acquisition audit, and missing/ambiguous/self/cyclic links. CAC UI 37 checks, CAC shapeshifter 61 checks, intra-period 63 checks, account activity 33 checks, productivity multiplier, linked loan balance and portfolio-paydown suites pass.

Packaged for the established Git-bundle deployment workflow. No engagement data changed; not deployed.
