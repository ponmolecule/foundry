# Foundry r358

Direct parent: r357 / d241939e8d4fbc0d6a9b59cd57e0149d767d632b.

The Activity section of each fee stream now shows its own calculated quantity from the latest engine run. It uses the existing compact sparkline, first/last-period values and expandable View all schedule. A shared six-significant-digit display preserves fractional counts consistently. Monetary balances/throughput display in $000s, converted once from the native-dollar quantity series. Counts remain natural counts. Period labels follow the model cadence.

The preview reads the stream's own stable quantity_series_id from fee_stream_quantities.series. It therefore includes shares, coefficients and other transformations already applied by the engine. A card-account stream with a 60% share shows its resulting card count, rather than repeating the full practice-count input. There is no second frontend calculation and no change to model economics or saved assumptions.

Duplicate upstream-number previews are removed from the fee-stream Activity editor. The source/reference selectors still identify the upstream source. No Show source / Hide source control is added for the result. Other modules' source previews and cost-pool component editors remain available. The same result preview applies to stream owners in fee products, lending and deposits; monetary inference follows cross-family quantity links.

Result previews update in place after a run, preserve an expanded View all schedule while refreshed, and distinguish a real zero from unavailable results. Stable quantity IDs preserve the result association through renaming/reordering. No results from an unrelated stream are substituted.

Verification: Node regression covers 60% share results, fractional/zero counts, engine-result ownership, monetary scaling, cross-family quantity semantics, compact/full schedule, stable IDs/reordering, in-place refresh, quarterly labels, missing results and no duplicate upstream blocks. Full inline-script syntax passes. Existing fee quantity-link engine checks, loan/deposit streams (9), stream figure recovery, revised r355 source-preview checks (23), and r357 precision integration pass. The r355 test removes expectations for the superseded stream source previews; other modules retain their checks. Browser pixel/layout verification was unavailable.

Packaged for user deployment; not deployed. Attrition precision and capacity staffing display fixes from r357 remain included. The CAC-summary visibility change remains deferred.
