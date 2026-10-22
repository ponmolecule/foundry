# Foundry r374 — annual compensation pools with linked minimums

Previous release: r373 / 16c9e04.

Existing revenue sources and marginal bands are reused. An optional recognition mode evaluates a complete model-year award and allocates it evenly across that year's periods. An optional minimum links to a percentage of selected roles' actual annual base compensation; the greater of minimum and band award is recognized, with a separately entered component payroll load. All role IDs, rates and thresholds are user-authored.

Existing components retain scheduled-event / YTD behavior unless explicitly changed. No engagement migration or numerical assumptions are introduced. Full-year allocation supports monthly/quarterly/annual Profile A and quarterly Profile B, requires complete model years and zero observation lag, and rejects feedback if posting the award changes its own revenue or selected-pay inputs. It does not infer an unsupported circular calculation or partial-year estimate.

The existing editor gains recognition and payroll-load controls. The selected-role picker is conditional; annual calculation details remain collapsed by default. The existing calculation audit exposes full-year terms and the minimum/award/load reconciliation. See docs/annual-compensation-pools.md.

Validation:
- Six new tests exercise the six-role salary floor, live salary changes, hiring dates and annual schedules, revenue/floor dominance, seven-year crossover, payroll loads, monthly/quarterly posting, both engines, invalid links/cadence/lag/partial years, feedback detection, public units and audit output.
- Seven existing workforce-capacity tests and all 14 existing additive-compensation checks pass.
- Monthly/quarterly Profile A and Profile B legacy outputs match r373 exactly (combined SHA256 3a3e50bdcd3bcb556e44e2a9a10fa1234eb7bc1fb0805b7e5e62e89253c25354).
- Real Chromium checks at 1440/1024/768 pixels verify contained controls, stable role links after rename/reorder, editable selections, collapsed audit details and reversible opt-in; no browser runtime errors. Prompt/editor screenshot inspected internally. Inline JavaScript syntax and whitespace checks pass.

Packaged; not deployed.
