# r441 — Collapsible schedule grids

Built on r440 (ab3abbb7). Presentation only; no engine or assumption schema changes.

All three grid renderers now have Collapse schedule / Edit schedule controls: participation shares, fee-stream level/stock/coefficient schedules, and lending/deposit/OBS product schedules. Collapsed schedules retain their loaded-period count and first/last entered values. Collapse state survives editor redraws within the page session. Collapsing does not change saved assumptions or draft text.

Grid paste boxes use Close paste and the existing Paste values action; they no longer show the redundant closed-paste banner. Clear retains its r440 behavior.

Browser regression coverage exercises all grid families, collapse/reopen and redraw persistence, unchanged configuration, draft preservation, and loading after reopening.
