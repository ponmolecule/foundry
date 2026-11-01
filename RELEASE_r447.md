# r447 — Live acquisition composition for deposit balances

Deposit weighted breakdowns can now use Active acquisition population instead of entered shares. Map each amount row to one band of the selected Customer Acquisition feed. Foundry resolves active band shares each month using the selected count measure, then applies the existing balance share. Amounts, pricing and the acquisition feed are unchanged.

For Operating Accounts, select this weight source on the Lower Tier and keep its four amounts and 70% balance share. Apply it to the Upper Tier with 30%, or retain a link to the Lower Tier’s per-customer amount if already used. Existing engagements retain entered shares until explicitly switched; all saved entered weights remain available when switching back.

Mappings use stable band IDs and must cover every band once. Zero populations resolve to zero. Monthly and quarterly calculations retain existing stock/average semantics. No engagement-specific names, shares or dollar amounts are hardcoded.

Validation: causal mix changes, all bands, both tier shares, linked amounts, end/average measures, monthly/quarterly aggregation, invalid mappings and zero populations; browser selection, mapping, save/reload, layout and restoration of entered weights. Existing fixture fingerprints are unchanged.

Regression: all 276 test modules pass, including the reference-coverage check rerun after refreshing its generated inventory. The three pinned fixture run and financial fingerprints remain unchanged.
