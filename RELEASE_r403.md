# Foundry r403 — Header engagement selector spacing

Direct continuation of r402 (f7a9990). The bank/version control moves to the right, and its version chip maximum and editing input grow by one third. The saved-engagement menu grows from 280px to 373px and opens beneath the version control rather than extending left over the brand. It is clamped to the viewport and repositions on resize. Narrow screens reduce header spacing and allow the name editor to shrink.

No configuration, financial, save or recovery behavior changes. Browser validation covers 1600, 1180, 1024 and 768px, menu anchoring/containment, editor width and unchanged configuration. The desktop header/menu layout was visually inspected. Inline JavaScript syntax and git whitespace checks pass.
