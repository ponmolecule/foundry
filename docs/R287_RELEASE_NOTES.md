# r287 — Compact expanded securities configuration

Built directly on r286 (`bb2f5bd6d4c2b2da15b8eb5c6710241d000722a7`). UI only. Engine, schema, default assumptions, financial outputs and audit output are unchanged.

- Funding allocation: three compact columns at desktop width, fewer columns as available space narrows; the allocation policy and its explanation remain first.
- Interest-bearing balances: visible, bordered product panels; fiduciary rates grouped together, then non-interest and interest-bearing attach rates paired with their corresponding per-customer balances. Affiliated cash, operating cash and FRB stock remain distinct panels.
- Linked customer source: its selector and help text occupy separate lines, with bounded width rather than overlapping fixed grid columns.
- Schedules: cadence and trajectory controls share a row; existing values, sparklines and edit actions remain visible. Growth controls and paste Load/Clear/Close remain intact.
- Other liabilities: opening and base level paired; components have visible boundaries and compact driver/multiplier/remove rows. Named components retain their disclosure state.
- Managed portfolios: security table and row selection preserved; target settings aligned; selected security identity, classification, risk weight, opening stock, allocation, runoff and yield organized compactly.

The presentation moves existing DOM nodes. It does not recreate model inputs or replace their handlers. Funding header summaries continue updating after edits. The r286 theme, top navigation, section disclosure and assumptions inspector remain.

See R287_VALIDATION.md. Delivery includes actual browser screenshots at desktop and laptop widths and the full Git history for the usual deployment script.
