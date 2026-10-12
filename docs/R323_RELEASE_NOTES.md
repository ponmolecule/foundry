# r323 — revenue-linked settlement liabilities and capped cash allocation

Direct continuation of r322 (b7bee17). Existing engagements are unchanged when the new options are absent. No new product type.

## Generic capabilities

Other liabilities → Formula / level gains a named Settlement liability component. Select fee-stream reported income, direct cost, or income less direct cost by stable ID. Selected observations add together without posting them again. Apply an explicit sign and a nonnegative weighted lag kernel; opening revenue history is most-recent-first and opening liability is an independent opening stock. Each lag contribution is audited. Inactive source periods are zero; missing active observations and negative resulting liabilities fail closed.

Holding units must match computation cadence. Monthly kernels consume monthly revenue; quarterly kernels consume quarterly revenue. Changing cadence cannot silently reinterpret a monthly kernel as quarterly. A quarterly kernel is not a reconstruction of intra-quarter monthly settlements. Monthly source timing must be modeled at monthly cadence when that precision is required.

Named Interest-bearing balances gains a cash allocation cap. Fixed cash allocations are reserved first; capped allocations use the remaining available cash in component order. Requested allocations never create borrowing to fund themselves. The single residual-cash component owns the remainder. Both allocations and residual cash can earn indexed annual yield (EFFR, SOFR or Prime plus a Flat/Growth/Explicit spread), measured on prior/current/average stock. A shared cash-interest flag switches both cash portions off without affecting liability balances or independently modeled off-book/other-asset income. Explicit zero-at-launch pricing is available for first-period prior/average interest measurement, without changing opening assets.

The existing mutually exclusive cash-interest branch posts the result once to cashInt. The legacy balances model cannot be active simultaneously. With a residual owner, generic fallback cash interest does not post a second amount. Existing AUA and Federal Reserve stock components are not implicitly deleted or recreated.

## Authoring and audit

Compact controls reuse the existing theme and bounded field sizes. A new settlement card opens; collapse state survives refresh. Selecting sources requires an explicit choice. Signed opening history accepts spreadsheet thousands separators and space-separated values. A liability consumed by a cash component cannot be deleted until its consumer is repointed/removed. Source catalog publishes fee-stream observations and settlement balance metadata. Audit sheets expose eligible revenue, lagged observations and contributions, opening settlement stock, requested/capped cash balance, pricing balance, yield and posted income.

## Explicit boundaries

This extends Profile A's existing named-balance engine. Settlement sources currently come from Fee Product streams with deterministic captured economics. Deposit/lending fee streams and Durbin-regulated repricing are not eligible: those paths update after initial captures and would require additional runtime wiring. Unsupported choices fail closed. Other-liability total/base opening balance and settlement-component opening balance are separate; do not enter the same opening liability in both.

The referenced bank curve remains authoritative in indexed mode. The build does not replace curve interpolation or manufacture source rates. For comparison against an abrupt annual source-rate change, confirm monthly curve values, or use an explicitly entered annual yield path to isolate the cash calculation.
