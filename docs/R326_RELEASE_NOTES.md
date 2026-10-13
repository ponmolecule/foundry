# r326 — focused Securities & AOCI authoring
Built directly on r325. Existing top-level menus, typography, authoring controls and engine are preserved.
The grouped local navigator selects a single visible editor. Inactive editors remain mounted and wired; switching only changes presentation, never financial configuration. Active selection survives authoring re-renders. Compact charcoal/gold navigation follows the existing palette. Small screens wrap navigation above the selected editor.
Settlement holding-period add action moves into the header. Only the oldest lag has a small labeled remove control; current period cannot be removed. Numeric fields and dropdowns are bounded, with a wide source picker. Existing saved weights/history remain unchanged.
Validation: authoring helper, focused navigation state tests, full inline syntax and whitespace checks. No browser-rendered QA claimed. Engine unchanged.
