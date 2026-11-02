# r449 — Balance per customer and stream types

Built on r448 (66b2b4a). Presentation only. **No engine or calculation change**: no Python engine, validator or stored-field change; every handler and stored value is the one r447/r448 already use.

## Deposit balance per customer (Customer count × balance per customer)
- **Balance per customer** and **Weight source** are segmented fields, like Customer-count measure: Enter amount · Weighted breakdown · Link another deposit, and Entered shares · Acquisition population. Acquisition population is disabled when the selected feed has no population bands.
- **Balance share** is a field (value, path tag, "Use full balance"), not a collapsible section. With no share: "Full balance" and "+ Apply a balance share".
- The breakdown is an **Amount per customer** table in the fee-stream Count calculation style: Band · Share · × · $000s per customer · Weighted, with a mix bar, a 100% check and FLAT / GROWTH / SCHEDULE tags that open the existing series editor. It sits full width under the fields and results chart, so it stays a table at 1440px.
- Acquisition population: each row's band picker maps it to one feed band; shares are read-only (LIVE) from the latest run at the reference period. Entered shares stay stored for switching back.
- **Explain calculation** replaces "Calculated amount per customer · latest run": customers × $000s per customer × balance share = balance, at the strip's reference period. In the r447 fixture: 283.80 × 756.96 × 70% = 150,378 (live) and 283.80 × 750.39 × 70% = 149,074 (entered), matching the engine.
- Amounts display to two decimals of $000s; stored values keep full precision unless edited.

## Fee-stream table
- New **Type** column after Stream: Account, Balance, Transaction, Flat or Event, with the icon from the Add-a-fee-stream tiles. Source and setup rows are blank. Text columns wrap so the Result column stays visible at 1440px.

## Tests
- New: `web/tests_r449_deposit_amount_ui.cjs` (segmented fields, table placement, engine reconciliation, path tags, balance share round-trip, disabled live option, 1440/1024/768 containment, Type column).
- Updated for the new controls: r386 (+ Add band), r387 / r389 (table selector; amount display tolerance $10), r447 (segment clicks instead of selectOption).
- Also updated: tests_cost_recovery (lifts _stTypeHtml into its harness); reference entry labels and embedded coverage regenerated.

Suite: 278 modules, 0 failing.

ZIP contains delivery/foundry-full.bundle. BUILD_STAMP = foundry-r449-deposit-amount-ui.
