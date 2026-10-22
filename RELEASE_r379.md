# Foundry r379 — bulk payable-base category selection

Built on r378 / 3beebc0. Packaged; not deployed.

The operating-expense category dropdown has Select all and Deselect all actions at the top. The action header stays visible while scrolling. Select all includes every current expense category; Deselect all clears the selection. Both update the actual authored inclusion IDs, checked boxes, selected count and name summary together, without closing or remounting the dropdown. Users can still adjust individual categories afterward. Select all is an explicit snapshot of current categories; later-added categories are not silently included. Missing historical references are not reselected as current categories.

No engine calculation or validation changes. A cleared selection remains an incomplete payable base until categories are selected, as in r378. Existing selections are untouched until a user acts.

Validation: real Chromium checks verify all 22 fixture categories are included, Deselect all writes an empty list and clears every checkbox/chip, individual selection still works, the menu remains open, and keyboard/outside dismissal, stable IDs and 1440/1024/768 viewport containment continue to pass. Popup screenshot inspected. Inline JavaScript syntax and whitespace checks pass.
