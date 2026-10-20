# Foundry r364

Direct parent: r363 / 8be474a.

Move Balance authoring to a dedicated panel below product identity and before the engine strip and numbered setup sections. Shared control covers all four lending methods in both funded-flow and standard lending layouts. Remove the mode selector from Costs & accounting and from the decorated balance subsection. Existing mode-change handler immediately rerenders the matching setup. Selector remains available independently of subsection collapse state. Calculation contracts unchanged.

Verification: all inline JavaScript syntax; selector rendering for all four modes and original handler; position before sections and absence from Costs; existing flow-lending renderer and customer-linked loan balance suite pass. Browser visual verification unavailable. Packaged, not deployed.
