# r305 — Consistent fee-stream authoring

Built on r304 (b9f7fea). Existing saved fee products keep their configuration and numbers; opening the editor does not migrate their economics.

- Balance streams derived from another stock now use one Stock % of source editor. Historical multiple/pct values are represented exactly (multiple takes precedence; absent both means 100%). An explicitly entered zero remains zero. Newly selecting a derived balance begins at 100%, consistent with the historical identity derivation.
- AUC balance measure is selectable per consuming managed-notional stream: Average (begin + end), or End of period. Missing measure remains Average. The selection affects quantity, fees, dependent streams, and their audit economics. Source explanation shows both balances; per-stream working uses the selected measure.
- Annual rate change now has Flat / Growth / Explicit schedules. The starting fee rate applies throughout Year 1. Change 1 applies after Year 1, Change 2 after Year 2, and so on. Last explicit change carries forward. Values are relative changes, not percentage-point deductions from the fee rate. Example: 14 bp, then −2%, then −3% gives 14 / 13.72 / 13.3084 bp in Years 1 / 2 / 3. Growth changes the change assumption itself: −2% with 50% annual growth becomes −3% at the next transition.
- Changes are authored as yearly Step paths; they are not interpolated across months. Flat retains the old compounding contract. New paths validate numeric finite changes at least −100%; missing schedules fail closed.
- Annual-change path, value and compact schedule disclosure share one line. Schedule has Load (replace), Clear and a saved-value preview. Selecting a new schedule initially seeds the current change so the mode switch is valid. Paste replaces it.
- Pricing switches suspend inactive flat rate paths instead of allowing hidden state to reject annual-change pricing. Existing menus, tabs, colors and unrelated stream types are retained.

Location: fee stream → Activity → AUC balance measure; Pricing → Rate behavior → Annual rate change.
