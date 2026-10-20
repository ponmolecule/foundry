# Foundry r368

Previous release: r367 / 37d96fd. Includes the intervening deferred CAC fix-log documentation; those deferred features remain unimplemented.

Adds a small muted Numbers link below calculated product-result panels. All tables and copy controls stay in an on-demand native dialog, preserving the closed page layout. Standard lending, deposits and off-balance-sheet/fee-product panels, funded-flow lending and resolved fee-stream previews use the same inspector.

Credit panels expose separate Charge-offs and Allowance rows. Other panels expose relevant balance, funded-flow, interest, annual yield, fee and cost paths. Units and native Month/Quarter labels are explicit. Copy values copies only one series as a tab-separated row; Copy table for Excel includes series/unit labels and all periods. Clipboard failure reveals a selected manual-copy textarea in the dialog. Zero values remain available; missing observations stay blank; last-complete-run results are labelled. Engine result arrays are never mutated or reconstructed from chart geometry.

The public exact-diagnostic view now additionally preserves unrounded interest and average-balance arrays. Numeric inspection prefers exact diagnostic series where available. Financial calculation logic is unchanged.

Verification: inspector rendering and actual copy handlers cover closed-state discretion, both credit series, precision, monthly/quarterly TSV, zero/missing observations, clipboard success/fallback and non-mutation. Existing product-layout, flow-lending, resolved-stream and stream-output regressions pass. Full console syntax and whitespace checks pass. Browser pixel verification unavailable.

Packaged for deployment; not deployed.
