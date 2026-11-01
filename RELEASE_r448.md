# r448 — Resizable product navigation

Built on r447, including live acquisition population weights for deposits.

Drag the divider between the product list and product editor to widen or narrow the list. Width is remembered locally in this browser and survives product changes. Double-click resets to 300px. Keyboard users can focus the divider and use Left/Right arrows; Home resets. Width is bounded to preserve room for the editor. The existing stacked layout on narrow windows is unchanged.

No engagement data, financial calculations or save mechanics change. Browser checks pass for drag, rerender persistence, local preference storage, keyboard adjustment, reset and narrow layout; the r447 deposit editor regression also passes.
